import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.deps import access, client_ip, require, require_open_cycle
from app.models import Cycle, KRVersion, StrategicGoal, TimePoint, Unit, UnitSession, User
from app.schemas.out import CycleOut, EntryOut, SessionHead, SessionPageOut
from app.services import reviews as rev
from app.services.access import Access
from app.services.okr import StaleVersion

router = APIRouter(tags=["sessions"])


def get_session_or_404(db: Session, session_id: uuid.UUID) -> UnitSession:
    s = db.get(UnitSession, session_id)
    if not s:
        raise HTTPException(404, "جلسه پیدا نشد")
    return s


def session_head(db: Session, s: UnitSession) -> dict:  # shape: schemas.out.SessionHead
    tp, unit = db.get(TimePoint, s.time_point_id), db.get(Unit, s.unit_id)
    return {"id": s.id, "unit_id": unit.id, "unit_name": unit.name, "time_point": tp.label, "kind": tp.kind,
            "ordinal": tp.ordinal, "scheduled_at": s.scheduled_at, "place": s.place, "status": s.status,
            "held_at": s.held_at, "version": s.version}


def cycle_out(db: Session, cycle: Cycle) -> dict:  # shape: schemas.out.CycleOut
    tps = db.scalars(select(TimePoint).where(TimePoint.cycle_id == cycle.id).order_by(TimePoint.ordinal)).all()
    return {"id": cycle.id, "name": cycle.name, "starts_on": cycle.starts_on, "ends_on": cycle.ends_on,
            "status": cycle.status,
            "time_points": [{"id": t.id, "label": t.label, "kind": t.kind, "ordinal": t.ordinal} for t in tps]}


@router.get("/cycles/current", response_model=CycleOut)
def current_cycle(db: Session = Depends(get_db), acc: Access = Depends(access)):
    cycle = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
    if not cycle:
        raise HTTPException(404, "چرخهٔ فعالی وجود ندارد")
    return cycle_out(db, cycle)


@router.get("/cycles", response_model=list[CycleOut])
def cycles(db: Session = Depends(get_db), acc: Access = Depends(access)):
    """The active cycle first, then past (closed) cycles, newest first. Drafts are an admin matter."""
    rows = db.scalars(select(Cycle).where(Cycle.status.in_(("active", "closed")))).all()
    rows = sorted(rows, key=lambda c: (c.status != "active", -c.starts_on.toordinal()))
    return [cycle_out(db, c) for c in rows]


