from sqlalchemy import text

from app.core import audit
from app.models import Unit

API = "/api/v1"


def unit_id(db, name):
    return db.query(Unit).filter(Unit.name == name).one().id


def it_sessions(client, h, db):
    rows = client.get(f"{API}/units/{unit_id(db, 'فناوری اطلاعات')}/sessions", headers=h).json()
    return {r["time_point"]: r for r in rows}


def test_requires_login(client):
    assert client.get(f"{API}/dashboard/overview").status_code == 401


def test_bad_password_and_lockout(client, db):
    from tests.conftest import _username
    u = _username("سینا رضایی")
    for _ in range(5):
        assert client.post(f"{API}/auth/login", json={"username": u, "password": "x"}).status_code == 401
    assert client.post(f"{API}/auth/login", json={"username": u, "password": "demo1234"}).status_code == 423
    db.execute(text("update user_account set locked_until=null, failed_logins=0"))
    db.commit()


def test_refresh_rotation_and_reuse_detection(client):
    from tests.conftest import _username
    t = client.post(f"{API}/auth/login", json={"username": _username("مهدی ایزدی"), "password": "demo1234"}).json()
    t2 = client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert t2.status_code == 200
    # replaying the old token revokes the whole family, including the new token
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": t2.json()["refresh_token"]}).status_code == 401


def test_overview_scopes_by_role(client, login):
    admin = client.get(f"{API}/dashboard/overview", headers=login("مهدی ایزدی")).json()
    assert len(admin["units"]) == 8
    mgr = client.get(f"{API}/dashboard/overview", headers=login("علی کریمی")).json()
    assert [u["unit_name"] for u in mgr["units"]] == ["فناوری اطلاعات"]


def test_manager_cannot_touch_other_unit(client, login, db):
    h = login("علی کریمی")
    other = unit_id(db, "تدارکات")
    r = client.get(f"{API}/units/{other}/sessions", headers=h)
    assert r.status_code == 403 and "دامنه" in r.json()["detail"]


def test_session_page_and_entry_flow(client, login, db):
    h = login("علی کریمی")
    ss = it_sessions(client, h, db)
    assert ss["R1"]["status"] == "held" and ss["R2"]["status"] == "scheduled"
    page = client.get(f"{API}/sessions/{ss['R2']['id']}", headers=h).json()
    assert page["can_edit_values"] and len(page["objectives"]) == 3
    kr = page["objectives"][0]["key_results"][1]  # CSAT 50 -> 70, R2 = 61
    assert kr["percent"] == 55
    r = client.put(f"{API}/sessions/{ss['R2']['id']}/entries/{kr['id']}", headers=h, json={"value": 70, "note": "ok"})
    assert r.json()["percent"] == 100
    # R3 stays closed until R2 is held
    assert not client.get(f"{API}/sessions/{ss['R3']['id']}", headers=h).json()["can_edit_values"]
    # R1 is frozen
    r1 = client.get(f"{API}/sessions/{ss['R1']['id']}", headers=h).json()
    assert not r1["can_edit_values"]
    k1 = r1["objectives"][0]["key_results"][1]
    assert k1["frozen"] and k1["value"] == 54
    assert client.put(f"{API}/sessions/{ss['R1']['id']}/entries/{k1['id']}", headers=h, json={"value": 1}).status_code == 409


def test_target_change_needs_reason_and_keeps_old_rounds(client, login, db):
    h = login("علی کریمی")
    ss = it_sessions(client, h, db)
    r1 = client.get(f"{API}/sessions/{ss['R1']['id']}", headers=h).json()
    kr = r1["objectives"][0]["key_results"][1]
    before = kr["percent"]
    url = f"{API}/key-results/{kr['id']}"
    assert client.patch(url, headers=h, json={"target": 90}).status_code == 422
    ok = client.patch(url, headers=h, json={"target": 90, "reason": "هدف چالشی‌تر", "session_id": ss["R2"]["id"]})
    assert ok.status_code == 200 and ok.json()["version"] == 2
    detail = client.get(url, headers=h).json()
    assert detail["versions"][0]["context"] == "in_session" and detail["versions"][0]["reason"] == "هدف چالشی‌تر"
    # the frozen percent of R1 is unchanged by the later target change
    again = client.get(f"{API}/sessions/{ss['R1']['id']}", headers=h).json()["objectives"][0]["key_results"][1]
    assert again["percent"] == before and again["target"] == 70
    # optimistic locking
    stale = client.patch(url, headers=h, json={"weight": 2, "expected_version": 1})
    assert stale.status_code == 409


