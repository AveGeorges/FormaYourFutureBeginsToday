import asyncio
import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models_registry  # noqa: F401
from app.core.database import Base
from app.core.errors import DomainError
from app.events.contracts import EventEnvelope
from app.modules.identity.infrastructure.models import UserProfile, Workspace
from app.modules.integrations.domain import CalendarSyncPage, ExternalEvent
from app.modules.integrations.infrastructure.models import CalendarConnection
from app.modules.notifications.infrastructure.models import (
    EmailDeliveryAttempt,
    Notification,
    WorkerReceipt,
)
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent, ExternalEventLink
from app.workers import (
    calendar_sync_worker,
    email_delivery_worker,
    notification_worker,
    runner,
    verification_email_worker,
)


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
    deliver_email = AsyncMock(return_value="skipped_missing_profile")
    monkeypatch.setattr(notification_worker, "deliver_notification_email", deliver_email)

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
    await asyncio.sleep(0)
    deliver_email.assert_awaited_once()
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

    provider_sync = AsyncMock(return_value=True)
    monkeypatch.setattr(runner, "sync_calendar_connection", provider_sync)
    sync_request = EventEnvelope.create(
        event_type="CalendarSyncRequested",
        aggregate_id=uuid4(),
        workspace_id=workspace_id,
        correlation_id="runner-provider-sync-test",
        payload={"provider": "google_calendar"},
    )
    await runner.dispatch_event(sync_request)
    provider_sync.assert_awaited_once_with(sync_request, sync_request.aggregate_id)

    async with session_factory() as session:
        notification_count = await session.scalar(select(func.count()).select_from(Notification))
        receipt_count = await session.scalar(select(func.count()).select_from(WorkerReceipt))

    assert notification_count == 2
    assert receipt_count == 4

    await engine.dispose()


