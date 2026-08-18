from datetime import UTC, datetime
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
from app.modules.tasks.application.references import require_task_reference
from app.modules.time_tracking.infrastructure.models import TimeEntry

router = APIRouter()


class AddTimeEntryRequest(BaseModel):
    workspace_id: UUID
    task_id: UUID
    started_at: datetime
    ended_at: datetime
    source: str = Field(default="manual", pattern="^(manual|timer)$")


class TimeEntryResponse(BaseModel):
    id: UUID
    task_id: UUID
    duration_seconds: int
    source: str


class TimerRequest(BaseModel):
    workspace_id: UUID
    task_id: UUID


@router.post("/time-entries", response_model=TimeEntryResponse, status_code=201)
async def add_time_entry(
    payload: AddTimeEntryRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> TimeEntryResponse:
    if payload.ended_at <= payload.started_at:
        raise DomainError("INVALID_TIME_RANGE", "Time entry end must be later than start.")
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    await require_task_reference(
        session, task_id=payload.task_id, workspace_id=payload.workspace_id
    )

    async def operation() -> dict[str, str | int]:
        duration = int((payload.ended_at - payload.started_at).total_seconds())
        entry = TimeEntry(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            task_id=payload.task_id,
            started_at=payload.started_at,
            ended_at=payload.ended_at,
            duration_seconds=duration,
            source=payload.source,
        )
        session.add(entry)
        record_audit(
            session,
            workspace_id=entry.workspace_id,
            actor_id=context.user_id,
            action="TimeEntryRecorded",
            aggregate_type="TimeEntry",
            aggregate_id=entry.id,
            correlation_id=context.correlation_id,
            details={"task_id": str(entry.task_id), "duration_seconds": duration},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="TimeEntryRecorded",
                aggregate_id=entry.id,
                workspace_id=entry.workspace_id,
                correlation_id=context.correlation_id,
                payload={"task_id": str(entry.task_id), "duration_seconds": duration},
            ),
        )
        return {
            "id": str(entry.id),
            "task_id": str(entry.task_id),
            "duration_seconds": duration,
            "source": entry.source,
        }

    return TimeEntryResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="time-entries.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/time-entries/timer/start", response_model=TimeEntryResponse, status_code=201)
async def start_timer(
    payload: TimerRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> TimeEntryResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    await require_task_reference(
        session, task_id=payload.task_id, workspace_id=payload.workspace_id
    )

    async def operation() -> dict[str, str | int]:
        entry = TimeEntry(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            task_id=payload.task_id,
            started_at=datetime.now(UTC),
            ended_at=None,
            duration_seconds=0,
            source="timer",
        )
        session.add(entry)
        record_audit(
            session,
            workspace_id=entry.workspace_id,
            actor_id=context.user_id,
            action="TimerStarted",
            aggregate_type="TimeEntry",
            aggregate_id=entry.id,
            correlation_id=context.correlation_id,
            details={"task_id": str(entry.task_id)},
        )
        return {
            "id": str(entry.id),
            "task_id": str(entry.task_id),
            "duration_seconds": 0,
            "source": entry.source,
        }

    return TimeEntryResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope=f"time-entries.timer.{payload.task_id}.start",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/time-entries/timer/stop", response_model=TimeEntryResponse)
async def stop_timer(
    payload: TimerRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> TimeEntryResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    entry = await session.scalar(
        select(TimeEntry)
        .where(
            TimeEntry.workspace_id == payload.workspace_id,
            TimeEntry.task_id == payload.task_id,
            TimeEntry.ended_at.is_(None),
        )
        .order_by(TimeEntry.started_at.desc())
    )
    if entry is None:
        raise DomainError("RUNNING_TIMER_NOT_FOUND", "No running timer exists for this task.")

    async def operation() -> dict[str, str | int]:
        entry.ended_at = datetime.now(UTC)
        entry.duration_seconds = int((entry.ended_at - entry.started_at).total_seconds())
        record_audit(
            session,
            workspace_id=entry.workspace_id,
            actor_id=context.user_id,
            action="TimerStopped",
            aggregate_type="TimeEntry",
            aggregate_id=entry.id,
            correlation_id=context.correlation_id,
            details={"duration_seconds": entry.duration_seconds},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="TimeEntryRecorded",
                aggregate_id=entry.id,
                workspace_id=entry.workspace_id,
                correlation_id=context.correlation_id,
                payload={"task_id": str(entry.task_id), "duration_seconds": entry.duration_seconds},
            ),
        )
        return {
            "id": str(entry.id),
            "task_id": str(entry.task_id),
            "duration_seconds": entry.duration_seconds,
            "source": entry.source,
        }

    return TimeEntryResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope=f"time-entries.timer.{payload.task_id}.stop",
            key=idempotency_key,
            operation=operation,
        )
    )
