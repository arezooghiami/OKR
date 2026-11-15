import hashlib
import secrets
import uuid
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import get_settings
from app.core.db import utcnow

_ph = PasswordHasher()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _ph.verify(hashed, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID) -> str:
    s = get_settings()
    now = utcnow()
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=s.access_token_minutes), "typ": "access"}
    return jwt.encode(payload, s.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> uuid.UUID | None:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    if data.get("typ") != "access":
        return None
    try:
        return uuid.UUID(data["sub"])
    except (KeyError, ValueError):
        return None


def new_refresh_token() -> tuple[str, str]:
    """Return (opaque token for the client, sha256 hash for storage)."""
    token = secrets.token_urlsafe(48)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
