import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import audit
from app.core.config import get_settings
from app.core.db import get_db, utcnow
from app.core.deps import access, client_ip, current_user
from app.core.security import (
    create_access_token,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, User
from app.schemas.out import RoleRef
from app.services.access import Access

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokensOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


def _issue(db: Session, user: User, family: uuid.UUID | None = None) -> TokensOut:
    s = get_settings()
    token, h = new_refresh_token()
    db.add(RefreshToken(user_id=user.id, family_id=family or uuid.uuid4(), token_hash=h,
                        expires_at=utcnow() + timedelta(days=s.refresh_token_days)))
    return TokensOut(access_token=create_access_token(user.id), refresh_token=token,
                     expires_in=s.access_token_minutes * 60)


def _bad_login() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "نام کاربری یا رمز عبور درست نیست")


@router.post("/auth/login", response_model=TokensOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    user = db.scalars(select(User).where(User.username == body.username)).first()
    if user and user.locked_until and user.locked_until > utcnow():
        raise HTTPException(status.HTTP_423_LOCKED, "حساب به‌طور موقت قفل شده است")
    ok = bool(user and user.is_active and user.source == "local" and verify_password(body.password, user.password_hash))
    if not ok:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= s.max_failed_logins:
                user.locked_until = utcnow() + timedelta(minutes=s.lockout_minutes)
                user.failed_logins = 0
        audit.record(db, actor_id=user.id if user else None, action="login_failed", resource="user",
                     resource_id=user.id if user else None, after={"username": body.username}, ip=client_ip(request))
        db.commit()
        raise _bad_login()
    user.failed_logins = 0
    audit.record(db, actor_id=user.id, action="login", resource="user", resource_id=user.id, ip=client_ip(request))
    tokens = _issue(db, user)
    db.commit()
    return tokens


@router.post("/auth/refresh", response_model=TokensOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    rt = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(body.refresh_token))).first()
    if not rt or rt.revoked or rt.expires_at < utcnow():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست منقضی شده است")
    if rt.used_at is not None:  # reuse of a rotated token: assume theft, revoke the whole family
        db.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id).values(revoked=True))
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست منقضی شده است")
    user = db.get(User, rt.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نشست منقضی شده است")
    rt.used_at = utcnow()
    tokens = _issue(db, user, rt.family_id)
    db.commit()
    return tokens


@router.post("/auth/logout", status_code=204)
def logout(body: RefreshIn, db: Session = Depends(get_db)):
    rt = db.scalars(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(body.refresh_token))).first()
    if rt:
        db.execute(update(RefreshToken).where(RefreshToken.family_id == rt.family_id).values(revoked=True))
        db.commit()


class MeOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    is_system_admin: bool
    roles: list[RoleRef]


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user), db: Session = Depends(get_db), acc: Access = Depends(access)):
    roles = [{"role": g.role, "units": sorted(g.units)} for g in acc.grants]
    return MeOut(id=user.id, username=user.username, full_name=user.full_name,
                 is_system_admin=user.is_system_admin, roles=roles)
