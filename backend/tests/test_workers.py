import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models_registry  # noqa: F401
from app.core.database import Base
from app.events.contracts import EventEnvelope
from app.modules.identity.infrastructure.models import Workspace
from app.modules.notifications.infrastructure.models import Notification, WorkerReceipt
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent, ExternalEventLink
from app.workers import calendar_sync_worker, notification_worker, runner


class FakeIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.ack = AsyncMock()
        self.reject = AsyncMock()


@pytest.mark.asyncio
async def test_worker_handlers_persist_once_and_deduplicate_by_consumer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(notification_worker, "SessionLocal", session_factory)
    monkeypatch.setattr(calendar_sync_worker, "SessionLocal", session_factory)
    monkeypatch.setattr(runner, "SessionLocal", session_factory)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    owner_id = uuid4()
    calendar_event_id = uuid4()
    link_id = uuid4()
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=owner_id, name="Worker test space"))
        calendar = Calendar(
            id=uuid4(),
            workspace_id=workspace_id,
            name="Internal",
            calendar_type="personal",
            timezone="UTC",
            provider="internal",
        )
        session.add(calendar)
        session.add(
            CalendarEvent(
                id=calendar_event_id,
                workspace_id=workspace_id,
                calendar_id=calendar.id,
                title="Sync me",
                starts_at=EventEnvelope.create(
                    event_type="CalendarEventScheduled",
                    aggregate_id=calendar_event_id,
                    workspace_id=workspace_id,
                    correlation_id="worker-test",
                    payload={},
                ).occurred_at,
                ends_at=EventEnvelope.create(
                    event_type="CalendarEventScheduled",
                    aggregate_id=calendar_event_id,
                    workspace_id=workspace_id,
                    correlation_id="worker-test",
                    payload={},
                ).occurred_at,
                status="scheduled",
            )
        )
        session.add(
            ExternalEventLink(
                id=link_id,
                calendar_event_id=calendar_event_id,
                provider="google_calendar",
                external_calendar_id="calendar-1",
                external_event_id="event-1",
                sync_state="pending",
            )
        )
        await session.commit()

    event = EventEnvelope.create(
        event_type="CalendarEventScheduled",
        aggregate_id=calendar_event_id,
        workspace_id=workspace_id,
        correlation_id="worker-test",
        payload={"calendar_event_id": str(calendar_event_id)},
    )

    assert await notification_worker.handle_notification_event(event, owner_id) is True
    assert await notification_worker.handle_notification_event(event, owner_id) is False
    assert await calendar_sync_worker.mark_external_event_for_sync(event, link_id) is True
    assert await calendar_sync_worker.mark_external_event_for_sync(event, link_id) is False

    async with session_factory() as session:
        notification_count = await session.scalar(select(func.count()).select_from(Notification))
        receipt_count = await session.scalar(select(func.count()).select_from(WorkerReceipt))
        link = await session.scalar(
            select(ExternalEventLink).where(ExternalEventLink.id == link_id)
        )

    assert notification_count == 1
    assert receipt_count == 2
    assert link is not None
    assert link.sync_state == "queued"

    dispatched_event = EventEnvelope.create(
        event_type="CalendarEventScheduled",
        aggregate_id=calendar_event_id,
        workspace_id=workspace_id,
        correlation_id="runner-test",
        payload={"calendar_event_id": str(calendar_event_id)},
    )
    await runner.dispatch_event(dispatched_event)
    await runner.dispatch_event(dispatched_event)
    await runner.dispatch_event(
        EventEnvelope.create(
            event_type="CalendarEventScheduled",
            aggregate_id=calendar_event_id,
            workspace_id=uuid4(),
            correlation_id="missing-workspace",
            payload={},
        )
    )

    async with session_factory() as session:
        notification_count = await session.scalar(select(func.count()).select_from(Notification))
        receipt_count = await session.scalar(select(func.count()).select_from(WorkerReceipt))

    assert notification_count == 2
    assert receipt_count == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_consumer_rejects_handler_failure_without_requeue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = EventEnvelope.create(
        event_type="TaskCreated",
        aggregate_id=uuid4(),
        workspace_id=uuid4(),
        correlation_id="consumer-failure",
        payload={},
    )
    payload = event.to_dict()
    payload["occurred_at"] = datetime.now(UTC).isoformat()
    message = FakeIncomingMessage(json.dumps(payload).encode())

    async def fail_dispatch(_: EventEnvelope) -> None:
        raise RuntimeError("worker handler failed")

    monkeypatch.setattr(runner, "dispatch_event", fail_dispatch)
    await runner.process_message(message)  # type: ignore[arg-type]

    message.ack.assert_not_awaited()
    message.reject.assert_awaited_once_with(requeue=False)
