"""Idempotent calendar sync event handler; external provider state never replaces domain truth."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.modules.notifications.infrastructure.models import WorkerReceipt
from app.modules.scheduling.infrastructure.models import ExternalEventLink


async def mark_external_event_for_sync(event: EventEnvelope, external_link_id: UUID) -> bool:
    async with SessionLocal() as session:
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "calendar-sync-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )
        if receipt is not None:
            return False
        link = await session.scalar(
            select(ExternalEventLink).where(ExternalEventLink.id == external_link_id)
        )
        if link is None:
            return False
        link.sync_state = "queued"
        link.last_synced_at = datetime.now(UTC)
        session.add(
            WorkerReceipt(
                id=uuid4(),
                consumer_name="calendar-sync-worker",
                event_id=event.event_id,
                status="queued",
            )
        )
        await session.commit()
        return True
