"""Phase 2 of docs/07: five roles, per-unit overrides, role-based landing, recording not blocked by a missing
meeting time, «برگزار شد» by the system manager (also in bulk), and KR owners assigned in bulk."""

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.db import Base, get_db
from app.main import app
from app.models import KeyResult, Objective, Role, TimePoint, Unit, UnitSession, User
from app.services.access import Access
from tests import demo_seed as seed

API = "/api/v1"
URL = "postgresql+psycopg://okr:okr_dev_password@localhost:5433/okr_test_roles"


@pytest.fixture(scope="module")
def env():
    with psycopg.connect("postgresql://okr:okr_dev_password@localhost:5433/okr", autocommit=True) as conn:
        if not conn.execute("select 1 from pg_database where datname='okr_test_roles'").fetchone():
            conn.execute("create database okr_test_roles")
    eng = create_engine(URL)
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, expire_on_commit=False)
    with factory() as db:
        seed.seed(db)

    def override():
        with factory() as s:
            yield s

    app.dependency_overrides[get_db] = override
    yield TestClient(app), factory
    app.dependency_overrides.pop(get_db, None)
    eng.dispose()


def h(env, full_name):
    c, factory = env
    with factory() as db:
        username = db.scalars(select(User.username).where(User.full_name == full_name)).one()
    r = c.post(f"{API}/auth/login", json={"username": username, "password": seed.DEMO_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def uid(env, name):
    with env[1]() as db:
        return db.scalars(select(Unit.id).where(Unit.name == name)).one()


def sessions_of(env, unit):
    u = uid(env, unit)
    with env[1]() as db:
        rows = db.execute(select(UnitSession, TimePoint.label).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                          .where(UnitSession.unit_id == u)).all()
        return {label: s for s, label in rows}


def test_landing_page_follows_the_role(env):
    c = env[0]

    def me(who):
        return c.get(f"{API}/me", headers=h(env, who)).json()

    assert me("مهدی ایزدی")["home"] == "dashboard"   # super admin
    assert me("لیلا احمدی")["home"] == "dashboard"   # system manager
    assert me("احمد نوری")["home"] == "dashboard"    # system expert
    assert me("علی کریمی")["home"] == "unit"         # unit manager
    assert me("سینا رضایی")["home"] == "my"          # unit expert
    assert me("لیلا احمدی")["can_hold"]
    assert not me("علی کریمی")["can_hold"] and not me("احمد نوری")["can_hold"]


def test_hold_belongs_to_the_system_manager(env):
    c = env[0]
    r2 = sessions_of(env, "فناوری اطلاعات")["R2"]
    assert c.get(f"{API}/sessions/{r2.id}", headers=h(env, "علی کریمی")).json()["can_hold"] is False
    assert c.post(f"{API}/sessions/{r2.id}/hold", headers=h(env, "علی کریمی"), json={}).status_code == 403
    assert c.post(f"{API}/sessions/{r2.id}/hold", headers=h(env, "احمد نوری"), json={}).status_code == 403
    mgr = h(env, "لیلا احمدی")
    assert c.get(f"{API}/sessions/{r2.id}", headers=mgr).json()["can_hold"] is True
    # backdating stays with the super admin
    assert c.post(f"{API}/sessions/{r2.id}/hold", headers=mgr, json={"held_at": "2026-10-20T08:00:00Z"}).status_code == 403
    assert c.post(f"{API}/sessions/{r2.id}/hold", headers=mgr, json={}).json()["status"] == "held"


def test_bulk_hold_reports_each_session(env):
    c = env[0]
    a, b = sessions_of(env, "تدارکات")["R2"], sessions_of(env, "کنترل کیفیت")["R2"]
    missing = "00000000-0000-0000-0000-000000000000"
    r = c.post(f"{API}/sessions/hold", headers=h(env, "لیلا احمدی"),
               json={"session_ids": [str(a.id), str(b.id), missing]})
    assert r.status_code == 200
    res = {x["session_id"]: x for x in r.json()}
    assert res[str(a.id)]["ok"] and res[str(b.id)]["ok"] and not res[missing]["ok"]
    with env[1]() as db:
        assert db.get(UnitSession, a.id).status == "held" and db.get(UnitSession, b.id).status == "held"
    # a unit manager gets a refusal per session and nothing is held
    other = sessions_of(env, "فروش سازمانی")["R2"]
    r = c.post(f"{API}/sessions/hold", headers=h(env, "علی کریمی"), json={"session_ids": [str(other.id)]})
    assert r.json()[0]["ok"] is False
    with env[1]() as db:
        assert db.get(UnitSession, other.id).status != "held"


def test_missing_meeting_time_does_not_block_recording(env):
    c = env[0]
    s = sessions_of(env, "معاونت مالی")["R2"]
    assert s.status == "unscheduled"
    admin = h(env, "مهدی ایزدی")
    page = c.get(f"{API}/sessions/{s.id}", headers=admin).json()
    assert page["entry_blocker"] is None
    kr = page["objectives"][0]["key_results"][0]
    r = c.put(f"{API}/sessions/{s.id}/entries/{kr['id']}", headers=admin, json={"value": 12})
    assert r.status_code == 200, r.text
    # an unscheduled session can still be marked held
    assert c.post(f"{API}/sessions/{s.id}/hold", headers=h(env, "لیلا احمدی"), json={}).json()["status"] == "held"


def test_unit_override_changes_one_unit_only(env):
    c, factory = env
    admin = h(env, "مهدی ایزدی")
    with factory() as db:
        expert = db.scalars(select(Role.id).where(Role.name == "کارشناس واحد")).one()
        sina = db.scalars(select(User.id).where(User.full_name == "سینا رضایی")).one()
    it, sales = uid(env, "فناوری اطلاعات"), uid(env, "فروش سازمانی")
    with factory() as db:
        assert not Access(db, db.get(User, sina)).can("key_result", "edit", it)
    # in IT the unit expert may edit KR definitions but no longer record values
    r = c.put(f"{API}/admin/roles/{expert}/overrides/{it}", headers=admin,
              json={"permissions": {"key_result": {"edit": "allow"}, "review_value": {"edit": "deny"}}})
    assert r.status_code == 200 and r.json()[0]["unit"] == "فناوری اطلاعات"
    with factory() as db:
        acc = Access(db, db.get(User, sina))
        assert acc.can("key_result", "edit", it)
        assert not acc.can("review_value", "edit", it)
        assert "استثنای واحد" in acc.decide("review_value", "edit", it).reason
        assert acc.visible_units("review_value", "edit") == set()
        assert not acc.can("key_result", "edit", sales)  # an override never widens the role's scope
    # only the super admin manages exceptions; an empty body removes them
    assert c.get(f"{API}/admin/roles/{expert}/overrides", headers=h(env, "لیلا احمدی")).status_code == 403
    assert c.put(f"{API}/admin/roles/{expert}/overrides/{it}", headers=admin, json={"permissions": {}}).json() == []
    with factory() as db:
        assert Access(db, db.get(User, sina)).can("review_value", "edit", it)


def test_visible_units_respects_deny(env):
    """A deny on one of the user's roles hides the units in lists too, exactly like can()."""
    c, factory = env
    admin = h(env, "مهدی ایزدی")
    with factory() as db:
        viewer = db.scalars(select(User.id).where(User.full_name == "احمد نوری")).one()
        expert = db.scalars(select(Role.id).where(Role.name == "کارشناس سامانه")).one()
        assert Access(db, db.get(User, viewer)).visible_units("report", "view") is None
    mine = next(r for r in c.get(f"{API}/admin/roles", headers=admin).json()["roles"] if r["id"] == str(expert))
    perms = {k: dict(v) for k, v in mine["permissions"].items()}
    perms["report"]["view"] = "deny"
    assert c.put(f"{API}/admin/roles/{expert}", headers=admin,
                 json={"permissions": perms, "scopes": mine["scopes"]}).status_code == 200
    with factory() as db:
        assert Access(db, db.get(User, viewer)).visible_units("report", "view") == set()
    perms["report"]["view"] = "allow"
    assert c.put(f"{API}/admin/roles/{expert}", headers=admin,
                 json={"permissions": perms, "scopes": mine["scopes"]}).status_code == 200


def test_new_kr_defaults_to_objective_owner_and_bulk_owner(env):
    c, factory = env
    boss = h(env, "علی کریمی")
    it = uid(env, "فناوری اطلاعات")
    with factory() as db:
        ali = db.scalars(select(User.id).where(User.full_name == "علی کریمی")).one()
        sina = db.scalars(select(User.id).where(User.full_name == "سینا رضایی")).one()
    o = c.post(f"{API}/units/{it}/objectives", headers=boss, json={"title": "هدف آزمایشی مسئول", "owner_id": str(ali)}).json()
    k1 = c.post(f"{API}/objectives/{o['id']}/key-results", headers=boss, json={"title": "یک", "baseline": 0, "target": 10}).json()
    k2 = c.post(f"{API}/objectives/{o['id']}/key-results", headers=boss, json={"title": "دو", "baseline": 0, "target": 5}).json()
    assert c.get(f"{API}/key-results/{k1['id']}", headers=boss).json()["definition"]["owner"] == "علی کریمی"
    r = c.post(f"{API}/units/{it}/key-results/owner", headers=boss,
               json={"key_result_ids": [k1["id"], k2["id"]], "owner_id": str(sina)})
    assert r.json() == {"changed": 2, "unchanged": 0}
    assert c.get(f"{API}/key-results/{k2['id']}", headers=boss).json()["definition"]["owner"] == "سینا رضایی"
    mine = c.get(f"{API}/me/key-results", headers=h(env, "سینا رضایی")).json()
    assert {"یک", "دو"} <= {k["title"] for b in mine for k in b["key_results"]}
    # KRs of another unit make the whole request fail
    with factory() as db:
        other = db.scalars(select(KeyResult.id).join(Objective, Objective.id == KeyResult.objective_id)
                           .where(Objective.unit_id == uid(env, "تدارکات"))).first()
    r = c.post(f"{API}/units/{it}/key-results/owner", headers=boss,
               json={"key_result_ids": [k1["id"], str(other)], "owner_id": str(ali)})
    assert r.status_code == 422
    # a unit expert cannot reassign
    assert c.post(f"{API}/units/{it}/key-results/owner", headers=h(env, "سینا رضایی"),
                  json={"key_result_ids": [k1["id"]], "owner_id": str(ali)}).status_code == 403


def _owner_book() -> bytes:
    import io

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "IT"
    ws.append(["Objective 1", "پشتیبانی بهتر", "توضیحات", "خط مبنا", "هدف", "هدف کسب و کاری", "تیم‌های همکار",
               "شرح انتظار", "مسئول", "R1"])
    ws.append(["KR 1.1", "تیکت‌ها", None, 0, 10, None, None, None, "سینا رضایی", None])
    ws.append(["KR 1.2", "پشتیبان‌گیری", None, 0, 4, None, None, None, "کسی که نیست", None])
    ws.append(["KR 1.3", "مستندسازی", None, 0, 3, None, None, None, None, None])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_excel_owner_column_with_objective_owner_fallback(env):
    from app.services import excel_import as xi
    from app.services import okr as okr_svc
    book = xi.parse_workbook(_owner_book())
    assert [k.owner_text for k in book.sheets[0].objectives[0].krs] == ["سینا رضایی", "کسی که نیست", None]
    with env[1]() as db:
        admin = db.scalars(select(User.id).where(User.full_name == "مهدی ایزدی")).one()
        names = dict(db.execute(select(User.id, User.full_name)).all())
        rep = xi.apply_import(db, book, actor_id=admin, file_name="owners.xlsx",
                              mapping={"IT": xi.SheetChoice("existing", uid(env, "فناوری اطلاعات"))})
        obj = db.scalars(select(Objective).where(Objective.unit_id == uid(env, "فناوری اطلاعات"))
                         .order_by(Objective.number.desc())).first()
        krs = db.scalars(select(KeyResult).where(KeyResult.objective_id == obj.id).order_by(KeyResult.number)).all()
        owners = [names.get(okr_svc.current_kr_version(db, k.id).owner_id) for k in krs]
        assert names[okr_svc.current_objective_version(db, obj.id).owner_id] == "علی کریمی"  # the unit manager
        assert owners == ["سینا رضایی", "علی کریمی", "علی کریمی"]
        assert any("کسی که نیست" in i.message for s in rep.sheets for i in s.issues)
        db.rollback()
