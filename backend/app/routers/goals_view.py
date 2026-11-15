"""Strategic goals view: for each strategic goal, which units, objectives and KRs push it forward and how far they
are — and what is linked to no goal at all. The link is the KR's «هدف کلان», set in the unit table."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import access
from app.models import KeyResult, Objective, StrategicGoal, TimePoint, Unit, UnitSession, User
from app.routers.workspace import _cycle, _progress
from app.schemas.out import GoalsViewOut
from app.services import okr as svc
from app.services.access import Access
from app.services.calc import status_for

router = APIRouter(tags=["goals"])


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


@router.get("/goals/overview", response_model=GoalsViewOut)
def goals_overview(cycle_id: uuid.UUID | None = None, db: Session = Depends(get_db), acc: Access = Depends(access)):
    try:
        cycle = _cycle(db, cycle_id)
    except HTTPException:  # no cycle yet: show the goals with nothing linked
        cycle = None
    goals = db.scalars(select(StrategicGoal).where(StrategicGoal.active).order_by(StrategicGoal.sort, StrategicGoal.title)).all()
    blocks: dict = {g.id: {"id": g.id, "title": g.title, "color": g.color_token, "rows": []} for g in goals}
    unlinked = {"id": None, "title": "بدون هدف کلان", "color": None, "rows": []}
    if cycle is not None:
        visible = acc.visible_units("objective")
        users = {u.id: u.full_name for u in db.scalars(select(User))}
        objectives = db.scalars(select(Objective).where(Objective.cycle_id == cycle.id, Objective.archived_at.is_(None))
                                .order_by(Objective.number)).all()
        by_unit: dict = {}
        for o in objectives:
            if visible is None or o.unit_id in visible:
                by_unit.setdefault(o.unit_id, []).append(o)
        for unit_id, objs in by_unit.items():
            rows = db.execute(select(UnitSession, TimePoint).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                              .where(UnitSession.unit_id == unit_id, TimePoint.cycle_id == cycle.id)
                              .order_by(TimePoint.ordinal)).all()
            prog = _progress(db, rows)
            unit_name = db.get(Unit, unit_id).name
            for o in objs:
                title = svc.current_objective_version(db, o.id).title
                for k in db.scalars(select(KeyResult).where(KeyResult.objective_id == o.id, KeyResult.archived_at.is_(None))
                                    .order_by(KeyResult.number)):
                    v = svc.current_kr_version(db, k.id)
                    p = prog.get(k.id, {})
                    kr = {"id": k.id, "code": f"{o.number}.{k.number}", "title": v.title, "owner": users.get(v.owner_id),
                          "progress": p.get("progress"), "status": status_for(p.get("progress")).value, "round": p.get("progress_round")}
                    target = blocks.get(v.strategic_goal_id, unlinked) if v.strategic_goal_id else unlinked
                    target["rows"].append((unit_id, unit_name, o, title, kr))

    def build(b: dict) -> dict:
        units: dict = {}
        for unit_id, unit_name, o, title, kr in b["rows"]:
            u = units.setdefault(unit_id, {"unit_id": unit_id, "unit_name": unit_name, "objectives": {}})
            u["objectives"].setdefault(o.id, {"id": o.id, "number": o.number, "title": title, "krs": []})["krs"].append(kr)
        out_units = []
        for u in units.values():
            objs = sorted(u["objectives"].values(), key=lambda x: x["number"])
            ps = [k["progress"] for o in objs for k in o["krs"] if k["progress"] is not None]
            out_units.append({"unit_id": u["unit_id"], "unit_name": u["unit_name"], "progress": _mean(ps), "objectives": objs})
        out_units.sort(key=lambda u: u["unit_name"])
        ps = [r[4]["progress"] for r in b["rows"] if r[4]["progress"] is not None]
        return {"id": b["id"], "title": b["title"], "color": b["color"], "progress": _mean(ps), "krs": len(b["rows"]),
                "recorded": len(ps), "objectives": len({r[2].id for r in b["rows"]}), "units": out_units}

    return {"cycle": {"id": cycle.id, "name": cycle.name} if cycle else None,
            "goals": [build(b) for b in blocks.values()], "unlinked": build(unlinked)}
