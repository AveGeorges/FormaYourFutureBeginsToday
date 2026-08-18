"""Idempotent in-app notification event handler."""

import asyncio
from uuid import UUID, uuid4

import structlog
from sqlalchemy import select

from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.modules.notifications.infrastructure.models import Notification, WorkerReceipt
from app.workers.email_delivery_worker import deliver_notification_email

logger = structlog.get_logger(__name__)


async def _deliver_notification_email_without_blocking(notification_id: UUID) -> None:
    """Run external email delivery apart from the in-app worker receipt transaction."""
    try:
        delivery_state = await deliver_notification_email(notification_id)
    except Exception:
        logger.exception(
            "notification_email_delivery_failed_unexpectedly",
            notification_id=str(notification_id),
        )
        return
    logger.info(
        "notification_email_delivery_finished",
        notification_id=str(notification_id),
        delivery_state=delivery_state,
    )


async def handle_notification_event(event: EventEnvelope, recipient_id: UUID) -> bool:
    """Persist once, then detach external email delivery after the receipt commit."""
    async with SessionLocal() as session:
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "notification-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )
        if receipt is not None:
            return False
        notification = Notification(
            id=uuid4(),
            workspace_id=event.workspace_id,
            user_id=recipient_id,
            notification_type=event.event_type,
            payload=event.to_dict(),
            status="delivered_in_app",
        )
        session.add(notification)
        session.add(
            WorkerReceipt(
                id=uuid4(),
                consumer_name="notification-worker",
                event_id=event.event_id,
                status="completed",
            )
        )
        await session.commit()
        asyncio.create_task(_deliver_notification_email_without_blocking(notification.id))
        return True
