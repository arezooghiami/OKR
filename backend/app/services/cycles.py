"""Cycle structure: time points and the unit x time point sessions that follow from them."""

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import (
    Attachment,
    Comment,
    Cycle,
    KRVersion,
    ObjectiveVersion,
    ReviewEntry,
    TimePoint,
    Unit,
    UnitPlacement,
    UnitSession,
)
from app.services.orgtree import active_org_version


class CycleError(ValueError):
    pass


def active_unit_ids(db: Session) -> list[uuid.UUID]:
    v = active_org_version(db)
    if not v:
        return []
    ids = db.scalars(select(UnitPlacement.unit_id).where(UnitPlacement.org_version_id == v.id)).all()
    live = set(db.scalars(select(Unit.id).where(Unit.archived.is_(False))).all())
    return [i for i in ids if i in live]


def ensure_sessions(db: Session, *, cycle_id: uuid.UUID | None = None, unit_id: uuid.UUID | None = None) -> int:
    """Create the missing (unit x time point) sessions for open cycles; returns how many were added."""
    cycles = [cycle_id] if cycle_id else list(db.scalars(select(Cycle.id).where(Cycle.status != "closed")))
    units = [unit_id] if unit_id else active_unit_ids(db)
    added = 0
    for cid in cycles:
        for tp in db.scalars(select(TimePoint).where(TimePoint.cycle_id == cid)):
            have = set(db.scalars(select(UnitSession.unit_id).where(UnitSession.time_point_id == tp.id)))
            for u in units:
                if u not in have:
                    db.add(UnitSession(unit_id=u, time_point_id=tp.id))
                    added += 1
    db.flush()
    return added


def _ordered(db: Session, cycle_id: uuid.UUID) -> list[TimePoint]:
    return list(db.scalars(select(TimePoint).where(TimePoint.cycle_id == cycle_id).order_by(TimePoint.ordinal)))


def _renumber(db: Session, tps: list[TimePoint]) -> None:
    # two passes so the (cycle, ordinal) unique constraint is never violated mid-way
    for i, tp in enumerate(tps):
        tp.ordinal = 1000 + i
    db.flush()
    for i, tp in enumerate(tps):
        tp.ordinal = i
    db.flush()


def add_time_point(db: Session, cycle: Cycle, kind: str, label: str) -> TimePoint:
    if kind not in ("start", "review", "final"):
        raise CycleError("نوع نقطهٔ زمانی نامعتبر است")
    label = label.strip()
    if not label:
        raise CycleError("برچسب نقطهٔ زمانی خالی است")
    tps = _ordered(db, cycle.id)
    if any(t.label == label for t in tps):
        raise CycleError("این برچسب در چرخه تکراری است")
    if kind in ("start", "final") and any(t.kind == kind for t in tps):
        raise CycleError("هر چرخه فقط یک جلسهٔ شروع و یک جلسهٔ نهایی دارد")
    tp = TimePoint(cycle_id=cycle.id, kind=kind, ordinal=10_000, label=label)
    db.add(tp)
    db.flush()
    if kind == "start":
        tps.insert(0, tp)
    elif kind == "final":
        tps.append(tp)
    else:  # reviews go after the last review and before the final session
        pos = next((i for i, t in enumerate(tps) if t.kind == "final"), len(tps))
        tps.insert(pos, tp)
    _renumber(db, tps)
    ensure_sessions(db, cycle_id=cycle.id)
    return tp


def delete_time_point(db: Session, tp: TimePoint) -> None:
    sessions = list(db.scalars(select(UnitSession).where(UnitSession.time_point_id == tp.id)))
    if any(s.status == "held" for s in sessions):
        raise CycleError("برای این نقطه جلسهٔ برگزارشده وجود دارد و حذف نمی‌شود")
    ids = [s.id for s in sessions]
    used = (
        db.scalar(select(func.count()).select_from(ReviewEntry).where(ReviewEntry.session_id.in_(ids), ReviewEntry.value.is_not(None)))
        or db.scalar(select(func.count()).select_from(KRVersion).where(KRVersion.session_id.in_(ids)))
        or db.scalar(select(func.count()).select_from(ObjectiveVersion).where(ObjectiveVersion.session_id.in_(ids)))
        or db.scalar(select(func.count()).select_from(Comment).where(Comment.session_id.in_(ids)))
        or db.scalar(select(func.count()).select_from(Attachment).where(Attachment.session_id.in_(ids)))
    )
    if used:
        raise CycleError("برای این نقطه داده ثبت شده است و حذف نمی‌شود")
    db.execute(delete(ReviewEntry).where(ReviewEntry.session_id.in_(ids)))  # blank placeholders only
    for s in sessions:
        db.delete(s)
    db.flush()  # sessions must go before their time point (no ORM relationship orders this for us)
    cycle_id = tp.cycle_id
    db.delete(tp)
    db.flush()
    _renumber(db, _ordered(db, cycle_id))
