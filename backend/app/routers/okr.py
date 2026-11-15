import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import access, require, require_open_cycle
from app.models import (
    Comment,
    Cycle,
    KeyResult,
    KRVersion,
    Membership,
    Objective,
    ReviewEntry,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitSession,
    User,
)
from app.schemas.out import IdOut, KRCreated, KRDetailOut, KRPatched, MemberOut, MyBlockOut, ObjectiveCreated
from app.services import okr as svc
from app.services import reviews as rev
from app.services.access import Access
from app.services.calc import InvalidDefinition, percent, status_for

router = APIRouter(tags=["okr"])


def _unit_of_kr(db: Session, kr: KeyResult) -> tuple[Objective, uuid.UUID]:
    obj = db.get(Objective, kr.objective_id)
    return obj, obj.unit_id


class ObjectiveIn(BaseModel):
    title: str
    description: str | None = None
    owner_id: uuid.UUID | None = None
    weight: float = 1.0


@router.post("/units/{unit_id}/objectives", status_code=201, response_model=ObjectiveCreated)
def create_objective(unit_id: uuid.UUID, body: ObjectiveIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    require(acc, "objective", "create", unit_id)
    cycle = db.scalars(select(Cycle).where(Cycle.status == "active")).first()
    if not cycle:
        raise HTTPException(409, "دورهٔ فعالی وجود ندارد")
    obj = svc.create_objective(db, cycle_id=cycle.id, unit_id=unit_id, actor_id=acc.user.id, data=body.model_dump())
    db.commit()
    return {"id": obj.id, "number": obj.number}


class KRIn(BaseModel):
    title: str
    description: str | None = None
    kind: str = "numeric"
    unit_of_measure: str | None = None
    baseline: float | None = None
    target: float | None = None
    range_min: float | None = None
    range_max: float | None = None
    weight: float = 1.0
    owner_id: uuid.UUID | None = None
    strategic_goal_id: uuid.UUID | None = None
    expectation: str | None = None
    session_id: uuid.UUID | None = None  # set when created from a session page


@router.post("/objectives/{objective_id}/key-results", status_code=201, response_model=KRCreated)
def create_kr(objective_id: uuid.UUID, body: KRIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    obj = db.get(Objective, objective_id)
    if not obj:
        raise HTTPException(404, "هدف پیدا نشد")
    require(acc, "key_result", "create", obj.unit_id)
    require_open_cycle(db, obj.cycle_id)
    sess = db.get(UnitSession, body.session_id) if body.session_id else None
    data = body.model_dump(exclude={"session_id"})
    if data["owner_id"] is None:  # default owner: whoever owns the objective (docs/07 phase 2)
        data["owner_id"] = svc.current_objective_version(db, obj.id).owner_id
    try:
        kr = svc.create_kr(db, objective=obj, actor_id=acc.user.id, data=data,
                           context=svc.edit_context(db, obj.cycle_id, obj.unit_id, sess),
                           session_id=sess.id if sess else None)
    except InvalidDefinition as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return {"id": kr.id, "code": f"{obj.number}.{kr.number}"}


class OwnerBulkIn(BaseModel):
    key_result_ids: list[uuid.UUID]
    owner_id: uuid.UUID | None  # None = clear the owner


class OwnerBulkOut(BaseModel):
    changed: int
    unchanged: int


@router.post("/units/{unit_id}/key-results/owner", response_model=OwnerBulkOut)
def set_owner_bulk(unit_id: uuid.UUID, body: OwnerBulkIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """Give many KRs of one unit the same owner in one step (e.g. right after an Excel import).
    Each change is a normal new definition version with its audit record."""
    require(acc, "key_result", "edit", unit_id)
    if body.owner_id is not None:
        u = db.get(User, body.owner_id)
        if u is None or not u.is_active:
            raise HTTPException(422, "کاربر انتخاب‌شده فعال نیست")
    krs = db.scalars(select(KeyResult).join(Objective, Objective.id == KeyResult.objective_id)
                     .where(KeyResult.id.in_(body.key_result_ids), Objective.unit_id == unit_id,
                            KeyResult.archived_at.is_(None))).all()
    if len(krs) != len(set(body.key_result_ids)):
        raise HTTPException(422, "بعضی نتیجه‌های کلیدی پیدا نشدند یا به این واحد تعلق ندارند")
    changed = 0
    for kr in krs:
        obj = db.get(Objective, kr.objective_id)
        require_open_cycle(db, obj.cycle_id)
        _, diff = svc.update_kr(db, kr=kr, actor_id=acc.user.id, changes={"owner_id": body.owner_id},
                                expected_version=None, reason="تعیین مسئول گروهی",
                                context=svc.edit_context(db, obj.cycle_id, unit_id, None))
        changed += bool(diff)
    db.commit()
    return {"changed": changed, "unchanged": len(krs) - changed}


class KRPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    kind: str | None = None
    unit_of_measure: str | None = None
    baseline: float | None = None
    target: float | None = None
    range_min: float | None = None
    range_max: float | None = None
    weight: float | None = None
    owner_id: uuid.UUID | None = None
    strategic_goal_id: uuid.UUID | None = None
    expectation: str | None = None
    reason: str | None = None
    session_id: uuid.UUID | None = None
    expected_version: int | None = None


@router.patch("/key-results/{kr_id}", response_model=KRPatched)
def patch_kr(kr_id: uuid.UUID, body: KRPatch, db: Session = Depends(get_db), acc: Access = Depends(access)):
    kr = db.get(KeyResult, kr_id)
    if not kr:
        raise HTTPException(404, "نتیجه کلیدی پیدا نشد")
    obj, unit_id = _unit_of_kr(db, kr)
    require(acc, "key_result", "edit", unit_id)
    require_open_cycle(db, obj.cycle_id)
    sess = db.get(UnitSession, body.session_id) if body.session_id else None
    changes = body.model_dump(exclude={"reason", "session_id", "expected_version"}, exclude_unset=True)
    try:
        ver, diff = svc.update_kr(
            db, kr=kr, actor_id=acc.user.id, changes=changes, expected_version=body.expected_version,
            reason=body.reason, context=svc.edit_context(db, obj.cycle_id, unit_id, sess),
            session_id=sess.id if sess else None)
    except svc.ReasonRequired as e:
        raise HTTPException(422, str(e)) from e
    except InvalidDefinition as e:
        raise HTTPException(422, str(e)) from e
    except svc.StaleVersion as e:
        raise HTTPException(409, f"این نتیجه کلیدی در این فاصله تغییر کرده است (نسخه {e.current})") from e
    db.commit()
    return {"version": ver.number, "changed": [d.field for d in diff], "resource_version": kr.version}


def _ver_out(db: Session, v: KRVersion, names: dict) -> dict:
    return {"number": v.number, "title": v.title, "baseline": v.baseline, "target": v.target, "weight": v.weight,
            "kind": v.kind, "actor": names.get(v.actor_id), "at": v.created_at, "context": v.context,
            "reason": v.reason, "session_id": v.session_id}


@router.get("/key-results/{kr_id}", response_model=KRDetailOut)
def kr_detail(kr_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    kr = db.get(KeyResult, kr_id)
    if not kr:
        raise HTTPException(404, "نتیجه کلیدی پیدا نشد")
    obj, unit_id = _unit_of_kr(db, kr)
    require(acc, "key_result", "view", unit_id)
    versions = db.scalars(select(KRVersion).where(KRVersion.key_result_id == kr_id).order_by(KRVersion.number.desc())).all()
    cur = versions[0]
    names = {u.id: u.full_name for u in db.scalars(select(User))}
    series = []
    sessions = db.execute(select(UnitSession, TimePoint).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                          .where(UnitSession.unit_id == unit_id, TimePoint.cycle_id == obj.cycle_id)
                          .order_by(TimePoint.ordinal)).all()
    entries = {e.session_id: e for e in db.scalars(select(ReviewEntry).where(ReviewEntry.key_result_id == kr_id))}
    for s, tp in sessions:
        e = entries.get(s.id)
        if e is None:
            continue
        p = e.frozen_percent if e.is_frozen else percent(svc.definition_of(cur), e.value)
        series.append({"label": tp.label, "value": e.value, "note": e.note, "percent": p, "frozen": e.is_frozen})
    last = next((x for x in reversed(series) if x["value"] is not None), None)
    goal = db.get(StrategicGoal, cur.strategic_goal_id) if cur.strategic_goal_id else None
    comments = db.scalars(select(Comment).where(Comment.key_result_id == kr_id).order_by(Comment.created_at.desc())).all()
    formula = None
    if last and cur.kind == "numeric":
        formula = {"expression": "(value − base) / (target − base)", "value": last["value"],
                   "baseline": cur.baseline, "target": cur.target, "percent": last["percent"]}
    return {
        "id": kr.id, "code": f"{obj.number}.{kr.number}", "unit_id": unit_id, "objective_id": obj.id,
        "version": kr.version, "definition": _ver_out(db, cur, names) | {
            "description": cur.description, "expectation": cur.expectation, "unit_of_measure": cur.unit_of_measure,
            "owner": names.get(cur.owner_id), "goal": goal.title if goal else None},
        "status": status_for(last["percent"] if last else None).value,
        "series": series, "formula": formula,
        "versions": [_ver_out(db, v, names) for v in versions],
        "comments": [{"id": c.id, "author": names.get(c.author_id), "body": c.body, "at": c.created_at} for c in comments],
        "can_edit": acc.can("key_result", "edit", unit_id),
    }


class CommentIn(BaseModel):
    body: str
    session_id: uuid.UUID | None = None


@router.post("/key-results/{kr_id}/comments", status_code=201, response_model=IdOut)
def add_comment(kr_id: uuid.UUID, body: CommentIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    kr = db.get(KeyResult, kr_id)
    if not kr:
        raise HTTPException(404, "نتیجه کلیدی پیدا نشد")
    obj, unit_id = _unit_of_kr(db, kr)
    require(acc, "key_result", "view", unit_id)
    require_open_cycle(db, obj.cycle_id)
    if not body.body.strip():
        raise HTTPException(422, "متن کامنت خالی است")
    c = Comment(key_result_id=kr_id, session_id=body.session_id, author_id=acc.user.id, body=body.body.strip())
    db.add(c)
    db.commit()
    return {"id": c.id}


@router.get("/me/key-results", response_model=list[MyBlockOut])
def my_key_results(db: Session = Depends(get_db), acc: Access = Depends(access)):
    """KRs owned by me, grouped by objective, with the value of the unit's current open session."""
    out: dict[uuid.UUID, dict] = {}
    krs = db.scalars(select(KeyResult).where(KeyResult.archived_at.is_(None))).all()
    for kr in krs:
        cur = svc.current_kr_version(db, kr.id)
        if cur.owner_id != acc.user.id:
            continue
        obj, unit_id = _unit_of_kr(db, kr)
        sess = db.scalars(select(UnitSession).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                          .where(UnitSession.unit_id == unit_id, UnitSession.status != "held",
                                 TimePoint.cycle_id == obj.cycle_id).order_by(TimePoint.ordinal).limit(1)).first()
        prev = db.execute(select(ReviewEntry, TimePoint).join(UnitSession, UnitSession.id == ReviewEntry.session_id)
                          .join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                          .where(ReviewEntry.key_result_id == kr.id, UnitSession.status == "held",
                                 ReviewEntry.value.is_not(None))
                          .order_by(TimePoint.ordinal.desc()).limit(1)).first()
        tp = db.get(TimePoint, sess.time_point_id) if sess else None
        blocker = (rev.entry_blocker(db, sess) if sess else "پایش بازی برای این واحد نیست")
        if blocker is None and not acc.can("review_value", "edit", unit_id):
            blocker = "اجازهٔ ثبت مقدار در این واحد را ندارید"
        e = db.scalars(select(ReviewEntry).where(ReviewEntry.key_result_id == kr.id,
                                                 ReviewEntry.session_id == sess.id)).first() if sess else None
        p = percent(svc.definition_of(cur), e.value if e else None)
        ov = svc.current_objective_version(db, obj.id)
        block = out.setdefault(obj.id, {"objective_id": obj.id, "title": ov.title,
                                        "unit_name": db.get(Unit, unit_id).name, "key_results": []})
        block["key_results"].append({
            "id": kr.id, "code": f"{obj.number}.{kr.number}", "title": cur.title, "baseline": cur.baseline,
            "target": cur.target, "range_min": cur.range_min, "range_max": cur.range_max, "session_id": sess.id if sess else None, "value": e.value if e else None,
            "entry_version": e.version if e else None, "percent": p, "status": status_for(p).value,
            "editable": blocker is None, "kind": cur.kind, "unit_of_measure": cur.unit_of_measure,
            "note": e.note if e else None, "round": tp.label if tp else None, "round_at": sess.scheduled_at if sess else None,
            "blocker": blocker, "previous_value": prev[0].value if prev else None,
            "previous_round": prev[1].label if prev else None})
    return list(out.values())


class ArchiveIn(BaseModel):
    reason: str


@router.post("/key-results/{kr_id}/archive", response_model=IdOut)
def archive_kr(kr_id: uuid.UUID, body: ArchiveIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    kr = db.get(KeyResult, kr_id)
    if not kr or kr.archived_at:
        raise HTTPException(404, "نتیجه کلیدی پیدا نشد")
    obj, unit_id = _unit_of_kr(db, kr)
    require(acc, "key_result", "delete", unit_id)
    require_open_cycle(db, obj.cycle_id)
    try:
        svc.archive_kr(db, kr=kr, actor_id=acc.user.id, reason=body.reason)
    except svc.ReasonRequired as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return {"id": kr.id}


@router.post("/objectives/{objective_id}/archive", response_model=IdOut)
def archive_objective(objective_id: uuid.UUID, body: ArchiveIn, db: Session = Depends(get_db),
                      acc: Access = Depends(access)):
    obj = db.get(Objective, objective_id)
    if not obj or obj.archived_at:
        raise HTTPException(404, "هدف پیدا نشد")
    require(acc, "objective", "delete", obj.unit_id)
    require_open_cycle(db, obj.cycle_id)
    try:
        svc.archive_objective(db, objective=obj, actor_id=acc.user.id, reason=body.reason)
    except svc.ReasonRequired as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return {"id": obj.id}


class ObjectivePatch(BaseModel):
    title: str | None = None
    description: str | None = None
    owner_id: uuid.UUID | None = None
    weight: float | None = None
    session_id: uuid.UUID | None = None


@router.patch("/objectives/{objective_id}", response_model=IdOut)
def patch_objective(objective_id: uuid.UUID, body: ObjectivePatch, db: Session = Depends(get_db), acc: Access = Depends(access)):
    obj = db.get(Objective, objective_id)
    if not obj:
        raise HTTPException(404, "هدف پیدا نشد")
    require(acc, "objective", "edit", obj.unit_id)
    require_open_cycle(db, obj.cycle_id)
    sess = db.get(UnitSession, body.session_id) if body.session_id else None
    try:
        svc.update_objective(db, objective=obj, actor_id=acc.user.id,
                             changes=body.model_dump(exclude={"session_id"}, exclude_unset=True),
                             context=svc.edit_context(db, obj.cycle_id, obj.unit_id, sess), session_id=sess.id if sess else None)
    except InvalidDefinition as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return {"id": obj.id}


@router.get("/units/{unit_id}/members", response_model=list[MemberOut])
def unit_members(unit_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """People who can be given a KR in this unit (members of the unit). Needs permission to create or edit KRs there."""
    if not (acc.can("key_result", "create", unit_id) or acc.can("key_result", "edit", unit_id)):
        raise HTTPException(403, "اجازهٔ تعریف KR در این واحد را ندارید")
    rows = db.execute(select(User.id, User.full_name).join(Membership, Membership.user_id == User.id)
                      .where(Membership.unit_id == unit_id, User.is_active).distinct().order_by(User.full_name)).all()
    return [{"id": i, "full_name": n} for i, n in rows]
