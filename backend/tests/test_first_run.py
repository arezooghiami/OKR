"""First-run flow on an EMPTY database: nothing but the bootstrap admin, everything else entered through the admin APIs,
then exercised with every standard role."""

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app import bootstrap
from app.core.db import Base, get_db
from app.main import app

API = "/api/v1"
PWD = "Passw0rd-test"


@pytest.fixture(scope="module")
def c():
    with psycopg.connect("postgresql://okr:okr_dev_password@localhost:5433/okr", autocommit=True) as conn:
        if not conn.execute("select 1 from pg_database where datname='okr_test_empty'").fetchone():
            conn.execute("create database okr_test_empty")
    eng = create_engine("postgresql+psycopg://okr:okr_dev_password@localhost:5433/okr_test_empty")
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


@pytest.fixture(scope="module")
def world(c):
    """Units, cycle and users with every role, created exactly as the admin pages would."""
    a = hdr(c, "admin")
    roles = {r["name"]: r["id"] for r in c.get(f"{API}/admin/roles", headers=a).json()["roles"]}
    types = {t["name"]: t["id"] for t in c.get(f"{API}/admin/unit-types", headers=a).json()}

    def mk(name, parent=None, t="مدیریت"):
        r = c.post(f"{API}/admin/units", headers=a, json={"name": name, "type_id": types[t], "parent_id": parent})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    root = mk("شرکت", None, "معاونت")
    tech, fin = mk("فنی", root), mk("مالی", root)
    cyc = c.post(f"{API}/admin/cycles", headers=a, json={
        "name": "چرخه آزمایشی", "starts_on": "2026-01-01", "ends_on": "2026-06-30",
        "time_points": [{"kind": "start", "label": "شروع"}, {"kind": "review", "label": "R1"},
                        {"kind": "review", "label": "R2"}, {"kind": "final", "label": "نهایی"}]})
    assert cyc.status_code == 201, cyc.text
    assert c.patch(f"{API}/admin/cycles/{cyc.json()['id']}", headers=a, json={"status": "active"}).status_code == 200

    def user(name, role, unit):
        r = c.post(f"{API}/admin/users", headers=a, json={"username": name, "full_name": name, "password": PWD})
        assert r.status_code == 201, r.text
        m = c.post(f"{API}/admin/users/{r.json()['id']}/memberships", headers=a, json={"role_id": roles[role], "unit_id": unit})
        assert m.status_code == 201, m.text
        return r.json()["id"]

    ids = {"mgr_tech": user("mgr_tech", "مدیر واحد", tech), "mgr_fin": user("mgr_fin", "مدیر واحد", fin),
           "member": user("member", "مسئول KR", tech), "viewer": user("viewer", "ناظر", None)}
    return {"a": a, "root": root, "tech": tech, "fin": fin, "cycle": cyc.json()["id"], "ids": ids, "roles": roles}


def test_empty_system_has_no_cycle_and_a_clean_start(c):
    a = hdr(c, "admin")
    assert c.get(f"{API}/cycles/current", headers=a).status_code == 404
    assert c.get(f"{API}/admin/units", headers=a).json() == []
    assert c.get(f"{API}/admin/cycles", headers=a).json() == []
    st = c.get(f"{API}/admin/setup", headers=a).json()
    assert st["units_total"] == 0 and st["users_total"] == 0 and st["active_cycle"] is None and st["goals_total"] == 0


def test_cycle_structure_and_sessions(c, world):
    a = world["a"]
    cyc = c.get(f"{API}/admin/cycles", headers=a).json()[0]
    assert [t["label"] for t in cyc["time_points"]] == ["شروع", "R1", "R2", "نهایی"]
    assert cyc["sessions_total"] == 12 and cyc["sessions_unscheduled"] == 12  # 4 time points x 3 units
    # a new review lands before the final session; sessions follow automatically
    r = c.post(f"{API}/admin/cycles/{world['cycle']}/time-points", headers=a, json={"kind": "review", "label": "R3"}).json()
    assert [t["label"] for t in r["time_points"]] == ["شروع", "R1", "R2", "R3", "نهایی"]
    assert [t["ordinal"] for t in r["time_points"]] == [0, 1, 2, 3, 4] and r["sessions_total"] == 15
    r3 = next(t for t in r["time_points"] if t["label"] == "R3")
    gone = c.delete(f"{API}/admin/time-points/{r3['id']}", headers=a).json()
    assert [t["label"] for t in gone["time_points"]] == ["شروع", "R1", "R2", "نهایی"] and gone["sessions_total"] == 12
    # a unit added later gets its sessions for the open cycle
    c.post(f"{API}/admin/units", headers=a, json={"name": "منابع انسانی", "parent_id": world["root"]})
    assert c.get(f"{API}/admin/cycles", headers=a).json()[0]["sessions_total"] == 16


