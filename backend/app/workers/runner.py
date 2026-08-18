import asyncio
import json
from datetime import datetime
from uuid import UUID

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.modules.identity.infrastructure.models import Workspace
from app.modules.scheduling.infrastructure.models import ExternalEventLink
from app.workers.calendar_sync_worker import mark_external_event_for_sync
from app.workers.notification_worker import handle_notification_event


def parse_event(raw: bytes) -> EventEnvelope:
    payload = json.loads(raw)
    return EventEnvelope(
        event_id=UUID(payload["event_id"]),
        event_type=payload["event_type"],
        event_version=payload["event_version"],
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
        aggregate_id=UUID(payload["aggregate_id"]),
        workspace_id=UUID(payload["workspace_id"]),
        correlation_id=payload["correlation_id"],
        payload=payload["payload"],
    )


async def dispatch_event(event: EventEnvelope) -> None:
    async with SessionLocal() as session:
        workspace = await session.scalar(
            select(Workspace).where(Workspace.id == event.workspace_id)
        )
        if workspace is None:
            return
        await handle_notification_event(event, workspace.owner_id)
        if event.event_type == "CalendarEventScheduled":
            links = await session.scalars(
                select(ExternalEventLink).where(
                    ExternalEventLink.calendar_event_id == event.aggregate_id
                )
            )
            for link in links:
                await mark_external_event_for_sync(event, link.id)


async def process_message(message: AbstractIncomingMessage) -> None:
    try:
        await dispatch_event(parse_event(message.body))
        await message.ack()
    except Exception:
        await message.reject(requeue=False)


async def run_consumer() -> None:
    connection = await aio_pika.connect_robust(get_settings().rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=20)
        exchange = await channel.declare_exchange(
            "forma.events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        dead_letter_exchange = await channel.declare_exchange(
            "forma.events.dlx", aio_pika.ExchangeType.TOPIC, durable=True
        )
        await channel.declare_queue("forma.events.dead-letter", durable=True)
        dead_letter_queue = await channel.get_queue("forma.events.dead-letter")
        await dead_letter_queue.bind(dead_letter_exchange, routing_key="#")
        queue = await channel.declare_queue(
            "forma.background-workers",
            durable=True,
            arguments={"x-dead-letter-exchange": "forma.events.dlx"},
        )
        await queue.bind(exchange, routing_key="#")

        async with queue.iterator() as iterator:
            async for message in iterator:
                await process_message(message)


if __name__ == "__main__":
    asyncio.run(run_consumer())