def test_equal_baseline_target_rejected(client, login, db):
    h = login("علی کریمی")
    ss = it_sessions(client, h, db)
    kr = client.get(f"{API}/sessions/{ss['R2']['id']}", headers=h).json()["objectives"][0]["key_results"][0]
    r = client.patch(f"{API}/key-results/{kr['id']}", headers=h, json={"baseline": 100, "target": 100, "reason": "x"})
    assert r.status_code == 422


def test_member_cannot_hold_or_schedule(client, login, db):
    h = login("سینا رضایی")
    ss = it_sessions(client, login("علی کریمی"), db)
    assert client.post(f"{API}/sessions/{ss['R2']['id']}/hold", headers=h, json={}).status_code == 403


def test_simulator_matches_rules(client, login, db):
    admin = login("مهدی ایزدی")
    from app.models import User
    from tests.conftest import _username  # noqa: F401
    sina = db.query(User).filter(User.full_name == "سینا رضایی").one()
    r = client.post(f"{API}/admin/access/simulate", headers=admin, json={
        "user_id": str(sina.id), "action": "delete", "resource": "key_result", "unit_id": str(unit_id(db, "فناوری اطلاعات"))})
    assert r.json()["allowed"] is False and r.json()["rule"] in ("deny", "none")
    r = client.post(f"{API}/admin/access/simulate", headers=admin, json={
        "user_id": str(sina.id), "action": "view", "resource": "review_value", "unit_id": str(unit_id(db, "تدارکات"))})
    assert r.json()["rule"] == "out_of_scope"


def test_audit_chain_detects_tampering(client, login, db):
    assert audit.verify_chain(db) is None
    db.execute(text("update audit_event set action='forged' where seq=(select min(seq)+3 from audit_event)"))
    db.commit()
    body = client.get(f"{API}/admin/audit", headers=login("مهدی ایزدی")).json()
    assert body["chain_broken_at"] is not None


def test_start_session_has_no_score(client, login):
    ov = client.get(f"{API}/dashboard/overview", headers=login("علی کریمی")).json()
    cells = {c["time_point"]: c for c in ov["units"][0]["cells"]}
    assert cells["شروع"]["score"] is None
    assert cells["R1"]["score"] is not None
    assert ov["units"][0]["delta"] is None  # only one scored round so far


def _workbook(resp):
    import io

    from openpyxl import load_workbook
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/vnd.openxmlformats")
    return load_workbook(io.BytesIO(resp.content))


def test_unit_export_layout_and_formulas(client, login, db):
    h = login("علی کریمی")
    wb = _workbook(client.get(f"{API}/units/{unit_id(db, 'فناوری اطلاعات')}/export.xlsx", headers=h))
    ws = wb[wb.sheetnames[0]]
    assert ws.sheet_view.rightToLeft
    header = [c.value for c in ws[3]]
    assert header[:5] == ["ردیف", "نتیجه کلیدی", "هدف کسب‌وکاری", "مبنا", "هدف"] and "R1 · مقدار" in header
    kr = next(r for r in ws.iter_rows(min_row=4) if r[0].value == "2.1")  # restore drill: 0 -> 11, R1 = 2 (no test edits it)
    assert (kr[3].value, kr[4].value) == (0, 11)
    v1, p1 = header.index("R1 · مقدار"), header.index("R1 · درصد")
    assert kr[v1].value == 2 and str(kr[p1].value).startswith("=IF(ISNUMBER(")
    assert ws.max_row > 10


