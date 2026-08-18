from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent
from app.modules.tasks.application.references import get_task_title


async def project_task_to_calendar_from_ai(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    task_id: UUID,
    calendar_id: UUID,
    title: str | None,
    starts_at: datetime,
    ends_at: datetime,
    correlation_id: str,
) -> UUID:
    task_title = await get_task_title(session, task_id=task_id, workspace_id=workspace_id)
    calendar = await session.scalar(
        select(Calendar).where(Calendar.id == calendar_id, Calendar.workspace_id == workspace_id)
    )
    if calendar is None:
        raise DomainError(
            "SCHEDULING_REFERENCE_NOT_FOUND",
            "AI proposal references an unavailable task or calendar.",
        )
    if ends_at <= starts_at:
        raise DomainError(
            "INVALID_EVENT_WINDOW", "AI proposal contains an invalid calendar time range."
        )
    event = CalendarEvent(
        id=uuid4(),
        workspace_id=workspace_id,
        calendar_id=calendar_id,
        task_id=task_id,
        title=title or task_title,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    session.add(event)
    record_outbox_event(
        session,
        EventEnvelope.create(
            event_type="CalendarEventScheduled", aggregate_id=event.id,
            workspace_id=workspace_id, correlation_id=correlation_id,
            payload={"task_id": str(task_id), "source": "ai_plan"},
        ),
    )
    return event.id
