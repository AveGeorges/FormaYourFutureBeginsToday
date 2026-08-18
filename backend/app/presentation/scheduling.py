from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.identity.application.permissions import require_workspace_access
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent
from app.modules.tasks.application.references import require_task_reference

router = APIRouter()


class CreateCalendarRequest(BaseModel):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=120)
    calendar_type: str = Field(default="personal", max_length=48)
    timezone: str = Field(default="UTC", max_length=64)


class CalendarResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    calendar_type: str
    timezone: str


class CreateCalendarEventRequest(BaseModel):
    workspace_id: UUID
    calendar_id: UUID
    title: str = Field(min_length=1, max_length=240)
    starts_at: datetime
    ends_at: datetime
    task_id: UUID | None = None
    action_id: UUID | None = None


class CalendarEventResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    calendar_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    status: str


class RescheduleCalendarEventRequest(BaseModel):
    workspace_id: UUID
    starts_at: datetime
    ends_at: datetime


@router.post("/calendars", response_model=CalendarResponse, status_code=201)
async def create_calendar(
    payload: CreateCalendarRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> CalendarResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)

    async def operation() -> dict[str, str]:
        calendar = Calendar(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            name=payload.name,
            calendar_type=payload.calendar_type,
            timezone=payload.timezone,
        )
        session.add(calendar)
        record_audit(
            session,
            workspace_id=calendar.workspace_id,
            actor_id=context.user_id,
            action="CalendarCreated",
            aggregate_type="Calendar",
            aggregate_id=calendar.id,
            correlation_id=context.correlation_id,
            details={"name": calendar.name, "calendar_type": calendar.calendar_type},
        )
        return {
            "id": str(calendar.id),
            "workspace_id": str(calendar.workspace_id),
            "name": calendar.name,
            "calendar_type": calendar.calendar_type,
            "timezone": calendar.timezone,
        }

    return CalendarResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="calendars.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/calendar-events", response_model=CalendarEventResponse, status_code=201)
async def create_calendar_event(
    payload: CreateCalendarEventRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> CalendarEventResponse:
    if payload.ends_at <= payload.starts_at:
        raise DomainError("INVALID_EVENT_WINDOW", "Event end must be later than event start.")
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    calendar = await session.scalar(
        select(Calendar).where(
            Calendar.id == payload.calendar_id, Calendar.workspace_id == payload.workspace_id
        )
    )
    if calendar is None:
        raise DomainError("CALENDAR_NOT_FOUND", "Calendar does not exist in this workspace.")
    await require_task_reference(
        session, task_id=payload.task_id, workspace_id=payload.workspace_id
    )

    async def operation() -> dict[str, str]:
        event = CalendarEvent(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            calendar_id=payload.calendar_id,
            task_id=payload.task_id,
            action_id=payload.action_id,
            title=payload.title,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            status="scheduled",
        )
        session.add(event)
        record_audit(
            session,
            workspace_id=event.workspace_id,
            actor_id=context.user_id,
            action="CalendarEventScheduled",
            aggregate_type="CalendarEvent",
            aggregate_id=event.id,
            correlation_id=context.correlation_id,
            details={
                "calendar_id": str(event.calendar_id),
                "task_id": str(event.task_id) if event.task_id else None,
            },
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="CalendarEventScheduled",
                aggregate_id=event.id,
                workspace_id=event.workspace_id,
                correlation_id=context.correlation_id,
                payload={
                    "task_id": str(event.task_id) if event.task_id else None,
                    "calendar_id": str(event.calendar_id),
                },
            ),
        )
        return {
            "id": str(event.id),
            "workspace_id": str(event.workspace_id),
            "calendar_id": str(event.calendar_id),
            "title": event.title,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat(),
            "status": event.status,
        }

    return CalendarEventResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="calendar-events.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.patch("/calendar-events/{event_id}", response_model=CalendarEventResponse)
async def reschedule_calendar_event(
    event_id: UUID,
    payload: RescheduleCalendarEventRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> CalendarEventResponse:
    if payload.ends_at <= payload.starts_at:
        raise DomainError("INVALID_EVENT_WINDOW", "Event end must be later than event start.")
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    event = await session.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.workspace_id == payload.workspace_id,
        )
    )
    if event is None:
        raise DomainError(
            "CALENDAR_EVENT_NOT_FOUND", "Calendar event does not exist in this workspace."
        )

    async def operation() -> dict[str, str]:
        event.starts_at = payload.starts_at
        event.ends_at = payload.ends_at
        record_audit(
            session,
            workspace_id=event.workspace_id,
            actor_id=context.user_id,
            action="CalendarEventRescheduled",
            aggregate_type="CalendarEvent",
            aggregate_id=event.id,
            correlation_id=context.correlation_id,
            details={
                "starts_at": event.starts_at.isoformat(),
                "ends_at": event.ends_at.isoformat(),
            },
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="CalendarEventRescheduled",
                aggregate_id=event.id,
                workspace_id=event.workspace_id,
                correlation_id=context.correlation_id,
                payload={
                    "starts_at": event.starts_at.isoformat(),
                    "ends_at": event.ends_at.isoformat(),
                },
            ),
        )
        return {
            "id": str(event.id),
            "workspace_id": str(event.workspace_id),
            "calendar_id": str(event.calendar_id),
            "title": event.title,
            "starts_at": event.starts_at.isoformat(),
            "ends_at": event.ends_at.isoformat(),
            "status": event.status,
        }

    return CalendarEventResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope=f"calendar-events.{event_id}.reschedule",
            key=idempotency_key,
            operation=operation,
        )
    )
