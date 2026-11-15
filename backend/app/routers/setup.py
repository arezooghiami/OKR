"""The system administrator's setup checklist: units & users → cycle & sessions → strategic goals → unit OKRs."""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import access
from app.core.db import get_db, utcnow
from app.models import (
    Cycle,
    KeyResult,
    KRVersion,
    Membership,
    Objective,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitSession,
    User,
)
from app.routers.admin import _admin
from app.schemas.out import SetupOut
from app.services.access import Access
from app.services.cycles import active_unit_ids

router = APIRouter(prefix="/admin", tags=["admin-setup"])


def _cycle(db: Session, c: Cycle) -> dict:
    n = db.scalar(select(func.count()).select_from(TimePoint).where(TimePoint.cycle_id == c.id)) or 0
    return {"id": c.id, "name": c.name, "status": c.status, "starts_on": c.starts_on, "ends_on": c.ends_on, "time_points": n}


@router.get("/setup", response_model=SetupOut)
def setup(db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    now = utcnow()
    unit_ids = active_unit_ids(db)
    names = {u.id: u.name for u in db.scalars(select(Unit).where(Unit.id.in_(unit_ids)))} if unit_ids else {}
    order = sorted(unit_ids, key=lambda i: names.get(i, ""))

    live = or_(Membership.valid_to.is_(None), Membership.valid_to > now)
    staffed = set(db.scalars(select(Membership.unit_id).where(live, Membership.unit_id.is_not(None))))
    users = db.scalars(select(User).where(User.is_active, User.is_system_admin.is_(False))).all()
    with_role = set(db.scalars(select(Membership.user_id).where(live)))

    active = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
    drafts = db.scalars(select(Cycle).where(Cycle.status == "draft").order_by(Cycle.starts_on)).all()
    closed = db.scalar(select(func.count()).select_from(Cycle).where(Cycle.status == "closed")) or 0

    out = {
        "units_total": len(unit_ids),
        "units_without_members": [{"id": i, "name": names[i]} for i in order if i not in staffed],
        "users_total": len(users),
        "users_without_role": sum(1 for u in users if u.id not in with_role),
        "active_cycle": _cycle(db, active) if active else None,
        "draft_cycles": [_cycle(db, c) for c in drafts],
        "closed_cycles": closed,
        "current_round": None, "units_scheduled": 0, "units_unscheduled": [],
        "goals_total": db.scalar(select(func.count()).select_from(StrategicGoal).where(StrategicGoal.active)) or 0,
        "krs_total": 0, "krs_with_goal": 0, "objectives_total": 0, "units_without_objectives": [],
    }
    if active is None:
        return out

    # sessions: each unit's current round = its first session that has not been held
    tps = db.scalars(select(TimePoint).where(TimePoint.cycle_id == active.id).order_by(TimePoint.ordinal)).all()
    rank = {tp.id: i for i, tp in enumerate(tps)}
    label = {tp.id: tp.label for tp in tps}
    by_unit: dict = {}
    for s in db.scalars(select(UnitSession).where(UnitSession.time_point_id.in_(rank))):
        by_unit.setdefault(s.unit_id, []).append(s)
    rounds = Counter()
    for uid in order:
        current = next((s for s in sorted(by_unit.get(uid, []), key=lambda s: rank[s.time_point_id]) if s.status != "held"), None)
        if current is None:
            continue  # every session held: nothing left to schedule
        rounds[label[current.time_point_id]] += 1
        if current.status == "unscheduled":
            out["units_unscheduled"].append({"id": uid, "name": names[uid], "session_id": current.id})
        else:
            out["units_scheduled"] += 1
    out["current_round"] = rounds.most_common(1)[0][0] if rounds else None

    # unit OKRs and their link to strategic goals (current definition of every live KR)
    objs = db.scalars(select(Objective).where(Objective.cycle_id == active.id, Objective.archived_at.is_(None))).all()
    out["objectives_total"] = len(objs)
    with_obj = {o.unit_id for o in objs}
    out["units_without_objectives"] = [{"id": i, "name": names[i]} for i in order if i not in with_obj]
    goals = db.execute(
        select(KRVersion.strategic_goal_id)
        .join(KeyResult, (KeyResult.id == KRVersion.key_result_id) & (KeyResult.version == KRVersion.number))
        .join(Objective, Objective.id == KeyResult.objective_id)
        .where(Objective.cycle_id == active.id, Objective.archived_at.is_(None), KeyResult.archived_at.is_(None))
    ).scalars().all()
    out["krs_total"] = len(goals)
    out["krs_with_goal"] = sum(1 for g in goals if g is not None)
    return out