def test_export_keeps_frozen_percent_when_definition_changed(client, login, db):
    h = login("علی کریمی")
    ss = it_sessions(client, h, db)
    kr = client.get(f"{API}/sessions/{ss['R1']['id']}", headers=h).json()["objectives"][0]["key_results"][2]
    client.patch(f"{API}/key-results/{kr['id']}", headers=h, json={"target": 20, "reason": "سخت‌تر"})
    ws = _workbook(client.get(f"{API}/units/{unit_id(db, 'فناوری اطلاعات')}/export.xlsx", headers=h)).worksheets[0]
    header = [c.value for c in ws[3]]
    row = next(r for r in ws.iter_rows(min_row=4) if r[0].value == "1.3")
    cell = row[header.index("R1 · درصد")].value
    assert not str(cell).startswith("=")  # frozen number, not a formula over the new target
    assert abs(cell - kr["percent"] / 100) < 1e-9


def test_org_export_scopes_by_access(client, login):
    admin = _workbook(client.get(f"{API}/export/org.xlsx", headers=login("مهدی ایزدی")))
    assert admin.sheetnames[0] == "خلاصه" and len(admin.sheetnames) == 9
    mgr = _workbook(client.get(f"{API}/export/org.xlsx", headers=login("علی کریمی")))
    assert len(mgr.sheetnames) == 2


def test_export_forbidden_for_other_unit(client, login, db):
    h = login("علی کریمی")
    assert client.get(f"{API}/units/{unit_id(db, 'تدارکات')}/export.xlsx", headers=h).status_code == 403


def test_every_read_endpoint_matches_its_response_model(client, login, db):
    admin = login("مهدی ایزدی")
    ss = it_sessions(client, login("علی کریمی"), db)
    paths = ["/me", "/cycles/current", "/org/tree", "/goals", "/dashboard/overview",
             "/admin/roles", "/admin/users", "/admin/audit", f"/sessions/{ss['R2']['id']}",
             f"/units/{unit_id(db, 'فناوری اطلاعات')}/sessions", f"/units/{unit_id(db, 'فناوری اطلاعات')}/workspace", "/me/units", f"/time-points/{db.query(__import__('app.models', fromlist=['TimePoint']).TimePoint).first().id}/sessions"]
    for p in paths:
        r = client.get(f"{API}{p}", headers=admin)
        assert r.status_code == 200, (p, r.text[:300])
    kr = client.get(f"{API}/sessions/{ss['R2']['id']}", headers=admin).json()["objectives"][0]["key_results"][0]
    assert client.get(f"{API}/key-results/{kr['id']}", headers=admin).status_code == 200
    assert client.post(f"{API}/key-results/{kr['id']}/comments", headers=admin, json={"body": "ok"}).status_code == 201
    mine = client.get(f"{API}/me/key-results", headers=login("سینا رضایی"))
    assert mine.status_code == 200 and mine.json(), "KR owner sees the KRs assigned in the demo"


def test_committed_openapi_is_up_to_date():
    from app.export_openapi import DEFAULT, render
    assert DEFAULT.exists(), "run: python -m app.export_openapi"
    assert DEFAULT.read_text(encoding="utf-8") == render(), "frontend/openapi.json is stale; run: python -m app.export_openapi"


def test_unit_home_shows_each_kr_progress(client, login, db):
    """Unit home: the open round's percent where a value is recorded, else the last held round's (frozen) percent."""
    h = login("علی کریمی")
    ws = client.get(f"{API}/units/{unit_id(db, 'فناوری اطلاعات')}/workspace", headers=h).json()
    page = lambda sid: {k["id"]: k for o in client.get(f"{API}/sessions/{sid}", headers=h).json()["objectives"]  # noqa: E731
                        for k in o["key_results"]}
    held = [s for s in ws["sessions"] if s["status"] == "held" and s["kind"] != "start"]
    cur_head = next(s for s in ws["sessions"] if s["id"] == ws["current_session_id"])
    cur, last = page(cur_head["id"]), page(held[-1]["id"])
    krs = [k for o in ws["objectives"] for k in o["key_results"]]
    for k in krs:
        if cur[k["id"]]["value"] is not None:
            assert (k["progress"], k["progress_round"], k["progress_live"]) == (cur[k["id"]]["percent"], cur_head["time_point"], True)
        elif last[k["id"]]["percent"] is not None:
            assert (k["progress"], k["progress_round"], k["progress_live"]) == (last[k["id"]]["percent"], held[-1]["time_point"], False)
        else:
            assert k["progress"] is None and k["progress_status"] == "not_recorded"
    assert any(k["progress_live"] for k in krs)


