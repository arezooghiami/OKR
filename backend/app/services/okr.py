"""Objective / KR definition versioning (PRD 4.4b). Every definitional edit creates a new version."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import utcnow
from app.models.cycle import TimePoint, UnitSession
from app.models.okr import KeyResult, KRVersion, Objective, ObjectiveVersion
from app.services.calc import Definition, InvalidDefinition, KRKind, validate_definition

KR_FIELDS = (
    "title", "description", "kind", "unit_of_measure", "baseline", "target", "range_min", "range_max",
    "weight", "owner_id", "strategic_goal_id", "expectation",
)
OBJ_FIELDS = ("title", "description", "owner_id", "weight")


class ReasonRequired(ValueError):
    pass


def definition_of(v: KRVersion) -> Definition:
    return Definition(KRKind(v.kind), v.baseline, v.target, v.range_min, v.range_max)


def current_kr_version(db: Session, kr_id: uuid.UUID) -> KRVersion:
    return db.scalars(
        select(KRVersion).where(KRVersion.key_result_id == kr_id).order_by(KRVersion.number.desc()).limit(1)
    ).one()


def kr_version_at(db: Session, kr_id: uuid.UUID, at: datetime) -> KRVersion | None:
    return db.scalars(
        select(KRVersion)
        .where(KRVersion.key_result_id == kr_id, KRVersion.created_at <= at)
        .order_by(KRVersion.number.desc()).limit(1)
    ).first()


def current_objective_version(db: Session, obj_id: uuid.UUID) -> ObjectiveVersion:
    return db.scalars(
        select(ObjectiveVersion).where(ObjectiveVersion.objective_id == obj_id)
        .order_by(ObjectiveVersion.number.desc()).limit(1)
    ).one()


def edit_context(db: Session, cycle_id: uuid.UUID, unit_id: uuid.UUID, session: UnitSession | None) -> str:
    """in_session / after_session when edited from a session page; outside a session it is a draft
    ("initial") until the unit's start session is held, and "between" sessions after that."""
    if session is not None:
        return "after_session" if session.status == "held" else "in_session"
    start = db.scalars(select(UnitSession).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                       .where(UnitSession.unit_id == unit_id, TimePoint.cycle_id == cycle_id,
                              TimePoint.kind == "start")).first()
    return "between" if start is not None and start.status == "held" else "initial"


def _clean(d: dict, fields: tuple[str, ...]) -> dict:
    return {k: d[k] for k in fields if k in d}


def create_objective(db: Session, *, cycle_id, unit_id, actor_id, data: dict, reason: str | None = None) -> Objective:
    number = (db.scalar(select(func.max(Objective.number)).where(
        Objective.cycle_id == cycle_id, Objective.unit_id == unit_id)) or 0) + 1
    obj = Objective(cycle_id=cycle_id, unit_id=unit_id, number=number)
    db.add(obj)
    db.flush()
    f = _clean(data, OBJ_FIELDS)
    db.add(ObjectiveVersion(objective_id=obj.id, number=1, actor_id=actor_id, created_at=utcnow(),
                            context="initial", reason=reason, **{"weight": 1.0, **f}))
    audit.record(db, actor_id=actor_id, action="create", resource="objective", resource_id=obj.id, after=f)
    return obj


def create_kr(db: Session, *, objective: Objective, actor_id, data: dict, time_point_id=None,
              context: str = "initial", session_id=None, reason: str | None = None) -> KeyResult:
    f = _clean(data, KR_FIELDS)
    _validate(f)
    number = (db.scalar(select(func.max(KeyResult.number)).where(KeyResult.objective_id == objective.id)) or 0) + 1
    kr = KeyResult(objective_id=objective.id, number=number, created_in_time_point=time_point_id,
                   external_id=data.get("external_id"))
    db.add(kr)
    db.flush()
    db.add(KRVersion(key_result_id=kr.id, number=1, actor_id=actor_id, created_at=utcnow(), context=context,
                     session_id=session_id, reason=reason, **{"weight": 1.0, "kind": "numeric", **f}))
    audit.record(db, actor_id=actor_id, action="create", resource="key_result", resource_id=kr.id, after=f)
    return kr