@router.get("/time-points/{time_point_id}/sessions", response_model=list[SessionHead])
def time_point_sessions(time_point_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """Every unit's session for one time point (the scheduling table)."""
    visible = acc.visible_units("session")
    rows = db.scalars(select(UnitSession).where(UnitSession.time_point_id == time_point_id)).all()
    return sorted((session_head(db, s) for s in rows if visible is None or s.unit_id in visible),
                  key=lambda r: r["unit_name"])


@router.get("/units/{unit_id}/sessions", response_model=list[SessionHead])
def unit_sessions(unit_id: uuid.UUID, cycle_id: uuid.UUID | None = None, db: Session = Depends(get_db),
                  acc: Access = Depends(access)):
    """The unit's sessions of one cycle (default: the active cycle), in time order."""
    require(acc, "session", "view", unit_id)
    if cycle_id is None:
        active = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
        if not active:
            return []
        cycle_id = active.id
    rows = db.scalars(select(UnitSession).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                      .where(UnitSession.unit_id == unit_id, TimePoint.cycle_id == cycle_id)
                      .order_by(TimePoint.ordinal)).all()
    return [session_head(db, s) for s in rows]


@router.get("/sessions/{session_id}/siblings", response_model=list[SessionHead])
def sibling_sessions(session_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """All sessions of this session's unit within the same cycle (drives the round stepper)."""
    s = get_session_or_404(db, session_id)
    require(acc, "session", "view", s.unit_id)
    cycle_id = db.get(TimePoint, s.time_point_id).cycle_id
    rows = db.scalars(select(UnitSession).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                      .where(UnitSession.unit_id == s.unit_id, TimePoint.cycle_id == cycle_id)
                      .order_by(TimePoint.ordinal)).all()
    return [session_head(db, x) for x in rows]


@router.get("/sessions/{session_id}", response_model=SessionPageOut)
def session_page(session_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    s = get_session_or_404(db, session_id)
    require(acc, "session", "view", s.unit_id)
    blocks = rev.build_session(db, s)
    goals = {g.id: g for g in db.scalars(select(StrategicGoal))}
    can_edit = acc.can("review_value", "edit", s.unit_id)
    names = dict(db.execute(select(User.id, User.full_name)).all())
    return {
        **session_head(db, s),
        "entry_blocker": rev.entry_blocker(db, s),
        "can_edit_values": can_edit and rev.entry_blocker(db, s) is None,
        "can_edit_definitions": acc.can("key_result", "edit", s.unit_id)
        and db.get(Cycle, db.get(TimePoint, s.time_point_id).cycle_id).status != "closed",
        "score": rev.unit_score(blocks),
        "objectives": [{
            "id": b.objective.id, "number": b.objective.number, "title": b.version.title, "score": b.score,
            "description": b.version.description, "owner_id": b.version.owner_id,
            "owner_name": names.get(b.version.owner_id),
            "key_results": [{
                "id": r.kr.id, "code": f"{b.objective.number}.{r.kr.number}", "title": r.version.title,
                "description": r.version.description, "kind": r.version.kind, "baseline": r.version.baseline,
                "target": r.version.target, "definition_version": r.version.number, "owner_id": r.version.owner_id,
                "owner_name": names.get(r.version.owner_id),
                "goal": ({"id": goals[r.version.strategic_goal_id].id, "title": goals[r.version.strategic_goal_id].title,
                          "color": goals[r.version.strategic_goal_id].color_token}
                         if r.version.strategic_goal_id in goals else None),
                "value": r.entry.value if r.entry else None, "note": r.entry.note if r.entry else None,
                "entry_version": r.entry.version if r.entry else None,
                "percent": r.percent, "status": r.status.value, "frozen": bool(r.entry and r.entry.is_frozen),
            } for r in b.rows]} for b in blocks],
    }


class ScheduleIn(BaseModel):
    scheduled_at: datetime
    place: str | None = None
    expected_version: int | None = None


@router.put("/sessions/{session_id}", response_model=SessionHead)
def schedule(session_id: uuid.UUID, body: ScheduleIn, request: Request, db: Session = Depends(get_db),
             acc: Access = Depends(access)):
    s = get_session_or_404(db, session_id)
    require(acc, "session", "edit", s.unit_id)
    require_open_cycle(db, db.get(TimePoint, s.time_point_id).cycle_id)
    if s.status == "held":
        raise HTTPException(409, "جلسهٔ برگزارشده قابل زمان‌بندی مجدد نیست")
    if body.expected_version is not None and body.expected_version != s.version:
        raise HTTPException(409, "جلسه در این فاصله تغییر کرده است")
    before = {"scheduled_at": s.scheduled_at, "place": s.place}
    s.scheduled_at, s.place, s.status, s.version = body.scheduled_at, body.place, "scheduled", s.version + 1
    audit.record(db, actor_id=acc.user.id, action="schedule", resource="unit_session", resource_id=s.id,
                 before=before, after={"scheduled_at": body.scheduled_at, "place": body.place}, ip=client_ip(request))
    db.commit()
    return session_head(db, s)


class HoldIn(BaseModel):
    held_at: datetime | None = None  # backdating is system-admin only


@router.post("/sessions/{session_id}/hold", response_model=SessionHead)
def hold(session_id: uuid.UUID, body: HoldIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    s = get_session_or_404(db, session_id)
    # marking a session held freezes that round for the unit: only the system administrator does it
    if not acc.user.is_system_admin:
        raise HTTPException(403, "فقط مدیر سیستم می‌تواند برگزاری جلسه را ثبت کند")
    require_open_cycle(db, db.get(TimePoint, s.time_point_id).cycle_id)
    try:
        rev.hold_session(db, session=s, actor_id=acc.user.id, held_at=body.held_at, backdated=bool(body.held_at))
    except rev.SessionLocked as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return session_head(db, s)


class EntryIn(BaseModel):
    value: float | None = None
    note: str | None = None
    confidence: str | None = None
    expected_version: int | None = None


@router.put("/sessions/{session_id}/entries/{kr_id}", response_model=EntryOut)
def put_entry(session_id: uuid.UUID, kr_id: uuid.UUID, body: EntryIn, db: Session = Depends(get_db),
              acc: Access = Depends(access)):
    s = get_session_or_404(db, session_id)
    require(acc, "review_value", "edit", s.unit_id)
    try:
        e = rev.set_entry(db, session=s, kr_id=kr_id, value=body.value, note=body.note,
                          confidence=body.confidence, actor_id=acc.user.id, expected_version=body.expected_version)
    except rev.SessionLocked as ex:
        raise HTTPException(409, str(ex)) from ex
    except StaleVersion as ex:
        raise HTTPException(409, f"مقدار در این فاصله توسط دیگری تغییر کرده است (نسخه {ex.current})") from ex
    ver = db.scalars(select(KRVersion).where(KRVersion.key_result_id == kr_id).order_by(KRVersion.number.desc())).first()
    from app.services.calc import percent, status_for
    from app.services.okr import definition_of
    p = percent(definition_of(ver), e.value)
    db.commit()
    return {"value": e.value, "note": e.note, "entry_version": e.version, "percent": p, "status": status_for(p).value}