def test_my_krs_carry_round_context_and_previous_value(client, login):
    h = login("سینا رضایی")
    blocks = client.get(f"{API}/me/key-results", headers=h).json()
    krs = [k for b in blocks for k in b["key_results"]]
    assert krs and all(b["unit_name"] for b in blocks)
    for k in krs:
        assert k["editable"] == (k["blocker"] is None)
        assert k["round"] is not None  # the open round the value goes into
    assert any(k["previous_round"] == "R1" and k["previous_value"] is not None for k in krs)


def test_overview_counts_recorded_krs_of_the_open_round(client, login, db):
    h = login("احمد نوری")
    ov = client.get(f"{API}/dashboard/overview", headers=h).json()
    it = next(u for u in ov["units"] if u["unit_name"] == "فناوری اطلاعات")
    page = client.get(f"{API}/sessions/{it['current_session_id']}", headers=h).json()
    krs = [k for o in page["objectives"] for k in o["key_results"]]
    assert it["current_round"] == page["time_point"]
    assert (it["recorded"], it["total_krs"]) == (sum(k["value"] is not None for k in krs), len(krs))


def test_unit_dossier_shows_every_round_and_history(client, login, db):
    it = unit_id(db, "فناوری اطلاعات")
    h = login("احمد نوری")
    d = client.get(f"{API}/units/{it}/dossier", headers=h)
    assert d.status_code == 200, d.text
    d = d.json()
    assert d["unit"]["name"] == "فناوری اطلاعات" and d["unit"]["path"]
    assert {"علی کریمی", "سینا رضایی"} <= {m["full_name"] for m in d["members"]}
    active = d["cycles"][0]
    assert active["status"] == "active" and d["cycle"]["id"] == active["id"]
    assert [r["label"] for r in active["rounds"]][0] == "شروع" and active["rounds"][0]["score"] is None
    # one value column per review round, in order; every KR has a cell for each
    assert d["review_labels"] and "شروع" not in d["review_labels"]
    krs = [k for o in d["objectives"] for k in o["krs"]]
    assert krs and all([v["label"] for v in k["values"]] == d["review_labels"] for k in krs)
    held = next(r for r in active["rounds"] if r["status"] == "held" and r["kind"] != "start")
    assert any(v["value"] is not None for k in krs for v in k["values"] if v["label"] == held["label"])
    # the readable history names who did what
    assert d["history_total"] >= len(d["history"]) > 0
    assert all(e["text"] and "؟" not in e["text"] for e in d["history"])
    # a KR owner sees their own unit's dossier, not another unit's
    owner = login("سینا رضایی")
    assert client.get(f"{API}/units/{it}/dossier", headers=owner).status_code == 200
    other = db.query(Unit).filter(Unit.name != "فناوری اطلاعات", Unit.name != "مدیرعامل").first().id
    assert client.get(f"{API}/units/{other}/dossier", headers=owner).status_code == 403


def test_goals_view_groups_krs_by_strategic_goal(client, login, db):
    d = client.get(f"{API}/goals/overview", headers=login("احمد نوری"))
    assert d.status_code == 200, d.text
    d = d.json()
    assert d["cycle"] and d["goals"]
    every = [k for g in d["goals"] + [d["unlinked"]] for u in g["units"] for o in u["objectives"] for k in o["krs"]]
    assert len(every) == len({k["id"] for k in every})  # each KR sits under exactly one goal (or none)
    for g in d["goals"]:
        n = sum(len(o["krs"]) for u in g["units"] for o in u["objectives"])
        assert n == g["krs"] and g["recorded"] <= g["krs"]
        if g["recorded"]:
            assert 0 <= g["progress"] <= 100
    # a KR owner only sees the units they may see
    mine = client.get(f"{API}/goals/overview", headers=login("سینا رضایی")).json()
    names = {u["unit_name"] for g in mine["goals"] + [mine["unlinked"]] for u in g["units"]}
    assert names <= {"فناوری اطلاعات"}
