"""Idempotent in-app notification event handler."""

from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.modules.notifications.infrastructure.models import Notification, WorkerReceipt


async def handle_notification_event(event: EventEnvelope, recipient_id: UUID) -> bool:
    """Persist a single in-app notification once; external delivery is a separate adapter."""
    async with SessionLocal() as session:
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "notification-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )
        if receipt is not None:
            return False
        session.add(
            Notification(
                id=uuid4(),
                workspace_id=event.workspace_id,
                user_id=recipient_id,
                notification_type=event.event_type,
                payload=event.to_dict(),
                status="delivered_in_app",
            )
        )
        session.add(
            WorkerReceipt(
                id=uuid4(),
                consumer_name="notification-worker",
                event_id=event.event_id,
                status="completed",
            )
        )
        await session.commit()
        return True
