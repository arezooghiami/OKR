import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class Attachment(Base, IdMixin, TimestampMixin):
    __tablename__ = "attachment"

    key_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("key_result.id"), nullable=True, index=True)
    objective_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("objective.id"), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit_session.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(300))
    storage_path: Mapped[str] = mapped_column(String(500))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    mime: Mapped[str] = mapped_column(String(120))
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"))


class Comment(Base, IdMixin, TimestampMixin):
    __tablename__ = "comment"

    key_result_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("key_result.id"), nullable=True, index=True)
    objective_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("objective.id"), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("unit_session.id"), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"))
    body: Mapped[str] = mapped_column(Text)


class Notification(Base, IdMixin):
    __tablename__ = "notification"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_account.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
