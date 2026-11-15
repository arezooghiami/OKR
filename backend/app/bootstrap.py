"""First-run setup: standard roles, unit types and one administrator. No demo data.

Usage:
    python -m app.bootstrap                      # fresh database only
    python -m app.bootstrap --reset              # wipe ALL data first
    python -m app.bootstrap --admin-username admin --admin-password '...'   (or env OKR_ADMIN_PASSWORD)
A random password is generated and printed once when none is given."""

import argparse
import os
import secrets
import sys

from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.core import audit
from app.core.db import Base, get_engine
from app.core.security import hash_password
from app.defaults import SUPER_ADMIN, install_roles, install_unit_types
from app.models import Membership, User


def wipe(db) -> None:
    db.execute(text("TRUNCATE " + ",".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables)) + " CASCADE"))


def install(db, username: str, password: str | None) -> str | None:
    """Create roles, unit types and the administrator on an empty database. Returns a generated password, if any."""
    if db.scalars(select(User)).first():
        raise SystemExit("database already has users; use --reset to wipe everything")
    generated = None
    if not password:
        password = generated = secrets.token_urlsafe(9)
    if len(password) < 8:
        raise SystemExit("password must be at least 8 characters")
    roles = install_roles(db)
    install_unit_types(db)
    admin = User(username=username, full_name="مدیر سیستم", password_hash=hash_password(password), is_system_admin=True)
    db.add(admin)
    db.flush()
    db.add(Membership(user_id=admin.id, unit_id=None, role_id=roles[SUPER_ADMIN].id))
    audit.record(db, actor_id=admin.id, action="bootstrap", resource="system", after={"admin": username})
    db.commit()
    return generated


def run(username: str, password: str | None, reset: bool) -> str | None:
    with sessionmaker(bind=get_engine())() as db:
        if reset:
            wipe(db)
            db.commit()
        return install(db, username, password)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--admin-username", default="admin")
    ap.add_argument("--admin-password", default=os.environ.get("OKR_ADMIN_PASSWORD"))
    a = ap.parse_args()
    generated = run(a.admin_username, a.admin_password, a.reset)
    print(f"ready. admin username: {a.admin_username}")
    if generated:
        print(f"generated password (shown once): {generated}")
    sys.exit(0)


if __name__ == "__main__":
    main()
