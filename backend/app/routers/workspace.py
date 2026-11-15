"""The unit manager's home: the active cycle, the unit's session timeline, and its objectives/KRs with owners."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import access, require
from app.models import (
    Cycle,
    KeyResult,
    Membership,
    Objective,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitSession,
    User,
)
from app.routers.sessions import cycle_out, session_head
from app.schemas.out import WorkspaceOut, WorkspaceUnitRef
from app.services import okr as svc
from app.services import reviews as rev
from app.services.access import Access

router = APIRouter(tags=["workspace"])


def _cycle(db: Session, cycle_id: uuid.UUID | None) -> Cycle:
    """The requested cycle (active or closed); by default the active one, else the latest closed one."""
    if cycle_id is not None:
        cycle = db.get(Cycle, cycle_id)
        if cycle is None or cycle.status == "draft":
            raise HTTPException(404, "دوره پیدا نشد")
        return cycle
    cycle = db.scalars(select(Cycle).where(Cycle.status == "active")).first() or db.scalars(
        select(Cycle).where(Cycle.status == "closed").order_by(Cycle.starts_on.desc()).limit(1)).first()
    if not cycle:
        raise HTTPException(404, "دورهٔ فعالی وجود ندارد")
    return cycle


@router.get("/me/units", response_model=list[WorkspaceUnitRef])
def my_units(cycle_id: uuid.UUID | None = None, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """Units of a cycle (default: the active one) the user may see objectives of; their own units come first."""
    cycle = _cycle(db, cycle_id)
    in_cycle = set(db.scalars(select(UnitSession.unit_id).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                              .where(TimePoint.cycle_id == cycle.id)))
    visible = acc.visible_units("objective")
    ids = in_cycle if visible is None else in_cycle & visible
    mine = set(db.scalars(select(Membership.unit_id).where(Membership.user_id == acc.user.id)))
    units = [db.get(Unit, i) for i in ids]
    units.sort(key=lambda u: (u.id not in mine, u.name))
    return [{"id": u.id, "name": u.name, "can_define": acc.can("objective", "create", u.id)} for u in units]


def _progress(db: Session, rows) -> dict:
    """Per KR: the open round's percent when a value is recorded there, otherwise the latest held round in which
    this KR has a value (a final session held without new values must not blank out R2)."""
    reviews = [(s, tp) for s, tp in rows if tp.kind != "start"]
    held = [(s, tp) for s, tp in reviews if s.status == "held"]
    current = next(((s, tp) for s, tp in reviews if s.status != "held"), None)
    out: dict = {}
    for pair, live in [*((h, False) for h in held), (current, True)]:
        if pair is None:
            continue
        s, tp = pair
        for block in rev.build_session(db, s):
            for r in block.rows:
                if r.percent is None or r.entry is None or r.entry.value is None:
                    continue
                out[r.kr.id] = {"progress": r.percent, "progress_value": r.entry.value if r.entry else None,
                                "progress_status": r.status.value,
                                "progress_round": tp.label, "progress_live": live}
    return out


@router.get("/units/{unit_id}/workspace", response_model=WorkspaceOut)
def workspace(unit_id: uuid.UUID, cycle_id: uuid.UUID | None = None, db: Session = Depends(get_db),
              acc: Access = Depends(access)):
    require(acc, "objective", "view", unit_id)
    unit = db.get(Unit, unit_id)
    if not unit:
        raise HTTPException(404, "واحد پیدا نشد")
    cycle = _cycle(db, cycle_id)
    writable = cycle.status != "closed"
    rows = db.execute(select(UnitSession, TimePoint).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                      .where(UnitSession.unit_id == unit_id, TimePoint.cycle_id == cycle.id)
                      .order_by(TimePoint.ordinal)).all()
    sessions = [session_head(db, s) for s, _ in rows]
    start = next((s for s, tp in rows if tp.kind == "start"), None)
    current = next((s for s, _ in rows if s.status != "held"), None)

    progress = _progress(db, rows)
    names = dict(db.execute(select(User.id, User.full_name)).all())
    goals = {g.id: g for g in db.scalars(select(StrategicGoal))}
    objectives = []
    for o in db.scalars(select(Objective).where(Objective.cycle_id == cycle.id, Objective.unit_id == unit_id,
                                                Objective.archived_at.is_(None)).order_by(Objective.number)):
        ov = svc.current_objective_version(db, o.id)
        krs = []
        for kr in db.scalars(select(KeyResult).where(KeyResult.objective_id == o.id, KeyResult.archived_at.is_(None))
                             .order_by(KeyResult.number)):
            v = svc.current_kr_version(db, kr.id)
            g = goals.get(v.strategic_goal_id)
            krs.append({"id": kr.id, "code": f"{o.number}.{kr.number}", "title": v.title, "description": v.description,
                        "kind": v.kind, "unit_of_measure": v.unit_of_measure, "baseline": v.baseline, "target": v.target,
                        "owner_id": v.owner_id, "owner_name": names.get(v.owner_id),
                        "goal": {"id": g.id, "title": g.title, "color": g.color_token} if g else None,
                        "definition_version": v.number, "version": kr.version,
                        **progress.get(kr.id, {"progress": None, "progress_value": None, "progress_status": "not_recorded",
                                               "progress_round": None, "progress_live": False})})
        objectives.append({"id": o.id, "number": o.number, "title": ov.title, "description": ov.description,
                           "owner_id": ov.owner_id, "owner_name": names.get(ov.owner_id),
                           "definition_version": ov.number, "key_results": krs})

    all_krs = [k for o in objectives for k in o["key_results"]]
    no_owner_obj = [o for o in objectives if not o["owner_id"]]
    no_kr = [o for o in objectives if not o["key_results"]]
    no_owner_kr = [k for k in all_krs if not k["owner_id"]]
    readiness = [
        {"key": "objectives", "label": "دست‌کم یک هدف تعریف شده", "done": bool(objectives),
         "detail": None if objectives else "هنوز هدفی ثبت نشده"},
        {"key": "objective_owner", "label": "هر هدف مسئول دارد", "done": bool(objectives) and not no_owner_obj,
         "detail": f"{len(no_owner_obj)} هدف بدون مسئول هدف" if no_owner_obj else None},
        {"key": "krs", "label": "هر هدف دست‌کم یک نتیجهٔ کلیدی دارد", "done": bool(objectives) and not no_kr,
         "detail": f"{len(no_kr)} هدف بدون نتیجهٔ کلیدی" if no_kr else None},
        {"key": "kr_owner", "label": "هر نتیجهٔ کلیدی مسئول دارد", "done": bool(all_krs) and not no_owner_kr,
         "detail": f"{len(no_owner_kr)} نتیجهٔ کلیدی بدون مسئول" if no_owner_kr else None},
        {"key": "scheduled", "label": "زمان جلسهٔ شروع تعیین شده",
         "done": start is not None and start.status != "unscheduled",
         "detail": None if start is not None and start.status != "unscheduled" else "مدیر واحد یا مدیر سامانه زمان را می‌گذارد"},
    ]
    return {
        "unit_id": unit.id, "unit_name": unit.name, "manager": unit.manager_name,
        "cycle": cycle_out(db, cycle), "read_only": not writable, "sessions": sessions,
        "current_session_id": current.id if current else (sessions[-1]["id"] if sessions else None),
        "start_session_id": start.id if start else None, "start_held": bool(start and start.status == "held"),
        "can_define": writable and acc.can("objective", "create", unit_id),
        "can_edit": writable and acc.can("key_result", "edit", unit_id),
        "can_delete": writable and acc.can("key_result", "delete", unit_id), "objectives": objectives, "readiness": readiness,
    }
