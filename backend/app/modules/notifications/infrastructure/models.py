from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[UUID] = mapped_column(index=True)
    notification_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class AuditRecord(Base):
    __tablename__ = "audit_records"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    actor_id: Mapped[UUID] = mapped_column(index=True)
    action: Mapped[str] = mapped_column(String(120))
    aggregate_type: Mapped[str] = mapped_column(String(80))
    aggregate_id: Mapped[UUID] = mapped_column(index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), index=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class WorkerReceipt(Base):
    __tablename__ = "worker_receipts"
    __table_args__ = (UniqueConstraint("consumer_name", "event_id", name="uq_worker_receipt"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    consumer_name: Mapped[str] = mapped_column(String(100), index=True)
    event_id: Mapped[UUID] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
