"""Administrator data entry: units, cycles (time points and sessions), users and memberships, goals, roles."""

import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.deps import access, client_ip
from app.core.security import hash_password
from app.models import (
    Cycle,
    Membership,
    OrgVersion,
    Role,
    RolePermission,
    RoleScope,
    StrategicGoal,
    TimePoint,
    Unit,
    UnitPlacement,
    UnitSession,
    UnitType,
    User,
)
from app.routers.admin import _admin, _role_out, user_out
from app.schemas.out import (
    AdminUserOut,
    CycleAdminOut,
    GoalAdminOut,
    IdOut,
    RoleOut,
    UnitAdminOut,
    UnitTypeOut,
)
from app.services import cycles as cyc
from app.services.access import Access
from app.services.orgtree import active_org_version, load_tree

router = APIRouter(prefix="/admin", tags=["admin-data"])

USERNAME = re.compile(r"^[A-Za-z0-9_.@-]{3,60}$")


def _conflict(msg: str) -> HTTPException:
    return HTTPException(409, msg)


def _commit(db: Session, what: str = "این مقدار تکراری است") -> None:
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _conflict(what) from e


# ---- units ------------------------------------------------------------------------------------
@router.get("/unit-types", response_model=list[UnitTypeOut])
def unit_types(db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    return [{"id": t.id, "name": t.name, "color_token": t.color_token} for t in db.scalars(select(UnitType).order_by(UnitType.sort, UnitType.name))]


class UnitTypeIn(BaseModel):
    name: str
    color_token: str = "--g0"


@router.post("/unit-types", status_code=201, response_model=IdOut)
def create_unit_type(body: UnitTypeIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if not body.name.strip():
        raise HTTPException(422, "نام نوع واحد خالی است")
    t = UnitType(name=body.name.strip(), color_token=body.color_token, sort=db.scalar(select(func.count()).select_from(UnitType)) or 0)
    db.add(t)
    _commit(db, "این نوع واحد از قبل وجود دارد")
    return {"id": t.id}


def _unit_rows(db: Session) -> list[dict]:
    v = active_org_version(db)
    parents = {p.unit_id: (p.parent_unit_id, p.sort) for p in db.scalars(select(UnitPlacement).where(UnitPlacement.org_version_id == v.id))} if v else {}
    types = {t.id: t.name for t in db.scalars(select(UnitType))}
    rows = [{"id": u.id, "name": u.name, "code": u.code, "type_id": u.type_id, "type": types.get(u.type_id),
             "manager_name": u.manager_name, "parent_id": parents.get(u.id, (None, 0))[0], "archived": u.archived}
            for u in db.scalars(select(Unit)) if u.id in parents]
    order = {u.id: parents[u.id][1] for u in db.scalars(select(Unit)) if u.id in parents}
    return sorted(rows, key=lambda r: (order[r["id"]], r["name"]))


@router.get("/units", response_model=list[UnitAdminOut])
def list_units(db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    return _unit_rows(db)


class UnitIn(BaseModel):
    name: str
    code: str | None = None
    type_id: uuid.UUID | None = None
    manager_name: str | None = None
    parent_id: uuid.UUID | None = None


def _ensure_org_version(db: Session) -> OrgVersion:
    v = active_org_version(db)
    if v is None:
        v = OrgVersion(number=1, effective_from=date.today(), is_active=True, note="ساختار اولیه")
        db.add(v)
        db.flush()
    return v


@router.post("/units", status_code=201, response_model=IdOut)
def create_unit(body: UnitIn, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if not body.name.strip():
        raise HTTPException(422, "نام واحد خالی است")
    v = _ensure_org_version(db)
    tree = load_tree(db, v.id)
    if body.parent_id is not None and body.parent_id not in tree.parents:
        raise HTTPException(422, "واحد والد در ساختار فعلی نیست")
    u = Unit(name=body.name.strip(), code=body.code or None, type_id=body.type_id, manager_name=body.manager_name or None)
    db.add(u)
    db.flush()
    siblings = sum(1 for p in tree.parents.values() if p == body.parent_id)
    db.add(UnitPlacement(org_version_id=v.id, unit_id=u.id, parent_unit_id=body.parent_id, sort=siblings))
    cyc.ensure_sessions(db, unit_id=u.id)  # the new unit gets a session for every open cycle's time points
    audit.record(db, actor_id=acc.user.id, action="create", resource="unit", resource_id=u.id,
                 after={"name": u.name, "parent": str(body.parent_id) if body.parent_id else None}, ip=client_ip(request))
    _commit(db)
    return {"id": u.id}


class UnitPatch(BaseModel):
    name: str | None = None
    code: str | None = None
    type_id: uuid.UUID | None = None
    manager_name: str | None = None
    parent_id: uuid.UUID | None = None
    move: bool = False  # parent_id=None is meaningful only together with move=True
    archived: bool | None = None


@router.patch("/units/{unit_id}", response_model=IdOut)
def patch_unit(unit_id: uuid.UUID, body: UnitPatch, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    u = db.get(Unit, unit_id)
    if not u:
        raise HTTPException(404, "واحد پیدا نشد")
    before = {"name": u.name, "manager": u.manager_name, "archived": u.archived}
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(422, "نام واحد خالی است")
        u.name = body.name.strip()
    for f in ("code", "type_id", "manager_name"):
        if f in body.model_fields_set:
            setattr(u, f, getattr(body, f) or None)
    v = active_org_version(db)
    tree = load_tree(db, v.id if v else None)
    if body.move and v:
        if body.parent_id == unit_id or (body.parent_id is not None and tree.is_descendant(body.parent_id, unit_id)):
            raise HTTPException(422, "واحد را نمی‌شود زیر خودش یا زیرمجموعه‌اش برد")
        if body.parent_id is not None and body.parent_id not in tree.parents:
            raise HTTPException(422, "واحد والد در ساختار فعلی نیست")
        pl = db.scalars(select(UnitPlacement).where(UnitPlacement.org_version_id == v.id, UnitPlacement.unit_id == unit_id)).one()
        pl.parent_unit_id = body.parent_id
    if body.archived is not None:
        if body.archived and any(p == unit_id and not db.get(Unit, k).archived for k, p in tree.parents.items()):
            raise HTTPException(409, "ابتدا زیرواحدها را آرشیو یا جابه‌جا کنید")
        u.archived = body.archived
    audit.record(db, actor_id=acc.user.id, action="update", resource="unit", resource_id=u.id, before=before,
                 after={"name": u.name, "manager": u.manager_name, "archived": u.archived, "moved": body.move}, ip=client_ip(request))
    if body.archived is False:
        cyc.ensure_sessions(db, unit_id=u.id)
    db.commit()
    return {"id": u.id}


# ---- goals ------------------------------------------------------------------------------------
@router.get("/goals", response_model=list[GoalAdminOut])
def list_goals(db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    return [{"id": g.id, "title": g.title, "color": g.color_token, "active": g.active} for g in db.scalars(select(StrategicGoal).order_by(StrategicGoal.sort))]


class GoalIn(BaseModel):
    title: str
    color: str | None = None
    active: bool | None = None


@router.post("/goals", status_code=201, response_model=IdOut)
def create_goal(body: GoalIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if not body.title.strip():
        raise HTTPException(422, "عنوان هدف خالی است")
    n = db.scalar(select(func.count()).select_from(StrategicGoal)) or 0
    g = StrategicGoal(title=body.title.strip(), color_token=body.color or f"--g{n % 6}", sort=n)
    db.add(g)
    db.commit()
    return {"id": g.id}


@router.patch("/goals/{goal_id}", response_model=IdOut)
def patch_goal(goal_id: uuid.UUID, body: GoalIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    g = db.get(StrategicGoal, goal_id)
    if not g:
        raise HTTPException(404, "هدف پیدا نشد")
    if body.title is not None and body.title.strip():
        g.title = body.title.strip()
    if body.color:
        g.color_token = body.color
    if body.active is not None:
        g.active = body.active
    db.commit()
    return {"id": g.id}


# ---- cycles -----------------------------------------------------------------------------------
def _cycle_out(db: Session, c: Cycle) -> dict:
    tps = db.scalars(select(TimePoint).where(TimePoint.cycle_id == c.id).order_by(TimePoint.ordinal)).all()
    counts = dict(db.execute(select(UnitSession.status, func.count()).join(TimePoint, TimePoint.id == UnitSession.time_point_id)
                             .where(TimePoint.cycle_id == c.id).group_by(UnitSession.status)).all())
    return {"id": c.id, "name": c.name, "starts_on": c.starts_on, "ends_on": c.ends_on, "status": c.status,
            "time_points": [{"id": t.id, "label": t.label, "kind": t.kind, "ordinal": t.ordinal} for t in tps],
            "sessions_total": sum(counts.values()), "sessions_held": counts.get("held", 0),
            "sessions_unscheduled": counts.get("unscheduled", 0)}


@router.get("/cycles", response_model=list[CycleAdminOut])
def list_cycles(db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    return [_cycle_out(db, c) for c in db.scalars(select(Cycle).order_by(Cycle.starts_on.desc()))]


class TimePointIn(BaseModel):
    kind: str  # start | review | final
    label: str


class CycleIn(BaseModel):
    name: str
    starts_on: date
    ends_on: date
    time_points: list[TimePointIn] = []


@router.post("/cycles", status_code=201, response_model=CycleAdminOut)
def create_cycle(body: CycleIn, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if not body.name.strip():
        raise HTTPException(422, "نام دوره خالی است")
    if body.ends_on <= body.starts_on:
        raise HTTPException(422, "تاریخ پایان باید بعد از شروع باشد")
    c = Cycle(name=body.name.strip(), starts_on=body.starts_on, ends_on=body.ends_on, status="draft")
    db.add(c)
    db.flush()
    try:
        for tp in body.time_points:
            cyc.add_time_point(db, c, tp.kind, tp.label)
    except cyc.CycleError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    audit.record(db, actor_id=acc.user.id, action="create", resource="cycle", resource_id=c.id, after={"name": c.name}, ip=client_ip(request))
    db.commit()
    return _cycle_out(db, c)


class CyclePatch(BaseModel):
    name: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    status: str | None = None  # draft | active | closed


@router.patch("/cycles/{cycle_id}", response_model=CycleAdminOut)
def patch_cycle(cycle_id: uuid.UUID, body: CyclePatch, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    c = db.get(Cycle, cycle_id)
    if not c:
        raise HTTPException(404, "دوره پیدا نشد")
    before = {"name": c.name, "status": c.status}
    if body.name is not None and body.name.strip():
        c.name = body.name.strip()
    c.starts_on, c.ends_on = body.starts_on or c.starts_on, body.ends_on or c.ends_on
    if c.ends_on <= c.starts_on:
        raise HTTPException(422, "تاریخ پایان باید بعد از شروع باشد")
    if body.status and body.status != c.status:
        if body.status not in ("draft", "active", "closed"):
            raise HTTPException(422, "وضعیت نامعتبر است")
        if c.status == "closed":
            raise HTTPException(409, "دورهٔ بسته دوباره باز نمی‌شود")
        if body.status == "active":
            if db.scalars(select(Cycle).where(Cycle.status == "active", Cycle.id != c.id)).first():
                raise HTTPException(409, "دورهٔ فعال دیگری وجود دارد؛ ابتدا آن را ببندید")
            if not db.scalars(select(TimePoint).where(TimePoint.cycle_id == c.id)).first():
                raise HTTPException(422, "دوره نقطهٔ زمانی ندارد")
            v = active_org_version(db)
            if v is None:
                raise HTTPException(422, "ابتدا ساختار سازمان (واحدها) را تعریف کنید")
            c.org_version_id = v.id
            cyc.ensure_sessions(db, cycle_id=c.id)
        c.status = body.status
    audit.record(db, actor_id=acc.user.id, action="update", resource="cycle", resource_id=c.id, before=before,
                 after={"name": c.name, "status": c.status}, ip=client_ip(request))
    db.commit()
    return _cycle_out(db, c)


@router.post("/cycles/{cycle_id}/time-points", status_code=201, response_model=CycleAdminOut)
def add_time_point(cycle_id: uuid.UUID, body: TimePointIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    c = db.get(Cycle, cycle_id)
    if not c:
        raise HTTPException(404, "دوره پیدا نشد")
    if c.status == "closed":
        raise HTTPException(409, "دورهٔ بسته تغییر نمی‌کند")
    try:
        cyc.add_time_point(db, c, body.kind, body.label)
    except cyc.CycleError as e:
        db.rollback()
        raise HTTPException(422, str(e)) from e
    db.commit()
    return _cycle_out(db, c)


class TimePointPatch(BaseModel):
    label: str


@router.patch("/time-points/{tp_id}", response_model=CycleAdminOut)
def rename_time_point(tp_id: uuid.UUID, body: TimePointPatch, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    tp = db.get(TimePoint, tp_id)
    if not tp or not body.label.strip():
        raise HTTPException(422 if tp else 404, "برچسب خالی است" if tp else "نقطه پیدا نشد")
    if db.scalars(select(TimePoint).where(TimePoint.cycle_id == tp.cycle_id, TimePoint.label == body.label.strip(), TimePoint.id != tp.id)).first():
        raise HTTPException(409, "این برچسب در دوره تکراری است")
    tp.label = body.label.strip()
    db.commit()
    return _cycle_out(db, db.get(Cycle, tp.cycle_id))


@router.delete("/time-points/{tp_id}", response_model=CycleAdminOut)
def delete_time_point(tp_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    tp = db.get(TimePoint, tp_id)
    if not tp:
        raise HTTPException(404, "نقطه پیدا نشد")
    cycle = db.get(Cycle, tp.cycle_id)
    try:
        cyc.delete_time_point(db, tp)
    except cyc.CycleError as e:
        db.rollback()
        raise HTTPException(409, str(e)) from e
    db.commit()
    return _cycle_out(db, cycle)


# ---- users ------------------------------------------------------------------------------------
class UserIn(BaseModel):
    username: str
    full_name: str
    email: str | None = None
    password: str
    is_system_admin: bool = False


def _check_password(p: str) -> None:
    if len(p) < 8:
        raise HTTPException(422, "رمز عبور باید دست‌کم ۸ نویسه باشد")


@router.post("/users", status_code=201, response_model=AdminUserOut)
def create_user(body: UserIn, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if not USERNAME.match(body.username):
        raise HTTPException(422, "نام کاربری باید ۳ تا ۶۰ نویسهٔ انگلیسی، عدد یا . _ - @ باشد")
    if not body.full_name.strip():
        raise HTTPException(422, "نام کامل خالی است")
    _check_password(body.password)
    u = User(username=body.username, full_name=body.full_name.strip(), email=body.email or None,
             password_hash=hash_password(body.password), is_system_admin=body.is_system_admin)
    db.add(u)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise _conflict("این نام کاربری از قبل وجود دارد") from e
    audit.record(db, actor_id=acc.user.id, action="create", resource="user", resource_id=u.id,
                 after={"username": u.username, "admin": u.is_system_admin}, ip=client_ip(request))
    db.commit()
    return user_out(db, u)


class UserPatch(BaseModel):
    full_name: str | None = None
    email: str | None = None
    is_active: bool | None = None
    is_system_admin: bool | None = None
    password: str | None = None


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def patch_user(user_id: uuid.UUID, body: UserPatch, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "کاربر پیدا نشد")
    if u.id == acc.user.id and (body.is_active is False or body.is_system_admin is False):
        raise HTTPException(409, "نمی‌توانید خودتان را غیرفعال کنید یا دسترسی ادمین خود را بگیرید")
    changed = []
    if body.full_name is not None and body.full_name.strip():
        u.full_name = body.full_name.strip()
        changed.append("full_name")
    if "email" in body.model_fields_set:
        u.email = body.email or None
        changed.append("email")
    if body.is_active is not None:
        u.is_active = body.is_active
        changed.append("is_active")
    if body.is_system_admin is not None:
        u.is_system_admin = body.is_system_admin
        changed.append("is_system_admin")
    if body.password:
        _check_password(body.password)
        u.password_hash = hash_password(body.password)
        u.failed_logins, u.locked_until = 0, None
        changed.append("password")  # the value itself is never logged
    audit.record(db, actor_id=acc.user.id, action="update", resource="user", resource_id=u.id, after={"changed": changed}, ip=client_ip(request))
    db.commit()
    return user_out(db, u)


class MembershipIn(BaseModel):
    role_id: uuid.UUID
    unit_id: uuid.UUID | None = None


@router.post("/users/{user_id}/memberships", status_code=201, response_model=AdminUserOut)
def add_membership(user_id: uuid.UUID, body: MembershipIn, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    u = db.get(User, user_id)
    if not u or not db.get(Role, body.role_id) or (body.unit_id and not db.get(Unit, body.unit_id)):
        raise HTTPException(404, "کاربر، نقش یا واحد پیدا نشد")
    db.add(Membership(user_id=user_id, role_id=body.role_id, unit_id=body.unit_id))
    audit.record(db, actor_id=acc.user.id, action="grant_role", resource="user", resource_id=u.id,
                 after={"role": str(body.role_id), "unit": str(body.unit_id) if body.unit_id else None}, ip=client_ip(request))
    _commit(db, "این نقش در این واحد از قبل به کاربر داده شده است")
    return user_out(db, u)


@router.delete("/memberships/{membership_id}", response_model=AdminUserOut)
def remove_membership(membership_id: uuid.UUID, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    m = db.get(Membership, membership_id)
    if not m:
        raise HTTPException(404, "عضویت پیدا نشد")
    u = db.get(User, m.user_id)
    audit.record(db, actor_id=acc.user.id, action="revoke_role", resource="user", resource_id=u.id,
                 before={"role": str(m.role_id), "unit": str(m.unit_id) if m.unit_id else None}, ip=client_ip(request))
    db.delete(m)
    db.commit()
    return user_out(db, u)


# ---- roles ------------------------------------------------------------------------------------
class RoleIn(BaseModel):
    name: str
    description: str | None = None
    copy_from_id: uuid.UUID | None = None


@router.post("/roles", status_code=201, response_model=RoleOut)
def create_role(body: RoleIn, request: Request, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if not body.name.strip():
        raise HTTPException(422, "نام نقش خالی است")
    r = Role(name=body.name.strip(), description=body.description)
    db.add(r)
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise _conflict("نقشی با این نام وجود دارد") from e
    if body.copy_from_id:
        for p in db.scalars(select(RolePermission).where(RolePermission.role_id == body.copy_from_id)):
            db.add(RolePermission(role_id=r.id, resource=p.resource, action=p.action, effect=p.effect))
        for s in db.scalars(select(RoleScope).where(RoleScope.role_id == body.copy_from_id)):
            db.add(RoleScope(role_id=r.id, resource=s.resource, scope=s.scope))
    audit.record(db, actor_id=acc.user.id, action="create", resource="role", resource_id=r.id, after={"name": r.name}, ip=client_ip(request))
    db.commit()
    return _role_out(db, r)