def test_setup_checklist_tracks_what_is_missing(c, world):
    a = world["a"]
    st = c.get(f"{API}/admin/setup", headers=a).json()
    assert st["units_total"] == 4 and st["users_total"] == 4 and st["users_without_role"] == 0
    assert {u["name"] for u in st["units_without_members"]} == {"شرکت", "منابع انسانی"}
    assert st["active_cycle"]["name"] == "چرخه آزمایشی" and st["active_cycle"]["time_points"] == 4
    assert st["current_round"] == "شروع" and st["units_scheduled"] == 0 and len(st["units_unscheduled"]) == 4
    assert st["objectives_total"] == 0 and len(st["units_without_objectives"]) == 4
    # scheduling one unit's current session moves it out of the missing list
    hr = next(u for u in st["units_unscheduled"] if u["name"] == "منابع انسانی")  # no other test uses this unit
    r = c.put(f"{API}/sessions/{hr['session_id']}", headers=a,
              json={"scheduled_at": "2026-01-05T07:30:00Z", "place": "اتاق شورا", "expected_version": 1})
    assert r.status_code == 200, r.text
    st = c.get(f"{API}/admin/setup", headers=a).json()
    assert st["units_scheduled"] == 1 and hr["id"] not in {u["id"] for u in st["units_unscheduled"]}
    # only the system administrator sees it
    assert c.get(f"{API}/admin/setup", headers=hdr(c, "mgr_tech")).status_code == 403


def test_validation_and_guards(c, world):
    a = world["a"]
    assert c.post(f"{API}/admin/users", headers=a, json={"username": "mgr_tech", "full_name": "x", "password": PWD}).status_code == 409
    assert c.post(f"{API}/admin/users", headers=a, json={"username": "newbie", "full_name": "x", "password": "short"}).status_code == 422
    assert c.post(f"{API}/admin/users", headers=a, json={"username": "bad name", "full_name": "x", "password": PWD}).status_code == 422
    me = next(u for u in c.get(f"{API}/admin/users", headers=a).json() if u["username"] == "admin")
    assert c.patch(f"{API}/admin/users/{me['id']}", headers=a, json={"is_active": False}).status_code == 409
    # cannot move a unit under its own child, cannot archive a unit that still has children
    assert c.patch(f"{API}/admin/units/{world['root']}", headers=a, json={"move": True, "parent_id": world["tech"]}).status_code == 422
    assert c.patch(f"{API}/admin/units/{world['root']}", headers=a, json={"archived": True}).status_code == 409
    assert c.post(f"{API}/admin/cycles", headers=a, json={"name": "x", "starts_on": "2026-02-01", "ends_on": "2026-01-01"}).status_code == 422
    two_starts = c.post(f"{API}/admin/cycles/{world['cycle']}/time-points", headers=a, json={"kind": "start", "label": "شروع ۲"})
    assert two_starts.status_code == 422
    c2 = c.post(f"{API}/admin/cycles", headers=a, json={"name": "دوم", "starts_on": "2026-07-01", "ends_on": "2026-12-30",
                                                        "time_points": [{"kind": "start", "label": "شروع"}]}).json()
    assert c.patch(f"{API}/admin/cycles/{c2['id']}", headers=a, json={"status": "active"}).status_code == 409  # one active cycle


