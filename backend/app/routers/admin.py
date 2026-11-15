import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core import audit
from app.core.db import get_db
from app.core.deps import access, client_ip
from app.models import AuditEvent, Membership, Role, RolePermission, RoleScope, RoleUnitOverride, Unit, User
from app.schemas.out import AdminUserOut, AuditOut, RoleOut, RolesOut, SimResult, UnitOverrideOut
from app.services.access import Access
from app.services.acl import ACTIONS, RESOURCES, Scope

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin(acc: Access) -> None:
    if not acc.user.is_system_admin:
        raise HTTPException(403, "فقط سوپر ادمین")


def _role_out(db: Session, r: Role) -> dict:
    perms: dict[str, dict[str, str]] = {res: {} for res in RESOURCES}
    for p in db.scalars(select(RolePermission).where(RolePermission.role_id == r.id)):
        perms[p.resource][p.action] = p.effect
    scopes = {s.resource: s.scope for s in db.scalars(select(RoleScope).where(RoleScope.role_id == r.id))}
    users = db.scalar(select(func.count(func.distinct(Membership.user_id))).where(Membership.role_id == r.id))
    return {"id": r.id, "name": r.name, "description": r.description, "version": r.version, "users": users,
            "permissions": perms, "scopes": {res: scopes.get(res, "unit") for res in RESOURCES}}


@router.get("/roles", response_model=RolesOut)
def list_roles(db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    return {"resources": RESOURCES, "actions": ACTIONS,
            "roles": [_role_out(db, r) for r in db.scalars(select(Role).order_by(Role.name))]}


class RolePut(BaseModel):
    permissions: dict[str, dict[str, str]]  # resource -> action -> allow|deny (missing = undefined)
    scopes: dict[str, str]
    expected_version: int | None = None


@router.put("/roles/{role_id}", response_model=RoleOut)
def put_role(role_id: uuid.UUID, body: RolePut, request: Request, db: Session = Depends(get_db),
             acc: Access = Depends(access)):
    _admin(acc)
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(404, "نقش پیدا نشد")
    if body.expected_version is not None and body.expected_version != role.version:
        raise HTTPException(409, "این نقش در این فاصله تغییر کرده است")
    for res, acts in body.permissions.items():
        if res not in RESOURCES:
            raise HTTPException(422, f"منبع نامعتبر: {res}")
        for a, eff in acts.items():
            if a not in ACTIONS or eff not in ("allow", "deny"):
                raise HTTPException(422, f"مقدار نامعتبر: {res}.{a}={eff}")
    for res, sc in body.scopes.items():
        if res not in RESOURCES or sc not in {s.value for s in Scope}:
            raise HTTPException(422, f"دامنهٔ نامعتبر: {res}={sc}")
    before = _role_out(db, role)
    db.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
    db.execute(delete(RoleScope).where(RoleScope.role_id == role_id))
    for res, acts in body.permissions.items():
        for a, eff in acts.items():
            db.add(RolePermission(role_id=role_id, resource=res, action=a, effect=eff))
    for res, sc in body.scopes.items():
        db.add(RoleScope(role_id=role_id, resource=res, scope=sc))
    role.version += 1
    db.flush()
    after = _role_out(db, role)
    audit.record(db, actor_id=acc.user.id, action="update", resource="role", resource_id=role_id,
                 before=before["permissions"] | {"scopes": before["scopes"]},
                 after=after["permissions"] | {"scopes": after["scopes"]}, ip=client_ip(request))
    db.commit()
    return after


def _overrides_out(db: Session, role_id: uuid.UUID) -> list[dict]:
    by_unit: dict[uuid.UUID, dict[str, dict[str, str]]] = {}
    for o in db.scalars(select(RoleUnitOverride).where(RoleUnitOverride.role_id == role_id)):
        by_unit.setdefault(o.unit_id, {}).setdefault(o.resource, {})[o.action] = o.effect
    names = dict(db.execute(select(Unit.id, Unit.name).where(Unit.id.in_(by_unit))).all()) if by_unit else {}
    return sorted(({"unit_id": u, "unit": names.get(u, "—"), "permissions": p} for u, p in by_unit.items()),
                  key=lambda x: x["unit"])


@router.get("/roles/{role_id}/overrides", response_model=list[UnitOverrideOut])
def list_overrides(role_id: uuid.UUID, db: Session = Depends(get_db), acc: Access = Depends(access)):
    """Per-unit exceptions to this role's matrix."""
    _admin(acc)
    if not db.get(Role, role_id):
        raise HTTPException(404, "نقش پیدا نشد")
    return _overrides_out(db, role_id)


class OverridePut(BaseModel):
    permissions: dict[str, dict[str, str]]  # resource -> action -> allow|deny; empty = remove the exception


@router.put("/roles/{role_id}/overrides/{unit_id}", response_model=list[UnitOverrideOut])
def put_override(role_id: uuid.UUID, unit_id: uuid.UUID, body: OverridePut, request: Request,
                 db: Session = Depends(get_db), acc: Access = Depends(access)):
    """Replace this role's exceptions in one unit (only the super admin, docs/07 §7)."""
    _admin(acc)
    role, unit = db.get(Role, role_id), db.get(Unit, unit_id)
    if not role or not unit:
        raise HTTPException(404, "نقش یا واحد پیدا نشد")
    for res, acts in body.permissions.items():
        if res not in RESOURCES:
            raise HTTPException(422, f"منبع نامعتبر: {res}")
        for a, eff in acts.items():
            if a not in ACTIONS or eff not in ("allow", "deny"):
                raise HTTPException(422, f"مقدار نامعتبر: {res}.{a}={eff}")
    old = db.scalars(select(RoleUnitOverride).where(RoleUnitOverride.role_id == role_id,
                                                    RoleUnitOverride.unit_id == unit_id)).all()
    before = {f"{o.resource}.{o.action}": o.effect for o in old}
    db.execute(delete(RoleUnitOverride).where(RoleUnitOverride.role_id == role_id, RoleUnitOverride.unit_id == unit_id))
    after = {}
    for res, acts in body.permissions.items():
        for a, eff in acts.items():
            db.add(RoleUnitOverride(role_id=role_id, unit_id=unit_id, resource=res, action=a, effect=eff))
            after[f"{res}.{a}"] = eff
    role.version += 1
    audit.record(db, actor_id=acc.user.id, action="update_unit_override", resource="role", resource_id=role_id,
                 before={"unit": unit.name, **before}, after={"unit": unit.name, **after}, ip=client_ip(request))
    db.commit()
    return _overrides_out(db, role_id)


def user_out(db: Session, u: User) -> dict:
    ms = db.execute(
        select(Membership.id, Membership.role_id, Role.name, Membership.unit_id, Unit.name)
        .select_from(Membership).join(Role, Role.id == Membership.role_id)
        .outerjoin(Unit, Unit.id == Membership.unit_id).where(Membership.user_id == u.id)
    ).all()
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "email": u.email, "source": u.source,
            "active": u.is_active, "is_system_admin": u.is_system_admin,
            "memberships": [{"id": i, "role_id": rid, "role": r, "unit_id": uid, "unit": un} for i, rid, r, uid, un in ms]}


