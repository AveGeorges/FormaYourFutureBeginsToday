from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.events.contracts import EventEnvelope


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    workspace_id: Mapped[UUID] = mapped_column(index=True)
    correlation_id: Mapped[str] = mapped_column(String(120), index=True)
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(default=0)
    is_dead_lettered: Mapped[bool] = mapped_column(Boolean, default=False)


def record_outbox_event(session: AsyncSession, event: EventEnvelope) -> None:
    session.add(
        OutboxEvent(
            id=event.event_id,
            event_type=event.event_type,
            workspace_id=event.workspace_id,
            correlation_id=event.correlation_id,
            payload=event.to_dict(),
            occurred_at=event.occurred_at,
        )
    )


async def unpublished_events(session: AsyncSession, limit: int = 100) -> list[OutboxEvent]:
    result = await session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None), OutboxEvent.is_dead_lettered.is_(False))
        .order_by(OutboxEvent.occurred_at)
        .limit(limit)
    )
    return list(result)


def mark_published(event: OutboxEvent) -> None:
    event.published_at = datetime.now(UTC)


def mark_publish_failure(event: OutboxEvent, max_attempts: int = 5) -> None:
    event.failed_attempts = (event.failed_attempts or 0) + 1
    if event.failed_attempts >= max_attempts:
        event.is_dead_lettered = True
