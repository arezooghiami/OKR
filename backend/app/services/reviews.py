"""Session page logic: which KRs count in a round, live vs frozen percent, entry rules, hold."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import utcnow
from app.models.cycle import TimePoint, UnitSession
from app.models.okr import KeyResult, KRVersion, Objective, ObjectiveVersion, ReviewEntry
from app.services import okr as okr_svc
from app.services.calc import Status, percent, status_for, weighted_mean


class SessionLocked(Exception):
    pass


@dataclass
class KRRow:
    kr: KeyResult
    version: KRVersion
    entry: ReviewEntry | None
    percent: float | None
    status: Status


@dataclass
class ObjectiveBlock:
    objective: Objective
    version: ObjectiveVersion
    rows: list[KRRow]
    score: float | None


def _counts_in_session(kr: KeyResult, session: UnitSession) -> bool:
    cutoff = session.held_at if session.status == "held" and session.held_at else utcnow()
    if kr.created_at > cutoff:
        return False
    return kr.archived_at is None or kr.archived_at > cutoff


def build_session(db: Session, session: UnitSession) -> list[ObjectiveBlock]:
    tp = db.get(TimePoint, session.time_point_id)
    objectives = db.scalars(
        select(Objective).where(Objective.cycle_id == tp.cycle_id, Objective.unit_id == session.unit_id,
                                Objective.archived_at.is_(None)).order_by(Objective.number)
    ).all()
    entries = {e.key_result_id: e for e in db.scalars(select(ReviewEntry).where(ReviewEntry.session_id == session.id))}
    blocks = []
    for o in objectives:
        rows: list[KRRow] = []
        for kr in db.scalars(select(KeyResult).where(KeyResult.objective_id == o.id).order_by(KeyResult.number)):
            if not _counts_in_session(kr, session):
                continue
            entry = entries.get(kr.id)
            if entry and entry.is_frozen and entry.frozen_kr_version_id:
                ver, pct = db.get(KRVersion, entry.frozen_kr_version_id), entry.frozen_percent
            else:
                ver = okr_svc.current_kr_version(db, kr.id)
                pct = percent(okr_svc.definition_of(ver), entry.value if entry else None)
            rows.append(KRRow(kr, ver, entry, pct, status_for(pct)))
        score = weighted_mean([(r.percent, r.version.weight) for r in rows])
        blocks.append(ObjectiveBlock(o, okr_svc.current_objective_version(db, o.id), rows, score))
    return blocks


def unit_score(blocks: list[ObjectiveBlock]) -> float | None:
    return weighted_mean([(b.score, b.version.weight) for b in blocks if b.rows])


def previous_session(db: Session, session: UnitSession) -> UnitSession | None:
    tp = db.get(TimePoint, session.time_point_id)
    return db.scalars(
        select(UnitSession).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
        .where(UnitSession.unit_id == session.unit_id, TimePoint.cycle_id == tp.cycle_id, TimePoint.ordinal < tp.ordinal)
        .order_by(TimePoint.ordinal.desc()).limit(1)
    ).first()


def entry_blocker(db: Session, session: UnitSession) -> str | None:
    """Why values cannot be entered right now (None = open)."""
    from app.models.cycle import Cycle

    tp = db.get(TimePoint, session.time_point_id)
    if db.get(Cycle, tp.cycle_id).status == "closed":
        return "این دوره بسته است و فقط‌خواندنی است"
    if session.status == "held":
        return "این جلسه برگزار شده و مقادیر آن منجمد است"
    if session.status == "unscheduled":
        return "برای این واحد زمان جلسه تعیین نشده است"
    prev = previous_session(db, session)
    if prev is not None and prev.status != "held":
        return "تب این پایش پس از «برگزار شد» جلسهٔ قبلی باز می‌شود"
    return None


def set_entry(db: Session, *, session: UnitSession, kr_id: uuid.UUID, value: float | None, note: str | None,
              confidence: str | None, actor_id, expected_version: int | None = None) -> ReviewEntry:
    blocker = entry_blocker(db, session)
    if blocker:
        raise SessionLocked(blocker)
    e = db.scalars(select(ReviewEntry).where(ReviewEntry.key_result_id == kr_id,
                                             ReviewEntry.session_id == session.id)).first()
    before = {"value": e.value, "note": e.note} if e else None
    if e is None:
        e = ReviewEntry(key_result_id=kr_id, session_id=session.id)
        db.add(e)
    elif expected_version is not None and e.version != expected_version:
        raise okr_svc.StaleVersion(e.version)
    else:
        e.version += 1
    e.value, e.note, e.confidence, e.updated_by = value, note, confidence, actor_id
    audit.record(db, actor_id=actor_id, action="set_value", resource="review_entry", resource_id=kr_id,
                 before=before, after={"value": value, "note": note, "session": str(session.id)})
    db.flush()
    return e


def hold_session(db: Session, *, session: UnitSession, actor_id, held_at: datetime | None = None,
                 backdated: bool = False) -> UnitSession:
    """Mark held; freeze definition version and percent of every counted KR for this round."""
    if session.status == "held":
        return session
    if session.status == "unscheduled":
        raise SessionLocked("جلسه‌ای که زمان ندارد نمی‌تواند برگزار شود")
    when = held_at or utcnow()
    session.status, session.held_at = "held", when
    session.version += 1
    for block in build_session(db, session):
        for row in block.rows:
            e = row.entry
            if e is None:
                e = ReviewEntry(key_result_id=row.kr.id, session_id=session.id)
                db.add(e)
            ver = okr_svc.kr_version_at(db, row.kr.id, when) or row.version
            e.frozen_kr_version_id = ver.id
            e.frozen_percent = percent(okr_svc.definition_of(ver), e.value)
            e.is_frozen = True
    audit.record(db, actor_id=actor_id, action="hold_backdated" if backdated else "hold", resource="unit_session",
                 resource_id=session.id, after={"held_at": when.isoformat()})
    db.flush()
    return session
