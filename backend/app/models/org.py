import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class UnitType(Base, IdMixin):
    __tablename__ = "unit_type"

    name: Mapped[str] = mapped_column(String(80), unique=True)
    color_token: Mapped[str] = mapped_column(String(20), default="--g0")
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Unit(Base, IdMixin, TimestampMixin):
    """Stable identity of an org unit; its place in the tree lives in UnitPlacement per OrgVersion."""

    __tablename__ = "unit"

    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    type_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit_type.id"), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class OrgVersion(Base, IdMixin, TimestampMixin):
    __tablename__ = "org_version"

    number: Mapped[int] = mapped_column(Integer, unique=True)
    effective_from: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class UnitPlacement(Base, IdMixin):
    __tablename__ = "unit_placement"
    __table_args__ = (UniqueConstraint("org_version_id", "unit_id"),)

    org_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("org_version.id"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit.id"), index=True)
    parent_unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit.id"), nullable=True, index=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Membership(Base, IdMixin):
    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("user_id", "unit_id", "role_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), index=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit.id"), nullable=True, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("role.id"))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
