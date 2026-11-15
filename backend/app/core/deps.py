import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models.cycle import Cycle
from app.models.user import User
from app.services.access import Access

_bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> User:
    uid = decode_access_token(creds.credentials) if creds else None
    user = db.get(User, uid) if uid else None
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "نیاز به ورود", headers={"WWW-Authenticate": "Bearer"})
    return user


def access(user: User = Depends(current_user), db: Session = Depends(get_db)) -> Access:
    return Access(db, user)


def require(acc: Access, resource: str, action: str, unit_id: uuid.UUID | None) -> None:
    d = acc.decide(resource, action, unit_id)
    if not d.allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, d.reason)


CLOSED_CYCLE = "این دوره بسته است و فقط‌خواندنی است"


def require_open_cycle(db: Session, cycle_id: uuid.UUID) -> None:
    """Past (closed) cycles stay visible but nothing in them changes: definitions, values, sessions, comments."""
    c = db.get(Cycle, cycle_id)
    if c is not None and c.status == "closed":
        raise HTTPException(status.HTTP_409_CONFLICT, CLOSED_CYCLE)


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
