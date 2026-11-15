"""Excel import of the legacy monitoring workbook, on its own empty database (bootstrap admin only).
The workbook is built here with the same quirks as the real file: template sheet, hidden goal list, leaked header
labels, formula zeros, Persian digits, text in number cells, a broken numeric description, a summary sheet."""

import io
import json

import psycopg
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app import bootstrap
from app.core.db import Base, get_db
from app.main import app
from app.models import KeyResult, KRCollaborator, KRVersion, Objective, ReviewEntry, StrategicGoal, Unit
from app.core.audit import verify_chain
from app.services import excel_import as xi
from app.services.calc import percent
from app.services.okr import current_kr_version, definition_of

API = "/api/v1"
PWD = "Passw0rd-test"
HEAD = ["توضیحات", "خط مبنا", "هدف", "هدف کسب و کاری", "تیم‌های همکار", "شرح انتظار"]


def _objective(ws, r: int, n: int, title):
    ws.cell(r, 1, f"Objective {n}")
    ws.cell(r, 2, title)
    for i, h in enumerate(HEAD):
        ws.cell(r, 3 + i, h)
    for k in range(6):
        ws.cell(r, 9 + 3 * k, f"R{k + 1}")
        ws.cell(r + 1, 9 + 3 * k, "میزان پیشرفت")
        ws.cell(r + 1, 10 + 3 * k, "درصد پیشرفت")
        ws.cell(r + 1, 11 + 3 * k, "توضیحات")


def _kr(ws, r: int, code: str, title=None, desc=None, base=None, target=None, goal=None, teams=None, rounds=None):
    ws.cell(r, 1, f"KR {code}")
    for col, v in ((2, title), (3, desc), (4, base), (5, target), (6, goal), (7, teams)):
        if v is not None:
            ws.cell(r, col, v)
    for k in range(6):
        ws.cell(r, 10 + 3 * k, 0)  # the percent formula's cached zero in every round
    for n, (value, pct, note) in (rounds or {}).items():
        if value is not None:
            ws.cell(r, 9 + 3 * (n - 1), value)
        if pct is not None:
            ws.cell(r, 10 + 3 * (n - 1), pct)
        if note is not None:
            ws.cell(r, 11 + 3 * (n - 1), note)


