import asyncio
from typing import Any, cast
from uuid import UUID

from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.events.outbox import mark_publish_failure, mark_published, unpublished_events
from app.events.rabbitmq import RabbitMQEventBus


async def publish_outbox_batch() -> int:
    bus = RabbitMQEventBus()
    async with SessionLocal() as session:
        events = await unpublished_events(session)
        for stored in events:
            envelope = EventEnvelope(
                event_id=stored.id,
                event_type=stored.event_type,
                event_version=int(str(stored.payload["event_version"])),
                occurred_at=stored.occurred_at,
                aggregate_id=UUID(str(stored.payload["aggregate_id"])),
                workspace_id=stored.workspace_id,
                correlation_id=stored.correlation_id,
                payload=cast(dict[str, Any], stored.payload.get("payload", {})),
            )
            try:
                await bus.publish(envelope)
                mark_published(stored)
            except Exception:
                mark_publish_failure(stored)
        await session.commit()
        return len(events)


async def run_forever(interval_seconds: float = 1.0) -> None:
    while True:
        await publish_outbox_batch()
        await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    asyncio.run(run_forever())
