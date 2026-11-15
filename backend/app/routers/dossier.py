"""Unit dossier: everything about one unit in one place — who works there, how every cycle went, the value of every
KR in every round of a cycle (including deleted ones), its sessions and the readable history of every change."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import access, require
from app.models import (
    AuditEvent,
    Cycle,
    KeyResult,
    KRVersion,
    Membership,
    Objective,
    ReviewEntry,
    Role,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitSession,
    UnitType,
    User,
)
from app.schemas.out import DossierOut
from app.services import okr as svc
from app.services import reviews as rev
from app.services.access import Access
from app.services.calc import percent, status_for
from app.services.orgtree import load_tree

router = APIRouter(tags=["dossier"])
HISTORY_LIMIT = 150

FIELD = {"title": "عنوان", "baseline": "مبنا", "target": "هدف", "owner_id": "مسئول", "strategic_goal_id": "هدف کلان",
         "weight": "وزن", "kind": "نوع", "unit_of_measure": "واحد اندازه‌گیری", "description": "توضیح",
         "expectation": "شرح انتظار", "range_min": "حداقل بازه", "range_max": "حداکثر بازه"}
SHOW_VALUE = {"title", "baseline", "target", "weight", "unit_of_measure"}


def _num(v) -> str:
    if v is None or v == "":
        return "—"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v)


def _rounds(db: Session, unit_id: uuid.UUID, cycle: Cycle) -> tuple[list[dict], float | None, int, int]:
    rows = db.execute(select(UnitSession, TimePoint).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                      .where(TimePoint.cycle_id == cycle.id, UnitSession.unit_id == unit_id)
                      .order_by(TimePoint.ordinal)).all()
    out, current_seen = [], False
    for s, tp in rows:
        is_current = s.status != "held" and not current_seen
        current_seen = current_seen or is_current
        score, recorded, total = None, 0, 0
        if tp.kind != "start" and (s.status == "held" or is_current):
            blocks = rev.build_session(db, s)
            krs = [r for b in blocks for r in b.rows]
            total, recorded = len(krs), sum(1 for r in krs if r.entry is not None and r.entry.value is not None)
            # a round with no recorded value has no score (a final session held without values is not 0%)
            score = rev.unit_score(blocks) if recorded and s.status in ("held", "scheduled") else None
        out.append({"label": tp.label, "kind": tp.kind, "status": s.status, "session_id": s.id,
                    "scheduled_at": s.scheduled_at, "held_at": s.held_at, "place": s.place,
                    "score": score, "recorded": recorded, "total": total})
    held = [r["score"] for r in out if r["status"] == "held" and r["score"] is not None]
    objs = db.scalars(select(Objective.id).where(Objective.cycle_id == cycle.id, Objective.unit_id == unit_id,
                                                 Objective.archived_at.is_(None))).all()
    krs = db.scalar(select(func.count()).select_from(KeyResult).where(KeyResult.objective_id.in_(objs),
                                                                      KeyResult.archived_at.is_(None))) if objs else 0
    return out, (held[-1] if held else None), len(objs), krs or 0


@router.get("/units/{unit_id}/dossier", response_model=DossierOut)
def dossier(unit_id: uuid.UUID, cycle_id: uuid.UUID | None = None, db: Session = Depends(get_db),
            acc: Access = Depends(access)):
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(404, "واحد پیدا نشد")
    require(acc, "objective", "view", unit_id)

    tree = load_tree(db)
    path, cur = [], tree.parents.get(unit_id)
    while cur is not None and len(path) < 30:
        p = db.get(Unit, cur)
        path.insert(0, p.name)
        cur = tree.parents.get(cur)
    ut = db.get(UnitType, unit.type_id) if unit.type_id else None
    members = db.execute(select(User, Role).join(Membership, Membership.user_id == User.id)
                         .join(Role, Role.id == Membership.role_id)
                         .where(Membership.unit_id == unit_id, User.is_active).order_by(User.full_name)).all()

    # every visible cycle with this unit's rounds; newest first, the active one on top
    cycles = db.scalars(select(Cycle).where(Cycle.status.in_(("active", "closed")))).all()
    cycles = sorted(cycles, key=lambda c: (c.status != "active", -c.starts_on.toordinal()))
    cycle_rows = []
    for c in cycles:
        rounds, score, n_obj, n_kr = _rounds(db, unit_id, c)
        if not rounds and not n_obj:
            continue  # the unit did not exist in that cycle
        cycle_rows.append({"id": c.id, "name": c.name, "status": c.status, "starts_on": c.starts_on, "ends_on": c.ends_on,
                           "objectives": n_obj, "krs": n_kr, "score": score, "rounds": rounds})

    sel = None
    if cycle_id is not None:
        sel = next((c for c in cycles if c.id == cycle_id), None)
        if sel is None:
            raise HTTPException(404, "دوره پیدا نشد")
    elif cycle_rows:
        sel = next(c for c in cycles if c.id == cycle_rows[0]["id"])

    out = {
        "unit": {"id": unit.id, "name": unit.name, "code": unit.code, "type": ut.name if ut else None,
                 "manager_name": unit.manager_name, "path": path, "archived": unit.archived},
        "members": [{"full_name": u.full_name, "username": u.username, "role": r.name} for u, r in members],
        "cycles": cycle_rows, "cycle": {"id": sel.id, "name": sel.name} if sel else None,
        "cycle_status": sel.status if sel else None, "review_labels": [], "objectives": [], "history": [], "history_total": 0,
    }
    if sel is None:
        return out

    # the KR matrix: every objective and KR of the cycle (deleted ones too), every review round's value
    sessions = db.execute(select(UnitSession, TimePoint).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                          .where(TimePoint.cycle_id == sel.id, UnitSession.unit_id == unit_id)
                          .order_by(TimePoint.ordinal)).all()
    reviews = [(s, tp) for s, tp in sessions if tp.kind != "start"]
    out["review_labels"] = [tp.label for _, tp in reviews]
    objectives = db.scalars(select(Objective).where(Objective.cycle_id == sel.id, Objective.unit_id == unit_id)
                            .order_by(Objective.archived_at.is_not(None), Objective.number)).all()
    krs_by_obj = {o.id: db.scalars(select(KeyResult).where(KeyResult.objective_id == o.id)
                                   .order_by(KeyResult.archived_at.is_not(None), KeyResult.number)).all() for o in objectives}
    all_krs = [k for ks in krs_by_obj.values() for k in ks]
    entries = {(e.key_result_id, e.session_id): e for e in db.scalars(
        select(ReviewEntry).where(ReviewEntry.session_id.in_([s.id for s, _ in reviews]))
    )} if reviews else {}
    users = {u.id: u.full_name for u in db.scalars(select(User))}
    goals = {g.id: g.title for g in db.scalars(select(StrategicGoal))}
    versions = dict(db.execute(select(KRVersion.key_result_id, func.count()).where(
        KRVersion.key_result_id.in_([k.id for k in all_krs])).group_by(KRVersion.key_result_id)).all()) if all_krs else {}

    obj_titles, kr_label = {}, {}
    for o in objectives:
        ov = svc.current_objective_version(db, o.id)
        obj_titles[o.id] = (o.number, ov.title)
        rows = []
        for k in krs_by_obj[o.id]:
            v = svc.current_kr_version(db, k.id)
            kr_label[k.id] = (f"{o.number}.{k.number}", v.title)
            values = []
            for s, tp in reviews:
                e = entries.get((k.id, s.id))
                val = e.value if e else None
                pct = e.frozen_percent if e and e.is_frozen and e.frozen_percent is not None else (
                    percent(svc.definition_of(v), val) if val is not None else None)
                values.append({"label": tp.label, "value": val, "percent": pct, "note": e.note if e else None})
            latest = next((x["percent"] for x in reversed(values) if x["percent"] is not None), None)
            rows.append({"id": k.id, "code": f"{o.number}.{k.number}", "title": v.title, "kind": v.kind,
                         "unit_of_measure": v.unit_of_measure, "baseline": v.baseline, "target": v.target,
                         "owner": users.get(v.owner_id), "goal": goals.get(v.strategic_goal_id),
                         "archived": k.archived_at is not None, "archive_reason": k.archive_reason,
                         "versions": versions.get(k.id, 1), "values": values, "latest_percent": latest,
                         "latest_status": status_for(latest).value})
        out["objectives"].append({"id": o.id, "number": o.number, "title": ov.title, "archived": o.archived_at is not None,
                                  "archive_reason": o.archive_reason, "krs": rows})

    # readable history of this cycle (plus changes to the unit itself)
    labels = {s.id: tp.label for s, tp in sessions}
    ids = [str(unit_id), *(str(o.id) for o in objectives), *(str(k.id) for k in all_krs), *(str(s.id) for s, _ in sessions)]
    q = select(AuditEvent).where(AuditEvent.resource_id.in_(ids))
    out["history_total"] = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    for ev in db.scalars(q.order_by(AuditEvent.seq.desc()).limit(HISTORY_LIMIT)):
        kind, text = _describe(ev, obj_titles, kr_label, labels, users, goals)
        out["history"].append({"at": ev.at, "actor": users.get(ev.actor_id), "kind": kind, "text": text})
    return out


def _describe(ev: AuditEvent, objs: dict, krs: dict, labels: dict, users: dict, goals: dict) -> tuple[str, str]:
    a, b = ev.after or {}, ev.before or {}
    rid = uuid.UUID(ev.resource_id) if ev.resource_id else None
    excel = " (از اکسل)" if a.get("source") == "excel" else ""
    if ev.resource == "objective":
        n, t = objs.get(rid, (None, "؟"))
        if ev.action == "create":
            return "create", f"هدف {n} «{t}» تعریف شد{excel}"
        if ev.action == "archive":
            return "archive", f"هدف {n} «{t}» حذف شد. دلیل: {a.get('reason') or '—'}"
        if ev.action in ("align", "unalign"):
            return "align", f"همترازی هدف {n} {'تعیین' if ev.action == 'align' else 'برداشته'} شد"
        return "update", f"هدف {n} ویرایش شد: {_changes(b, a, users, goals)}"
    if ev.resource == "key_result":
        code, t = krs.get(rid, ("؟", "؟"))
        if ev.action == "create":
            return "create", f"KR {code} «{t}» تعریف شد{excel}"
        if ev.action == "archive":
            return "archive", f"KR {code} «{t}» حذف شد. دلیل: {a.get('reason') or '—'}"
        reason = f" — دلیل: {a['reason']}" if isinstance(a.get("reason"), str) and a.get("reason") else ""
        return "update", f"KR {code} ویرایش شد: {_changes(b, a, users, goals)}{reason}"
    if ev.resource == "review_entry":
        code, _ = krs.get(rid, ("؟", "؟"))
        sid = a.get("session")
        lab = labels.get(uuid.UUID(sid)) if sid else None
        old = f" (قبلاً {_num(b.get('value'))})" if b.get("value") is not None and b.get("value") != a.get("value") else ""
        note = f" · یادداشت: {a['note']}" if a.get("note") else ""
        return "value", f"مقدار KR {code}{' در ' + lab if lab else ''}: {_num(a.get('value'))}{old}{note}{excel}"
    if ev.resource == "unit_session":
        lab = labels.get(rid, "")
        if ev.action.startswith("hold"):
            return "session", f"جلسهٔ {lab} برگزار شد{' (ثبت با تاریخ گذشته)' if ev.action == 'hold_backdated' else ''}"
        return "session", f"زمان جلسهٔ {lab} تعیین شد{(' · ' + a['place']) if a.get('place') else ''}"
    if ev.resource == "unit":
        if ev.action == "create":
            return "unit", f"واحد ساخته شد{excel}"
        if a.get("changes"):
            return "unit", "مشخصات واحد تغییر کرد: " + "، ".join(a["changes"])
        return "unit", "مشخصات واحد تغییر کرد"
    return "update", f"{ev.resource} · {ev.action}"


def _changes(before: dict, after: dict, users: dict, goals: dict) -> str:
    parts = []
    for f, new in after.items():
        if f in ("reason", "source", "session"):
            continue
        label = FIELD.get(f, f)
        if f in SHOW_VALUE:
            parts.append(f"{label} از {_num(before.get(f))} به {_num(new)}")
        elif f == "owner_id":
            parts.append(f"{label}: {users.get(_uuid(new), '—')}")
        elif f == "strategic_goal_id":
            parts.append(f"{label}: {goals.get(_uuid(new), '—')}")
        else:
            parts.append(label)
    return "، ".join(parts) or "بدون تغییر قابل نمایش"


def _uuid(v):
    try:
        return uuid.UUID(str(v)) if v else None
    except ValueError:
        return None