@pytest.mark.asyncio
async def test_email_delivery_worker_persists_all_profile_gated_delivery_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(email_delivery_worker, "SessionLocal", session_factory)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    recipient_id = uuid4()
    notification_id = uuid4()
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=recipient_id, name="Email test space"))
        session.add(
            Notification(
                id=notification_id,
                workspace_id=workspace_id,
                user_id=recipient_id,
                notification_type="TaskDueSoon",
                payload={"task_id": "task-1"},
                status="delivered_in_app",
            )
        )
        await session.commit()

    assert (
        await email_delivery_worker.deliver_notification_email(notification_id)
        == "skipped_missing_profile"
    )

    async with session_factory() as session:
        session.add(
            UserProfile(
                user_id=recipient_id,
                email="person@example.test",
                email_verified_at=None,
                email_notifications_enabled=True,
            )
        )
        await session.commit()

    assert (
        await email_delivery_worker.deliver_notification_email(notification_id)
        == "skipped_unverified"
    )

    async with session_factory() as session:
        profile = await session.get(UserProfile, recipient_id)
        assert profile is not None
        profile.email_verified_at = datetime.now(UTC)
        profile.email_notifications_enabled = False
        await session.commit()

    assert (
        await email_delivery_worker.deliver_notification_email(notification_id) == "skipped_opt_out"
    )

    send = AsyncMock(return_value="resend-message-1")
    monkeypatch.setattr(email_delivery_worker.ResendEmailProvider, "send", send)
    async with session_factory() as session:
        profile = await session.get(UserProfile, recipient_id)
        assert profile is not None
        profile.email_notifications_enabled = True
        await session.commit()

    assert await email_delivery_worker.deliver_notification_email(notification_id) == "delivered"
    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.kwargs == {
        "recipient": "person@example.test",
        "subject": "Forma: срок задачи приближается",
        "text": "Срок одной из ваших задач скоро наступит. Откройте Forma, чтобы уточнить "
        "следующее действие или перенести время в календаре.",
    }

    failed_notification_id = uuid4()
    async with session_factory() as session:
        session.add(
            Notification(
                id=failed_notification_id,
                workspace_id=workspace_id,
                user_id=recipient_id,
                notification_type="AiProposalReady",
                payload={"proposal_id": "proposal-1"},
                status="delivered_in_app",
            )
        )
        await session.commit()

    send.side_effect = DomainError("EMAIL_DELIVERY_FAILED", "Resend is unavailable")
    assert (
        await email_delivery_worker.deliver_notification_email(failed_notification_id) == "failed"
    )

    async with session_factory() as session:
        attempts = list(
            (
                await session.scalars(
                    select(EmailDeliveryAttempt).order_by(EmailDeliveryAttempt.created_at)
                )
            ).all()
        )

    assert [(attempt.notification_id, attempt.status) for attempt in attempts] == [
        (notification_id, "delivered"),
        (failed_notification_id, "failed"),
    ]
    assert attempts[0].provider_message_id == "resend-message-1"
    assert attempts[1].error_message == "Resend is unavailable"

    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_calendar_sync_imports_events_persists_cursor_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(calendar_sync_worker, "SessionLocal", session_factory)
    monkeypatch.setattr(calendar_sync_worker, "decrypt_token", lambda _: "google-access-token")
    lock_calls: list[tuple[str, int]] = []

    @asynccontextmanager
    async def fake_workspace_lock(workspace_id: str, ttl_seconds: int = 30):
        lock_calls.append((workspace_id, ttl_seconds))
        yield

    monkeypatch.setattr(calendar_sync_worker, "workspace_lock", fake_workspace_lock)
    list_events = AsyncMock(
        return_value=CalendarSyncPage(
            events=[
                ExternalEvent(
                    external_event_id="google-event-1",
                    calendar_id="primary",
                    title="Импортированная встреча",
                    starts_at=datetime(2026, 8, 18, 9, 0, tzinfo=UTC),
                    ends_at=datetime(2026, 8, 18, 10, 0, tzinfo=UTC),
                    etag="etag-1",
                )
            ],
            next_sync_cursor="google-sync-cursor-2",
        )
    )
    monkeypatch.setattr(calendar_sync_worker.GoogleCalendarProvider, "list_events", list_events)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    owner_id = uuid4()
    connection_id = uuid4()
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=owner_id, name="Provider sync space"))
        session.add(
            CalendarConnection(
                id=connection_id,
                workspace_id=workspace_id,
                owner_id=owner_id,
                provider="google_calendar",
                encrypted_access_token="encrypted-access-token",
                status="sync_queued",
            )
        )
        await session.commit()

    event = EventEnvelope.create(
        event_type="CalendarSyncRequested",
        aggregate_id=connection_id,
        workspace_id=workspace_id,
        correlation_id="provider-sync-test",
        payload={"provider": "google_calendar"},
    )

    assert await calendar_sync_worker.sync_calendar_connection(event, connection_id) is True
    assert await calendar_sync_worker.sync_calendar_connection(event, connection_id) is False
    list_events.assert_awaited_once_with("google-access-token", None)
    assert lock_calls == [(str(workspace_id), 30)]

    async with session_factory() as session:
        connection = await session.get(CalendarConnection, connection_id)
        calendars = list((await session.scalars(select(Calendar))).all())
        imported_events = list((await session.scalars(select(CalendarEvent))).all())
        links = list((await session.scalars(select(ExternalEventLink))).all())
        receipts = list(
            (
                await session.scalars(
                    select(WorkerReceipt).where(
                        WorkerReceipt.consumer_name == "calendar-provider-sync-worker"
                    )
                )
            ).all()
        )

    assert connection is not None
    assert connection.status == "connected"
    assert connection.sync_cursor == "google-sync-cursor-2"
    assert [(calendar.provider, calendar.name) for calendar in calendars] == [
        ("google_calendar", "Google Calendar")
    ]
    assert [(item.title, item.status) for item in imported_events] == [
        ("Импортированная встреча", "scheduled")
    ]
    assert [(link.external_event_id, link.sync_state, link.etag) for link in links] == [
        ("google-event-1", "synced", "etag-1")
    ]
    assert [receipt.status for receipt in receipts] == ["synced"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_provider_calendar_sync_persists_failed_state_before_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(calendar_sync_worker, "SessionLocal", session_factory)
    monkeypatch.setattr(calendar_sync_worker, "decrypt_token", lambda _: "google-access-token")
    monkeypatch.setattr(
        calendar_sync_worker.GoogleCalendarProvider,
        "list_events",
        AsyncMock(side_effect=DomainError("CALENDAR_SYNC_FAILED", "Google import failed")),
    )

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    owner_id = uuid4()
    connection_id = uuid4()
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=owner_id, name="Provider failure space"))
        session.add(
            CalendarConnection(
                id=connection_id,
                workspace_id=workspace_id,
                owner_id=owner_id,
                provider="google_calendar",
                encrypted_access_token="encrypted-access-token",
                status="sync_queued",
            )
        )
        await session.commit()

    event = EventEnvelope.create(
        event_type="CalendarSyncRequested",
        aggregate_id=connection_id,
        workspace_id=workspace_id,
        correlation_id="provider-sync-failure-test",
        payload={"provider": "google_calendar"},
    )
    with pytest.raises(DomainError, match="Google import failed"):
        await calendar_sync_worker.sync_calendar_connection(event, connection_id)

    async with session_factory() as session:
        connection = await session.get(CalendarConnection, connection_id)
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "calendar-provider-sync-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )

    assert connection is not None
    assert connection.status == "sync_failed"
    assert receipt is not None
    assert receipt.status == "failed"

    await engine.dispose()


