from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import access
from app.models import Cycle, StrategicGoal, TimePoint, Unit, UnitPlacement, UnitSession, UnitType
from app.schemas.out import GoalOut, OrgTreeOut, OverviewOut
from app.services import reviews as rev
from app.services.access import Access
from app.services.calc import status_for
from app.services.orgtree import active_org_version

router = APIRouter(tags=["dashboard"])


@router.get("/org/tree", response_model=OrgTreeOut)
def org_tree(db: Session = Depends(get_db), acc: Access = Depends(access)):
    v = active_org_version(db)
    if not v:
        return {"version": None, "units": []}
    placements = db.scalars(select(UnitPlacement).where(UnitPlacement.org_version_id == v.id)
                            .order_by(UnitPlacement.sort)).all()
    units = {u.id: u for u in db.scalars(select(Unit))}
    types = {t.id: t for t in db.scalars(select(UnitType))}
    visible = acc.visible_units("objective")
    nodes = {p.unit_id: {"id": p.unit_id, "name": units[p.unit_id].name, "manager": units[p.unit_id].manager_name,
                         "type": types[units[p.unit_id].type_id].name if units[p.unit_id].type_id else None,
                         "type_color": types[units[p.unit_id].type_id].color_token if units[p.unit_id].type_id else None,
                         "children": []} for p in placements}
    roots = []
    for p in placements:
        (nodes[p.parent_unit_id]["children"] if p.parent_unit_id else roots).append(nodes[p.unit_id])
    return {"version": v.number, "effective_from": v.effective_from, "units": roots,
            "visible_unit_ids": None if visible is None else sorted(visible, key=str)}


@router.get("/dashboard/overview", response_model=OverviewOut)
def overview(db: Session = Depends(get_db), acc: Access = Depends(access)):
    cycle = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
    if not cycle:
        raise HTTPException(404, "چرخهٔ فعالی وجود ندارد")
    tps = db.scalars(select(TimePoint).where(TimePoint.cycle_id == cycle.id).order_by(TimePoint.ordinal)).all()
    visible = acc.visible_units("session")
    unit_ids = {s.unit_id for s in db.scalars(select(UnitSession).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                                              .where(TimePoint.cycle_id == cycle.id))}
    if visible is not None:
        unit_ids &= visible
    rows = []
    for uid in unit_ids:
        unit = db.get(Unit, uid)
        sessions = {s.time_point_id: s for s in db.scalars(select(UnitSession).where(UnitSession.unit_id == uid))}
        cells, current = [], None
        for tp in tps:
            s = sessions.get(tp.id)
            if s is None:
                continue
            is_current = s.status != "held" and current is None
            if is_current:
                current = s
            # held rounds show their frozen score; the open round shows the live one
            score = rev.unit_score(rev.build_session(db, s)) if s.status == "held" or (
                is_current and s.status == "scheduled") else None
            if tp.kind == "start":  # the start session only fixes definitions; it carries no progress
                score = None
            cells.append({"time_point": tp.label, "session_id": s.id, "status": s.status, "score": score,
                          "scheduled_at": s.scheduled_at})
        held = [c for c in cells if c["status"] == "held" and c["score"] is not None]
        latest = held[-1]["score"] if held else None
        prev = held[-2]["score"] if len(held) > 1 else None
        warnings = []
        if current is not None and current.status == "unscheduled":
            warnings.append("زمان جلسه تعیین نشده")
        last = cells[-1]["session_id"] if cells else None
        recorded = total = 0
        cur_tp = next((tp for tp in tps if current is not None and tp.id == current.time_point_id), None)
        if current is not None and cur_tp is not None and cur_tp.kind != "start":
            rows_ = [r for b in rev.build_session(db, current) for r in b.rows]
            total, recorded = len(rows_), sum(1 for r in rows_ if r.entry is not None and r.entry.value is not None)
        rows.append({"unit_id": uid, "current_session_id": current.id if current is not None else last, "unit_name": unit.name, "manager": unit.manager_name, "cells": cells,
                     "latest_score": latest, "delta": (latest - prev) if latest is not None and prev is not None else None,
                     "status": status_for(latest).value, "warnings": warnings,
                     "next_session": ({"id": current.id, "at": current.scheduled_at, "place": current.place}
                                      if current is not None and current.status == "scheduled" else None),
                     "current_round": cur_tp.label if cur_tp is not None else None, "recorded": recorded, "total_krs": total})
    rows.sort(key=lambda r: (not r["warnings"], r["latest_score"] if r["latest_score"] is not None else -1))
    scores = [r["latest_score"] for r in rows if r["latest_score"] is not None]
    return {"cycle": {"id": cycle.id, "name": cycle.name}, "time_points": [t.label for t in tps], "units": rows,
            "org_score": sum(scores) / len(scores) if scores else None,
            "counts": {s: sum(1 for r in rows if r["status"] == s) for s in ("on_track", "at_risk", "behind", "not_recorded")}}


@router.get("/goals", response_model=list[GoalOut])
def goals(db: Session = Depends(get_db), acc: Access = Depends(access)):
    rows = db.scalars(select(StrategicGoal).where(StrategicGoal.active).order_by(StrategicGoal.sort)).all()
    return [{"id": g.id, "title": g.title, "color": g.color_token} for g in rows]
