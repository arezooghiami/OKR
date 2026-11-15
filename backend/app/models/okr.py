import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class Objective(Base, IdMixin, TimestampMixin):
    """Stable identity. Definition fields live in ObjectiveVersion (latest = current)."""

    __tablename__ = "objective"

    cycle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("cycle.id"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)  # stable, never reused within (cycle, unit)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class ObjectiveVersion(Base, IdMixin):
    __tablename__ = "objective_version"
    __table_args__ = (UniqueConstraint("objective_id", "number"),)

    objective_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("objective.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context: Mapped[str] = mapped_column(String(20))  # initial | in_session | between | after_session
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit_session.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class KeyResult(Base, IdMixin, TimestampMixin):
    __tablename__ = "key_result"

    objective_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("objective.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)  # shown as "<objective>.<number>"
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    created_in_time_point: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("time_point.id"), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class KRVersion(Base, IdMixin):
    __tablename__ = "kr_version"
    __table_args__ = (UniqueConstraint("key_result_id", "number"),)

    key_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("key_result.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="numeric")
    unit_of_measure: Mapped[str | None] = mapped_column(String(60), nullable=True)
    baseline: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    strategic_goal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategic_goal.id"), nullable=True)
    expectation: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context: Mapped[str] = mapped_column(String(20))  # initial | in_session | between | after_session
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit_session.id"), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class KRCollaborator(Base, IdMixin):
    __tablename__ = "kr_collaborator"
    __table_args__ = (UniqueConstraint("key_result_id", "unit_id"),)

    key_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("key_result.id"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit.id"))


class ReviewEntry(Base, IdMixin, TimestampMixin):
    """Monitoring value of one KR in one unit session. Not versioned as a definition; has its own history via audit."""

    __tablename__ = "review_entry"
    __table_args__ = (UniqueConstraint("key_result_id", "session_id"),)

    key_result_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("key_result.id"), index=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("unit_session.id"), index=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)  # low | medium | high
    # set when the session is marked held: freezes the definition and percent used for this round
    frozen_kr_version_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("kr_version.id"), nullable=True)
    frozen_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user_account.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Alignment(Base, IdMixin):
    """Child objective supports a parent objective (any unit). Many parents per child are allowed."""

    __tablename__ = "alignment"
    __table_args__ = (UniqueConstraint("child_id", "parent_id"),)

    child_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("objective.id"), index=True)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("objective.id"), index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
