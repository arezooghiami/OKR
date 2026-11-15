import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class StrategicGoal(Base, IdMixin):
    __tablename__ = "strategic_goal"

    title: Mapped[str] = mapped_column(String(300))
    color_token: Mapped[str] = mapped_column(String(20), default="--g0")
    sort: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Cycle(Base, IdMixin, TimestampMixin):
    __tablename__ = "cycle"

    name: Mapped[str] = mapped_column(String(200))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | active | closed
    org_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("org_version.id"), nullable=True)


class TimePoint(Base, IdMixin):
    __tablename__ = "time_point"
    __table_args__ = (UniqueConstraint("cycle_id", "ordinal"),)

    cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cycle.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # start | review | final
    ordinal: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(40))  # شروع / R1 / R2 / نهایی


class UnitSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "unit_session"
    __table_args__ = (UniqueConstraint("unit_id", "time_point_id"),)

    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit.id"), index=True)
    time_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("time_point.id"), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    place: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="unscheduled")  # unscheduled|scheduled|held
    held_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
