"""Idempotent calendar sync event handler; external provider state never replaces domain truth."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.modules.integrations.domain import ExternalEvent
from app.modules.integrations.infrastructure.google_calendar import GoogleCalendarProvider
from app.modules.integrations.infrastructure.models import CalendarConnection
from app.modules.integrations.infrastructure.token_cipher import decrypt_token
from app.modules.notifications.infrastructure.models import WorkerReceipt
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent, ExternalEventLink


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


async def sync_calendar_connection(event: EventEnvelope, connection_id: UUID) -> bool:
    """Import external events without replacing the normalized internal calendar truth."""
    async with SessionLocal() as session:
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "calendar-provider-sync-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )
        if receipt is not None:
            return False
        connection = await session.scalar(
            select(CalendarConnection).where(
                CalendarConnection.id == connection_id,
                CalendarConnection.workspace_id == event.workspace_id,
                CalendarConnection.provider == "google_calendar",
            )
        )
        if connection is None:
            return False
        try:
            if not connection.encrypted_access_token:
                raise RuntimeError("Google Calendar connection has no access token.")
            page = await GoogleCalendarProvider().list_events(
                decrypt_token(connection.encrypted_access_token), connection.sync_cursor
            )
            calendar = await _provider_calendar(session, connection)
            for external_event in page.events:
                await _upsert_external_event(session, calendar, external_event)
            connection.sync_cursor = page.next_sync_cursor
            connection.status = "connected"
            session.add(
                WorkerReceipt(
                    id=uuid4(),
                    consumer_name="calendar-provider-sync-worker",
                    event_id=event.event_id,
                    status="synced",
                )
            )
            await session.commit()
            return True
        except Exception:
            connection.status = "sync_failed"
            session.add(
                WorkerReceipt(
                    id=uuid4(),
                    consumer_name="calendar-provider-sync-worker",
                    event_id=event.event_id,
                    status="failed",
                )
            )
            await session.commit()
            raise


async def _provider_calendar(session: AsyncSession, connection: CalendarConnection) -> Calendar:
    calendar = await session.scalar(
        select(Calendar).where(
            Calendar.workspace_id == connection.workspace_id,
            Calendar.provider == connection.provider,
        )
    )
    if calendar is not None:
        return calendar
    calendar = Calendar(
        id=uuid4(),
        workspace_id=connection.workspace_id,
        name="Google Calendar",
        calendar_type="external",
        timezone="UTC",
        provider=connection.provider,
    )
    session.add(calendar)
    await session.flush()
    return calendar


async def _upsert_external_event(
    session: AsyncSession, calendar: Calendar, external_event: ExternalEvent
) -> None:
    link = await session.scalar(
        select(ExternalEventLink).where(
            ExternalEventLink.provider == calendar.provider,
            ExternalEventLink.external_calendar_id == external_event.calendar_id,
            ExternalEventLink.external_event_id == external_event.external_event_id,
        )
    )
    if link is None:
        calendar_event = CalendarEvent(
            id=uuid4(),
            workspace_id=calendar.workspace_id,
            calendar_id=calendar.id,
            title=external_event.title,
            starts_at=external_event.starts_at,
            ends_at=external_event.ends_at,
            status="scheduled",
        )
        session.add(calendar_event)
        session.add(
            ExternalEventLink(
                id=uuid4(),
                calendar_event_id=calendar_event.id,
                provider=calendar.provider,
                external_calendar_id=external_event.calendar_id,
                external_event_id=external_event.external_event_id,
                etag=external_event.etag,
                sync_state="synced",
                last_synced_at=datetime.now(UTC),
            )
        )
        return
    persisted_calendar_event = await session.get(CalendarEvent, link.calendar_event_id)
    if persisted_calendar_event is not None:
        persisted_calendar_event.title = external_event.title
        persisted_calendar_event.starts_at = external_event.starts_at
        persisted_calendar_event.ends_at = external_event.ends_at
    link.etag = external_event.etag
    link.sync_state = "synced"
    link.last_synced_at = datetime.now(UTC)