def test_every_role_end_to_end(c, world):
    a, tech, fin, ids = world["a"], world["tech"], world["fin"], world["ids"]
    mt, mf, mem, view = hdr(c, "mgr_tech"), hdr(c, "mgr_fin"), hdr(c, "member"), hdr(c, "viewer")

    # --- unit manager: defines objectives and KRs in own unit only
    o = c.post(f"{API}/units/{tech}/objectives", headers=mt, json={"title": "هدف فنی"})
    assert o.status_code == 201, o.text
    assert c.post(f"{API}/units/{fin}/objectives", headers=mt, json={"title": "نباید"}).status_code == 403
    members = {m["full_name"] for m in c.get(f"{API}/units/{tech}/members", headers=mt).json()}
    assert members == {"member", "mgr_tech"}
    kr = c.post(f"{API}/objectives/{o.json()['id']}/key-results", headers=mt, json={
        "title": "KR یک", "baseline": 0, "target": 10, "owner_id": ids["member"]})
    assert kr.status_code == 201, kr.text

    # --- unit manager home: cycle, own sessions, objectives with owners and start-session readiness
    assert [u["name"] for u in c.get(f"{API}/me/units", headers=mt).json()] == ["فنی"]
    ws = c.get(f"{API}/units/{tech}/workspace", headers=mt).json()
    assert ws["can_define"] and ws["cycle"]["name"] == "چرخه آزمایشی" and not ws["start_held"]
    assert [s["time_point"] for s in ws["sessions"]] == ["شروع", "R1", "R2", "نهایی"]
    ready = {r["key"]: r["done"] for r in ws["readiness"]}
    assert ready == {"objectives": True, "objective_owner": False, "krs": True, "kr_owner": True, "scheduled": False}
    assert ws["objectives"][0]["key_results"][0]["owner_name"] == "member"
    assert c.patch(f"{API}/objectives/{o.json()['id']}", headers=mt, json={"owner_id": ids["mgr_tech"]}).status_code == 200
    ws = c.get(f"{API}/units/{tech}/workspace", headers=mt).json()
    assert ws["objectives"][0]["owner_name"] == "mgr_tech" and ws["readiness"][1]["done"]
    assert c.get(f"{API}/units/{fin}/workspace", headers=mt).status_code == 403

    # --- sessions: only admin / the unit's manager schedule or hold them
    listed = c.get(f"{API}/units/{tech}/sessions", headers=mt).json()
    assert [s["time_point"] for s in listed] == ["شروع", "R1", "R2", "نهایی"]  # only the active cycle, even with a second draft cycle
    sessions = {s["time_point"]: s for s in listed}
    assert c.put(f"{API}/sessions/{sessions['شروع']['id']}", headers=mem,
                 json={"scheduled_at": "2026-01-10T10:00:00+03:30"}).status_code == 403
    for tp in ("شروع", "R1"):
        r = c.put(f"{API}/sessions/{sessions[tp]['id']}", headers=mt, json={"scheduled_at": "2026-01-10T10:00:00+03:30", "place": "اتاق"})
        assert r.status_code == 200, r.text
    # R1 stays closed until the start session is held; then the KR owner records a value
    r1 = sessions["R1"]["id"]
    kr_id = c.get(f"{API}/sessions/{r1}", headers=mt).json()["objectives"][0]["key_results"][0]["id"]
    assert c.put(f"{API}/sessions/{r1}/entries/{kr_id}", headers=mem, json={"value": 4}).status_code == 409
    assert c.post(f"{API}/sessions/{sessions['شروع']['id']}/hold", headers=mem, json={}).status_code == 403
    assert c.post(f"{API}/sessions/{sessions['شروع']['id']}/hold", headers=mt, json={}).status_code == 403  # admin only
    assert c.post(f"{API}/sessions/{sessions['شروع']['id']}/hold", headers=world["a"], json={}).status_code == 200
    mine = c.get(f"{API}/me/key-results", headers=mem).json()
    assert mine and mine[0]["key_results"][0]["editable"] is True
    ok = c.put(f"{API}/sessions/{r1}/entries/{kr_id}", headers=mem, json={"value": 4})
    assert ok.status_code == 200 and ok.json()["percent"] == 40

    # --- the other unit's manager and the observer
    assert c.get(f"{API}/sessions/{r1}", headers=mf).status_code == 403
    assert c.put(f"{API}/sessions/{r1}/entries/{kr_id}", headers=mf, json={"value": 9}).status_code == 403
    page = c.get(f"{API}/sessions/{r1}", headers=view)
    assert page.status_code == 200 and page.json()["can_edit_values"] is False
    assert c.put(f"{API}/sessions/{r1}/entries/{kr_id}", headers=view, json={"value": 9}).status_code == 403
    assert c.get(f"{API}/admin/users", headers=view).status_code == 403
    ov = c.get(f"{API}/dashboard/overview", headers=view).json()
    assert {u["unit_name"] for u in ov["units"]} >= {"فنی", "مالی"}
    assert {u["unit_name"] for u in c.get(f"{API}/dashboard/overview", headers=mf).json()["units"]} == {"مالی"}

    # --- a held round keeps its sessions
    cycle = next(x for x in c.get(f"{API}/admin/cycles", headers=a).json() if x["id"] == world["cycle"])
    start_tp = next(t for t in cycle["time_points"] if t["label"] == "شروع")
    assert c.delete(f"{API}/admin/time-points/{start_tp['id']}", headers=a).status_code == 409
    # --- role changes take effect at once
    m = next(u for u in c.get(f"{API}/admin/users", headers=a).json() if u["username"] == "mgr_tech")["memberships"][0]
    assert c.delete(f"{API}/admin/memberships/{m['id']}", headers=a).status_code == 200
    assert c.get(f"{API}/units/{tech}/sessions", headers=mt).status_code == 403
    # --- deactivated users are locked out; a reset password replaces the old one
    uid = ids["viewer"]
    assert c.patch(f"{API}/admin/users/{uid}", headers=a, json={"is_active": False}).status_code == 200
    assert c.post(f"{API}/auth/login", json={"username": "viewer", "password": PWD}).status_code == 401
    assert c.patch(f"{API}/admin/users/{uid}", headers=a, json={"is_active": True, "password": "N3w-secret-pass"}).status_code == 200
    assert c.post(f"{API}/auth/login", json={"username": "viewer", "password": PWD}).status_code == 401
    assert c.post(f"{API}/auth/login", json={"username": "viewer", "password": "N3w-secret-pass"}).status_code == 200


