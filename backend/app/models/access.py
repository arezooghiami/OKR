import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class Role(Base, IdMixin, TimestampMixin):
    __tablename__ = "role"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RolePermission(Base, IdMixin):
    """One cell of the permission matrix. A missing row means 'undefined' (= denied)."""

    __tablename__ = "role_permission"
    __table_args__ = (UniqueConstraint("role_id", "resource", "action"),)

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"), index=True)
    resource: Mapped[str] = mapped_column(String(40))
    action: Mapped[str] = mapped_column(String(40))
    effect: Mapped[str] = mapped_column(String(10))  # allow | deny


class RoleScope(Base, IdMixin):
    __tablename__ = "role_scope"
    __table_args__ = (UniqueConstraint("role_id", "resource"),)

    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id", ondelete="CASCADE"), index=True)
    resource: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(20))  # unit | unit_tree | all
