from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Calendar(Base):
    __tablename__ = "calendars"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    calendar_type: Mapped[str] = mapped_column(String(48), default="personal")
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    provider: Mapped[str] = mapped_column(String(48), default="internal")


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    calendar_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendars.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class ExternalEventLink(Base):
    __tablename__ = "external_event_links"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    calendar_event_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(48))
    external_calendar_id: Mapped[str] = mapped_column(String(255))
    external_event_id: Mapped[str] = mapped_column(String(255))
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sync_state: Mapped[str] = mapped_column(String(32), default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[str | None] = mapped_column(Text, nullable=True)