def test_new_role_copy_and_audit_has_no_secrets(c, world):
    a = world["a"]
    r = c.post(f"{API}/admin/roles", headers=a, json={"name": "هماهنگ‌کننده", "copy_from_id": world["roles"]["ناظر"]})
    assert r.status_code == 201 and r.json()["permissions"]["report"]["view"] == "allow"
    assert c.post(f"{API}/admin/roles", headers=a, json={"name": "هماهنگ‌کننده"}).status_code == 409
    log = c.get(f"{API}/admin/audit?limit=500", headers=a).json()
    assert log["chain_broken_at"] is None
    assert "Passw0rd" not in str(log) and "N3w-secret" not in str(log)


def test_delete_is_an_archive_that_keeps_history(c, world):
    """«حذف» in the unit table: gone from the lists, still in history and audit; reason required; role-checked."""
    a, tech = world["a"], world["tech"]
    # an earlier test removed mgr_tech's role; give it back
    c.post(f"{API}/admin/users/{world['ids']['mgr_tech']}/memberships", headers=a,
           json={"role_id": world["roles"]["مدیر واحد"], "unit_id": tech})
    mt, mem = hdr(c, "mgr_tech"), hdr(c, "member")
    r = c.post(f"{API}/units/{tech}/objectives", headers=mt, json={"title": "هدف موقت"})
    assert r.status_code == 201, r.text
    o = r.json()["id"]
    kr = c.post(f"{API}/objectives/{o}/key-results", headers=mt, json={"title": "KR موقت", "baseline": 0, "target": 5}).json()["id"]
    k2 = c.post(f"{API}/objectives/{o}/key-results", headers=mt, json={"title": "KR دوم", "baseline": 0, "target": 5}).json()["id"]
    ws = c.get(f"{API}/units/{tech}/workspace", headers=mt).json()
    assert ws["can_edit"] and ws["can_delete"]
    assert not c.get(f"{API}/units/{tech}/workspace", headers=mem).json()["can_delete"]

    assert c.post(f"{API}/key-results/{kr}/archive", headers=mem, json={"reason": "x"}).status_code == 403
    assert c.post(f"{API}/key-results/{kr}/archive", headers=mt, json={"reason": " "}).status_code == 422
    assert c.post(f"{API}/key-results/{kr}/archive", headers=mt, json={"reason": "تکراری بود"}).status_code == 200
    titles = [k["title"] for ob in c.get(f"{API}/units/{tech}/workspace", headers=mt).json()["objectives"] for k in ob["key_results"]]
    assert "KR موقت" not in titles and "KR دوم" in titles
    assert c.get(f"{API}/key-results/{kr}", headers=mt).status_code == 200  # history stays reachable

    assert c.post(f"{API}/objectives/{o}/archive", headers=mt, json={"reason": "ادغام با هدف دیگر"}).status_code == 200
    ws = c.get(f"{API}/units/{tech}/workspace", headers=mt).json()
    assert all(ob["id"] != o for ob in ws["objectives"])
    assert c.post(f"{API}/key-results/{k2}/archive", headers=mt, json={"reason": "x"}).status_code == 404  # went with its objective
    events = c.get(f"{API}/admin/audit", headers=a).json()["events"]
    assert sum(ev["action"] == "archive" for ev in events) >= 2