@router.get("/users", response_model=list[AdminUserOut])
def list_users(q: str | None = None, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    stmt = select(User).order_by(User.full_name)
    if q:
        stmt = stmt.where(User.full_name.ilike(f"%{q}%"))
    out = []
    for u in db.scalars(stmt.limit(200)):
        out.append(user_out(db, u))
    return out


class SimIn(BaseModel):
    user_id: uuid.UUID
    action: str
    resource: str
    unit_id: uuid.UUID | None = None


@router.post("/access/simulate", response_model=SimResult)
def simulate(body: SimIn, db: Session = Depends(get_db), acc: Access = Depends(access)):
    _admin(acc)
    if body.action not in ACTIONS or body.resource not in RESOURCES:
        raise HTTPException(422, "عمل یا منبع نامعتبر")
    target = db.get(User, body.user_id)
    if not target:
        raise HTTPException(404, "کاربر پیدا نشد")
    d = Access(db, target).decide(body.resource, body.action, body.unit_id)
    return {"allowed": d.allowed, "reason": d.reason, "rule": d.rule}


@router.get("/audit", response_model=AuditOut)
def audit_log(limit: int = 100, before_seq: int | None = None, db: Session = Depends(get_db),
              acc: Access = Depends(access)):
    _admin(acc)
    stmt = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(min(limit, 500))
    if before_seq:
        stmt = stmt.where(AuditEvent.seq < before_seq)
    rows = db.scalars(stmt).all()
    return {"chain_broken_at": audit.verify_chain(db),
            "events": [{"seq": e.seq, "at": e.at, "actor_id": e.actor_id, "action": e.action, "resource": e.resource,
                        "resource_id": e.resource_id, "before": e.before, "after": e.after} for e in rows]}
