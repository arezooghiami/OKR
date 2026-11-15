"""Units + users from Excel, on an empty database: preview saves nothing, commit creates the tree and accounts,
the downloaded template re-imports with no changes, and bad rows are reported without stopping good ones."""

import io

import psycopg
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app import bootstrap
from app.core.db import Base, get_db
from app.main import app

API = "/api/v1"
PWD = "Passw0rd-test"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture(scope="module")
def c():
    with psycopg.connect("postgresql://okr:okr_dev_password@localhost:5433/okr", autocommit=True) as conn:
        if not conn.execute("select 1 from pg_database where datname='okr_test_org'").fetchone():
            conn.execute("create database okr_test_org")
    eng = create_engine("postgresql+psycopg://okr:okr_dev_password@localhost:5433/okr_test_org")
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, expire_on_commit=False)
    with factory() as db:
        bootstrap.install(db, "admin", PWD)

    def override():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.pop(get_db, None)
    eng.dispose()


def hdr(c, user, pwd=PWD):
    r = c.post(f"{API}/auth/login", json={"username": user, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def book(units=None, users=None) -> bytes:
    wb = Workbook()
    wb.active.title = "یادداشت"
    if units is not None:
        ws = wb.create_sheet("واحدها")
        ws.append(["نام واحد", "واحد بالادستی", "نوع واحد", "کد", "مدیر واحد"])
        for r in units:
            ws.append(r)
    if users is not None:
        ws = wb.create_sheet("کاربران")
        ws.append(["نام کاربری", "نام و نام خانوادگی", "ایمیل", "رمز اولیه", "نقش", "واحد"])
        for r in users:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def send(c, h, data, what="preview"):
    r = c.post(f"{API}/admin/import/org/{what}", headers=h, files={"file": ("org.xlsx", data, XLSX)})
    assert r.status_code == 200, r.text
    return r.json()


UNITS = [
    ["فنی", "چرم مشهد", "معاونت", "T1", "علی کریمی"],  # child before its parent
    ["چرم مشهد", None, None, None, None],                # the root
    ["شبکه", "فنی", "گروه کاری", None, None],            # a new unit type
    ["مالی", None, None, None, None],                     # no parent: under the root
    ["فنی", None, None, None, None],                      # duplicate
    ["انبار", "لجستیک", None, None, None],                # unknown parent
]
USERS = [
    ["ali.k", "علی کریمی", "ali@example.com", None, "مدیر واحد", "فنی"],  # generated password
    ["ali.k", None, None, None, "مسئول KR", "شبکه"],                     # second role, same user
    ["sara", "سارا رضایی", None, "Sara-pass-1", "مسئول KR", "مالی"],
    ["nazer", "ناظر سازمان", None, "Nazer-pass-1", "ناظر", None],         # org-wide role
    ["x", "کوتاه", None, None, "ناظر", None],                              # bad username
    ["reza", "رضا", None, None, "نقش ناموجود", "مالی"],                    # unknown role
    ["omid", "امید", None, None, "مسئول KR", "انبار"],                     # unit that failed
]


def test_preview_saves_nothing_and_reports_every_row(c):
    a = hdr(c, "admin")
    r = send(c, a, book(UNITS, USERS))
    assert not r["committed"] and r["credentials"] == []
    st = {(x["row"], x["name"]): (x["status"], x["message"]) for x in r["units"]}
    assert st[(2, "فنی")][0] == "new" and st[(3, "چرم مشهد")][0] == "new" and st[(5, "مالی")][0] == "new"
    assert st[(6, "فنی")] == ("error", "این واحد در فایل تکرار شده است")
    assert st[(7, "انبار")][0] == "error" and "لجستیک" in st[(7, "انبار")][1]
    us = [(x["name"], x["status"]) for x in r["users"]]
    assert us == [("ali.k", "new"), ("ali.k", "update"), ("sara", "new"), ("nazer", "new"), ("x", "error"),
                  ("reza", "error"), ("omid", "error")]
    assert "خطا دارد" in r["users"][6]["message"]
    assert r["totals"] == {"units_new": 4, "units_updated": 0, "users_new": 3, "users_updated": 1, "errors": 5}
    assert r["types_created"] == ["گروه کاری"]
    assert c.get(f"{API}/admin/units", headers=a).json() == []  # nothing saved


def test_commit_builds_tree_and_accounts(c):
    a = hdr(c, "admin")
    r = send(c, a, book(UNITS, USERS), "commit")
    assert r["committed"]
    assert [x["username"] for x in r["credentials"]] == ["ali.k"]  # only users without a given password
    units = {u["name"]: u for u in c.get(f"{API}/admin/units", headers=a).json()}
    assert units["چرم مشهد"]["parent_id"] is None
    assert units["فنی"]["parent_id"] == units["چرم مشهد"]["id"] and units["فنی"]["manager_name"] == "علی کریمی"
    assert units["مالی"]["parent_id"] == units["چرم مشهد"]["id"]
    assert units["شبکه"]["parent_id"] == units["فنی"]["id"] and units["شبکه"]["type"] == "گروه کاری"
    # the generated password works once handed out; both roles were granted
    hdr(c, "ali.k", r["credentials"][0]["password"])
    users = {u["username"]: u for u in c.get(f"{API}/admin/users", headers=a).json()}
    assert len(users["ali.k"]["memberships"]) == 2
    assert users["nazer"]["memberships"][0]["unit_id"] is None
    hdr(c, "sara", "Sara-pass-1")


def test_template_is_the_current_org_and_reimports_unchanged(c):
    a = hdr(c, "admin")
    t = c.get(f"{API}/admin/import/org/template.xlsx", headers=a)
    assert t.status_code == 200 and t.headers["content-type"].startswith(XLSX)
    wb = load_workbook(io.BytesIO(t.content))
    assert wb.sheetnames == ["واحدها", "کاربران", "راهنما"]
    names = [r[0] for r in wb["واحدها"].iter_rows(min_row=2, values_only=True)]
    assert names[0] == "چرم مشهد" and set(names) == {"چرم مشهد", "فنی", "مالی", "شبکه"}
    assert ("ali.k", "مدیر واحد", "فنی") in {(r[0], r[4], r[5]) for r in wb["کاربران"].iter_rows(min_row=2, values_only=True)}
    r = send(c, a, t.content)
    assert r["totals"] == {"units_new": 0, "units_updated": 0, "users_new": 0, "users_updated": 0, "errors": 0}
    assert {x["status"] for x in r["units"] + r["users"]} == {"same"}


def test_edits_move_and_guard_loops(c):
    a = hdr(c, "admin")
    r = send(c, a, book([["شبکه", "مالی", None, None, "مدیر شبکه"], ["فنی", "شبکه", None, None, None]],
                        [["sara", None, None, "new-password-1", None, None]]), "commit")
    rows = {x["name"]: x for x in r["units"]}
    assert rows["شبکه"]["status"] == "update" and "مالی" in rows["شبکه"]["detail"] and "مدیر" in rows["شبکه"]["detail"]
    assert rows["فنی"]["status"] == "update"  # شبکه moved out first, so فنی may now go under it
    assert r["users"][0]["message"] == "رمز کاربر موجود از راه اکسل عوض نمی‌شود"
    hdr(c, "sara", "Sara-pass-1")  # unchanged
    # accounts made before the username rule (e.g. two characters) still match by username
    with c.app.dependency_overrides[get_db]().__next__() as db:
        from app.models import User
        db.add(User(username="u1", full_name="قدیمی", password_hash=None))
        db.commit()
    old = send(c, a, book(users=[["u1", None, None, None, "ناظر", None]]))
    assert old["users"][0]["status"] == "update"
    loop = send(c, a, book([["مالی", "فنی", None, None, None]]))
    assert loop["units"][0]["status"] == "error"  # فنی is under شبکه under مالی


def test_bad_files_and_access(c):
    a = hdr(c, "admin")
    r = c.post(f"{API}/admin/import/org/preview", headers=a, files={"file": ("x.xlsx", b"not excel", XLSX)})
    assert r.status_code == 422
    empty = send(c, a, book())
    assert empty["blocking"] and not empty["committed"]
    h = hdr(c, "sara", "Sara-pass-1")
    assert c.get(f"{API}/admin/import/org/template.xlsx", headers=h).status_code == 403
    assert c.post(f"{API}/admin/import/org/commit", headers=h, files={"file": ("o.xlsx", book([["x"]]), XLSX)}).status_code == 403