def test_closed_cycle_stays_visible_but_read_only(c, world):
    """A past cycle: listed, viewable with its data, every write refused; a new active cycle becomes the default."""
    a, tech = world["a"], world["tech"]
    mt = hdr(c, "mgr_tech")
    old = world["cycle"]
    assert c.patch(f"{API}/admin/cycles/{old}", headers=a, json={"status": "closed"}).status_code == 200

    listed = c.get(f"{API}/cycles", headers=mt).json()
    assert [x["status"] for x in listed if x["id"] == old] == ["closed"]
    ws = c.get(f"{API}/units/{tech}/workspace", headers=mt).json()  # no active cycle: falls back to the latest closed one
    assert ws["cycle"]["id"] == old and ws["read_only"] and not (ws["can_define"] or ws["can_edit"] or ws["can_delete"])
    kr = next(k for o in ws["objectives"] for k in o["key_results"])
    obj = ws["objectives"][0]["id"]

    assert c.patch(f"{API}/key-results/{kr['id']}", headers=mt, json={"title": "x"}).status_code == 409
    assert c.post(f"{API}/key-results/{kr['id']}/archive", headers=mt, json={"reason": "x"}).status_code == 409
    assert c.post(f"{API}/objectives/{obj}/key-results", headers=mt, json={"title": "x", "baseline": 0, "target": 1}).status_code == 409
    assert c.patch(f"{API}/objectives/{obj}", headers=mt, json={"title": "x"}).status_code == 409
    assert c.post(f"{API}/key-results/{kr['id']}/comments", headers=mt, json={"body": "x"}).status_code == 409
    r1 = next(s for s in ws["sessions"] if s["time_point"] == "R1")
    assert c.put(f"{API}/sessions/{r1['id']}/entries/{kr['id']}", headers=a, json={"value": 1}).status_code == 409
    page = c.get(f"{API}/sessions/{r1['id']}", headers=mt).json()
    assert not page["can_edit_values"] and not page["can_edit_definitions"] and "بسته" in page["entry_blocker"]
    assert c.get(f"{API}/units/{tech}/export.xlsx?cycle_id={old}", headers=a).status_code == 200

    new = c.post(f"{API}/admin/cycles", headers=a, json={
        "name": "چرخهٔ بعد", "starts_on": "2026-07-01", "ends_on": "2026-12-20",
        "time_points": [{"kind": "start", "label": "شروع"}, {"kind": "review", "label": "R1"}]}).json()["id"]
    assert c.patch(f"{API}/admin/cycles/{new}", headers=a, json={"status": "active"}).status_code == 200
    assert c.get(f"{API}/cycles", headers=mt).json()[0]["id"] == new  # active first
    ws = c.get(f"{API}/units/{tech}/workspace", headers=mt).json()
    assert ws["cycle"]["id"] == new and not ws["read_only"] and ws["can_define"] and ws["objectives"] == []
    past = c.get(f"{API}/units/{tech}/workspace?cycle_id={old}", headers=mt).json()
    assert past["read_only"] and past["objectives"]  # the old cycle's data is still there