def _validate(f: dict) -> None:
    kind = f.get("kind", "numeric")
    try:
        validate_definition(Definition(KRKind(kind), f.get("baseline"), f.get("target"),
                                       f.get("range_min"), f.get("range_max")))
    except (InvalidDefinition, ValueError) as e:
        raise InvalidDefinition(str(e)) from e


@dataclass
class Change:
    field: str
    before: object
    after: object


def update_kr(db: Session, *, kr: KeyResult, actor_id, changes: dict, expected_version: int | None,
              reason: str | None, context: str, session_id=None) -> tuple[KRVersion, list[Change]]:
    """Create a new KRVersion when any definitional field changed. A reason is mandatory when the target changes."""
    if expected_version is not None and kr.version != expected_version:
        raise StaleVersion(kr.version)
    cur = current_kr_version(db, kr.id)
    c = _clean(changes, KR_FIELDS)
    diff = [Change(k, getattr(cur, k), v) for k, v in c.items() if getattr(cur, k) != v]
    if not diff:
        return cur, []
    merged = {k: getattr(cur, k) for k in KR_FIELDS} | c
    _validate(merged)
    if any(d.field == "target" for d in diff) and not (reason and reason.strip()):
        raise ReasonRequired("دلیل تغییر هدف الزامی است")
    new = KRVersion(key_result_id=kr.id, number=cur.number + 1, actor_id=actor_id, created_at=utcnow(),
                    context=context, session_id=session_id, reason=reason, **merged)
    db.add(new)
    kr.version += 1
    audit.record(db, actor_id=actor_id, action="update", resource="key_result", resource_id=kr.id,
                 before={d.field: d.before for d in diff}, after={d.field: d.after for d in diff})
    db.flush()
    return new, diff


class StaleVersion(Exception):
    def __init__(self, current: int):
        self.current = current


def archive_kr(db: Session, *, kr: KeyResult, actor_id, reason: str) -> None:
    if not reason.strip():
        raise ReasonRequired("دلیل حذف الزامی است")
    kr.archived_at, kr.archive_reason = utcnow(), reason
    audit.record(db, actor_id=actor_id, action="archive", resource="key_result", resource_id=kr.id,
                 after={"reason": reason})


def archive_objective(db: Session, *, objective: Objective, actor_id, reason: str) -> int:
    """Remove an objective (and its KRs) from the lists. Nothing is deleted: versions, values and audit stay."""
    if not reason.strip():
        raise ReasonRequired("دلیل حذف الزامی است")
    now = utcnow()
    krs = db.scalars(select(KeyResult).where(KeyResult.objective_id == objective.id, KeyResult.archived_at.is_(None))).all()
    for kr in krs:
        kr.archived_at, kr.archive_reason = now, reason
    objective.archived_at, objective.archive_reason = now, reason
    audit.record(db, actor_id=actor_id, action="archive", resource="objective", resource_id=objective.id,
                 after={"reason": reason, "key_results": len(krs)})
    return len(krs)


def label_for(db: Session, tp_id: uuid.UUID) -> str:
    return db.get(TimePoint, tp_id).label


def update_objective(db: Session, *, objective: Objective, actor_id, changes: dict, context: str, session_id=None,
                     reason: str | None = None) -> ObjectiveVersion | None:
    cur = current_objective_version(db, objective.id)
    c = _clean(changes, OBJ_FIELDS)
    diff = {k: v for k, v in c.items() if getattr(cur, k) != v}
    if not diff:
        return None
    merged = {k: getattr(cur, k) for k in OBJ_FIELDS} | diff
    if not str(merged["title"]).strip():
        raise InvalidDefinition("عنوان هدف خالی است")
    new = ObjectiveVersion(objective_id=objective.id, number=cur.number + 1, actor_id=actor_id, created_at=utcnow(),
                           context=context, session_id=session_id, reason=reason, **merged)
    db.add(new)
    objective.version += 1
    audit.record(db, actor_id=actor_id, action="update", resource="objective", resource_id=objective.id,
                 before={k: getattr(cur, k) for k in diff}, after=diff)
    db.flush()
    return new