@pytest.mark.parametrize(
    ("event_type", "expected_subject", "expected_text"),
    [
        (
            "TaskReminder",
            "Forma: напоминание о задаче",
            "Пора вернуться к запланированной задаче. Откройте Forma, чтобы продолжить работу "
            "или скорректировать план.",
        ),
        (
            "CalendarEventReminder",
            "Forma: напоминание о календарном блоке",
            "Скоро начнётся запланированный блок времени. Откройте Forma, чтобы проверить "
            "контекст и подготовиться к работе.",
        ),
    ],
)
def test_reminder_email_templates_are_localized_and_do_not_expose_payload(
    event_type: str,
    expected_subject: str,
    expected_text: str,
) -> None:
    notification = Notification(
        id=uuid4(),
        workspace_id=uuid4(),
        user_id=uuid4(),
        notification_type=event_type,
        payload={"private_value": "must-not-appear"},
        status="delivered_in_app",
    )

    subject, text = email_delivery_worker._notification_email_content(notification)

    assert subject == expected_subject
    assert text == expected_text
    assert "must-not-appear" not in subject
    assert "must-not-appear" not in text


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


@pytest.mark.asyncio
async def test_verification_email_worker_delivers_signed_link_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(verification_email_worker, "SessionLocal", session_factory)
    monkeypatch.setattr(
        verification_email_worker,
        "get_settings",
        lambda: SimpleNamespace(web_app_base_url="https://forma.example.test"),
    )
    send = AsyncMock(return_value="resend-verification-message")
    monkeypatch.setattr(verification_email_worker.ResendEmailProvider, "send", send)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    user_id = uuid4()
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=user_id, name="Verification email space"))
        session.add(
            UserProfile(
                user_id=user_id,
                email="person@example.com",
                email_notifications_enabled=True,
            )
        )
        await session.commit()

    event = EventEnvelope.create(
        event_type="EmailVerificationRequested",
        aggregate_id=user_id,
        workspace_id=workspace_id,
        correlation_id="verification-email-test",
        payload={},
    )
    assert await verification_email_worker.deliver_verification_email(event) is True
    assert await verification_email_worker.deliver_verification_email(event) is False
    assert send.await_count == 1
    assert send.await_args is not None
    assert send.await_args.kwargs["recipient"] == "person@example.com"
    assert "token=" in send.await_args.kwargs["text"]

    async with session_factory() as session:
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "verification-email-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )
    assert receipt is not None
    assert receipt.status == "delivered"

    await engine.dispose()