def workbook() -> bytes:
    wb = Workbook()
    t = wb.active
    t.title = "الگو"
    _objective(t, 2, 1, "عنوان هدف")
    _objective(t, 8, 6, "تعهدات همسوسازی")
    g = wb.create_sheet("Sheet17")
    for i, x in enumerate(["تحقق تارگت فروش", "تحول ديجيتال"], 1):  # Arabic yeh on purpose
        g.cell(i, 1, x)
    g.sheet_state = "hidden"

    s = wb.create_sheet("فروش ")
    _objective(s, 2, 1, "افزایش فروش")
    _kr(s, 4, "1.1", "فروش کالا (میلیارد تومان)", base=0, target=120, goal="تحقق تارگت فروش", teams="مالی، مارکتینگ",
        rounds={1: (14.2, 11.83, "خوب بود")})
    _kr(s, 5, "1.2", "اطلاعات محصولات", target="۲۰۰", goal="علیزاده")
    _kr(s, 6, "1.3", "تحلیل خرید", desc="-180583", goal="تحول دیجیتال", rounds={1: (None, 40, "در حال انجام")})
    _kr(s, 7, "1.4", None, teams="بی‌عنوان")
    _kr(s, 8, "1.5", "مصرف چرم راکد", base=0, target=8000, rounds={1: ("3000فوت مربع", None, 0)})
    _objective(s, 10, 6, "تعهدات همسوسازی")  # untouched template block

    h = wb.create_sheet("Home")
    _objective(h, 2, 1, "زیرساخت")
    _kr(h, 4, "1.1", "تدوین ساختار سازمانی", target=1, rounds={2: (1, 100, None)})

    m = wb.create_sheet("مالی")
    _objective(m, 2, 1, "نقدینگی")
    _kr(m, 4, "1.1", "کاهش روز وصول مطالبات", base=57, target=47, rounds={1: (56, 10, None)})

    sm = wb.create_sheet("خلاصه گزارش")
    sm.append(["ردیف", "تیم", "R0", "R1"])
    sm.append([1, "فروش", 0, "#REF!"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


BOOK = workbook()


@pytest.fixture(scope="module")
def env():
    with psycopg.connect("postgresql://okr:okr_dev_password@localhost:5433/okr", autocommit=True) as conn:
        if not conn.execute("select 1 from pg_database where datname='okr_test_import'").fetchone():
            conn.execute("create database okr_test_import")
    eng = create_engine("postgresql+psycopg://okr:okr_dev_password@localhost:5433/okr_test_import")
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, expire_on_commit=False)
    with factory() as db:
        bootstrap.install(db, "admin", PWD)

    def override():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    c = TestClient(app)
    r = c.post(f"{API}/auth/login", json={"username": "admin", "password": PWD})
    yield c, {"Authorization": "Bearer " + r.json()["access_token"]}, factory
    app.dependency_overrides.pop(get_db, None)
    eng.dispose()


def _post(c, a, what: str, mapping: dict | None = None, data: bytes = BOOK):
    form = {"mapping": json.dumps(mapping)} if mapping else {}
    return c.post(f"{API}/admin/import/excel/{what}", headers=a, data=form,
                  files={"file": ("okr.xlsx", data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})


def _counts(factory) -> tuple[int, ...]:
    with factory() as db:
        return tuple(db.scalar(select(func.count()).select_from(m)) for m in (Unit, Objective, KeyResult, ReviewEntry, StrategicGoal))


def test_parse_tolerates_the_real_file_quirks():
    book = xi.parse_workbook(BOOK)
    assert [s.name.strip() for s in book.sheets] == ["فروش", "Home", "مالی"]
    assert book.ignored_sheets == ["الگو", "خلاصه گزارش"]
    assert book.goal_catalog == ["تحقق تارگت فروش", "تحول دیجیتال"]  # Arabic letters normalized
    sales = book.sheets[0]
    assert [o.title for o in sales.objectives] == ["افزایش فروش"]  # template block dropped
    krs = {k.code: k for k in sales.objectives[0].krs}
    assert sorted(krs) == ["1.1", "1.2", "1.3", "1.5"]  # untitled 1.4 skipped with a warning
    assert any(i.where == "KR 1.4" for i in sales.issues)
    assert krs["1.2"].target == 200 and krs["1.2"].baseline is None  # Persian digits
    assert krs["1.3"].description is None and krs["1.3"].issues  # "-180583" is a broken formula
    assert krs["1.1"].rounds[0].value == 14.2 and krs["1.1"].rounds[0].note == "خوب بود"
    r15 = krs["1.5"].rounds[0]
    assert (r15.value, r15.raw_text, r15.note) == (3000, "3000فوت مربع", None)  # number taken from text, "0" note empty


def test_non_workbook_and_non_admin_are_refused(env):
    c, a, _ = env
    assert _post(c, a, "preview", data=b"not a spreadsheet").status_code == 422
    empty = io.BytesIO()
    Workbook().save(empty)
    r = _post(c, a, "preview", data=empty.getvalue())
    assert r.status_code == 422 and "قالب" in r.json()["detail"]


def test_preview_without_active_cycle_is_blocked(env):
    c, a, factory = env
    r = _post(c, a, "commit")
    assert r.status_code == 200, r.text
    j = r.json()
    assert not j["committed"] and j["blocking"] and j["cycle"] is None
    assert _counts(factory) == (0, 0, 0, 0, 0)


@pytest.fixture(scope="module")
def world(env):
    c, a, _ = env
    root = c.post(f"{API}/admin/units", headers=a, json={"name": "شرکت"}).json()["id"]
    fin = c.post(f"{API}/admin/units", headers=a, json={"name": "مالي", "parent_id": root}).json()["id"]
    cyc = c.post(f"{API}/admin/cycles", headers=a, json={
        "name": "۱۴۰۵ نیمه دوم", "starts_on": "2026-09-23", "ends_on": "2027-03-20",
        "time_points": [{"kind": "start", "label": "شروع"}, {"kind": "review", "label": "R1"},
                        {"kind": "review", "label": "R2"}, {"kind": "final", "label": "نهایی"}]}).json()
    assert c.patch(f"{API}/admin/cycles/{cyc['id']}", headers=a, json={"status": "active"}).status_code == 200
    return {"root": root, "fin": fin, "cycle": cyc["id"]}


def test_preview_reports_everything_and_changes_nothing(env, world):
    c, a, factory = env
    before = _counts(factory)
    r = _post(c, a, "preview")
    assert r.status_code == 200, r.text
    j = r.json()
    assert not j["committed"] and not j["blocking"] and j["review_points"] == ["R1", "R2"]
    by = {s["sheet"].strip(): s for s in j["sheets"]}
    assert by["فروش"]["action"] == "create" and by["فروش"]["unit_id"] is None
    assert by["Home"]["unit_id"] == world["root"]  # Home -> the single top unit
    assert by["مالی"]["unit_id"] == world["fin"]  # "مالي" (Arabic yeh) matches
    assert (by["فروش"]["objectives"], by["فروش"]["krs"], by["فروش"]["values"], by["فروش"]["notes"]) == (1, 4, 3, 3)
    t = j["totals"]
    assert (t["objectives"], t["krs"], t["values"], t["units_created"], t["goals_created"]) == (3, 6, 5, 1, 2)
    assert j["unmatched_goals"] == [{"text": "علیزاده", "krs": 1}]
    assert {g["title"]: g["action"] for g in j["goals"]} == {"تحقق تارگت فروش": "create", "تحول دیجیتال": "create"}
    assert _counts(factory) == before


def test_commit_writes_versions_values_and_history(env, world):
    c, a, factory = env
    r = _post(c, a, "commit")
    assert r.status_code == 200 and r.json()["committed"], r.text
    with factory() as db:
        sales = db.scalars(select(Unit).where(Unit.name == "فروش")).one()
        krs = {current_kr_version(db, k.id).title: k for k in db.scalars(
            select(KeyResult).join(Objective).where(Objective.unit_id == sales.id))}
        k11 = krs["فروش کالا (میلیارد تومان)"]
        v11 = current_kr_version(db, k11.id)
        assert v11.reason and "اکسل" in v11.reason and v11.kind == "numeric" and v11.strategic_goal_id
        assert "مارکتینگ" in v11.description  # unmatched collaborator kept as text
        assert [db.get(Unit, x.unit_id).name for x in db.scalars(select(KRCollaborator).where(
            KRCollaborator.key_result_id == k11.id))] == ["مالي"]
        e = db.scalars(select(ReviewEntry).where(ReviewEntry.key_result_id == k11.id)).one()
        assert round(percent(definition_of(v11), e.value), 2) == 11.83 and e.note == "خوب بود"  # same as Excel
        v12 = current_kr_version(db, krs["اطلاعات محصولات"].id)
        assert (v12.baseline, v12.target) == (0, 200) and "علیزاده" in v12.description
        v13 = current_kr_version(db, krs["تحلیل خرید"].id)
        assert v13.kind == "milestone"
        assert db.scalars(select(ReviewEntry.value).where(ReviewEntry.key_result_id == krs["تحلیل خرید"].id)).one() == 40
        e15 = db.scalars(select(ReviewEntry).where(ReviewEntry.key_result_id == krs["مصرف چرم راکد"].id)).one()
        assert e15.value == 3000 and "فوت مربع" in e15.note
        fin_kr = db.scalars(select(KeyResult).join(Objective).where(Objective.unit_id == world["fin"])).one()
        fin_e = db.scalars(select(ReviewEntry).where(ReviewEntry.key_result_id == fin_kr.id)).one()
        assert percent(definition_of(current_kr_version(db, fin_kr.id)), fin_e.value) == 10.0  # descending KR
        assert db.scalar(select(func.count()).select_from(KRVersion)) == 6
        assert verify_chain(db) is None  # hundreds of audit rows in one transaction keep an unbroken chain
    audit = c.get(f"{API}/admin/audit", headers=a).json()
    assert any(ev["action"] == "import" for ev in audit["events"])


def test_reimport_does_not_duplicate(env, world):
    c, a, factory = env
    before = _counts(factory)
    j = _post(c, a, "commit").json()
    by = {s["sheet"].strip(): s["status"] for s in j["sheets"]}
    assert by["Home"] == by["مالی"] == "already_imported"
    assert by["فروش"] == "already_imported"  # matched to the unit created by the first import
    assert _counts(factory) == before


def test_mapping_can_skip_or_redirect_sheets(env, world):
    c, a, factory = env
    before = _counts(factory)
    j = _post(c, a, "preview", mapping={"فروش ": {"action": "skip"}, "Home": {"action": "skip"},
                                        "مالی": {"action": "create", "name": "مالی کارخانه"}}).json()
    by = {s["sheet"].strip(): s for s in j["sheets"]}
    assert by["فروش"]["status"] == "skipped" and by["مالی"]["status"] == "ready" and j["totals"]["units_created"] == 1
    assert _post(c, a, "preview", mapping={"Home": {"action": "bogus"}}).status_code == 422
    assert _counts(factory) == before
