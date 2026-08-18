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
from app.modules.planning.infrastructure.models import Action, Milestone
from app.modules.tasks.infrastructure.models import Task

router = APIRouter()


class CreateTaskRequest(BaseModel):
    workspace_id: UUID
    title: str = Field(min_length=1, max_length=240)
    priority: str = Field(default="medium", pattern="^(low|medium|high|critical)$")
    estimate_minutes: int = Field(default=0, ge=0)
    due_at: datetime | None = None
    action_id: UUID | None = None
    milestone_id: UUID | None = None
    parent_id: UUID | None = None


class TaskResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    priority: str
    status: str
    estimate_minutes: int
    due_at: datetime | None


class UpdateTaskStatusRequest(BaseModel):
    workspace_id: UUID
    status: str = Field(pattern="^(todo|in_progress|done)$")


async def _require_owned_link(
    session: AsyncSession,
    model: type[Action] | type[Milestone] | type[Task],
    item_id: UUID | None,
    workspace_id: UUID,
    code: str,
) -> None:
    if item_id is None:
        return
    item = await session.scalar(
        select(model).where(model.id == item_id, model.workspace_id == workspace_id)
    )
    if item is None:
        raise DomainError(code, "Linked object does not exist in this workspace.")


@router.post("/tasks", response_model=TaskResponse, status_code=201)
async def create_task(
    payload: CreateTaskRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> TaskResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    await _require_owned_link(
        session, Action, payload.action_id, payload.workspace_id, "ACTION_NOT_FOUND"
    )
    await _require_owned_link(
        session, Milestone, payload.milestone_id, payload.workspace_id, "MILESTONE_NOT_FOUND"
    )
    await _require_owned_link(
        session, Task, payload.parent_id, payload.workspace_id, "PARENT_TASK_NOT_FOUND"
    )

    async def operation() -> dict[str, str | int | None]:
        task = Task(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            title=payload.title,
            priority=payload.priority,
            estimate_minutes=payload.estimate_minutes,
            due_at=payload.due_at,
            action_id=payload.action_id,
            milestone_id=payload.milestone_id,
            parent_id=payload.parent_id,
        )
        session.add(task)
        record_audit(
            session,
            workspace_id=task.workspace_id,
            actor_id=context.user_id,
            action="TaskCreated",
            aggregate_type="Task",
            aggregate_id=task.id,
            correlation_id=context.correlation_id,
            details={"title": task.title, "priority": task.priority},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="TaskCreated",
                aggregate_id=task.id,
                workspace_id=task.workspace_id,
                correlation_id=context.correlation_id,
                payload={
                    "title": task.title,
                    "action_id": str(task.action_id) if task.action_id else None,
                },
            ),
        )
        return {
            "id": str(task.id),
            "workspace_id": str(task.workspace_id),
            "title": task.title,
            "priority": task.priority,
            "status": task.status,
            "estimate_minutes": task.estimate_minutes,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }

    return TaskResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="tasks.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: UUID,
    payload: UpdateTaskStatusRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> TaskResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    task = await session.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == payload.workspace_id)
    )
    if task is None:
        raise DomainError("TASK_NOT_FOUND", "Task does not exist in this workspace.")

    async def operation() -> dict[str, str | int | None]:
        task.status = payload.status
        record_audit(
            session,
            workspace_id=task.workspace_id,
            actor_id=context.user_id,
            action="TaskStatusUpdated",
            aggregate_type="Task",
            aggregate_id=task.id,
            correlation_id=context.correlation_id,
            details={"status": task.status},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="TaskStatusUpdated",
                aggregate_id=task.id,
                workspace_id=task.workspace_id,
                correlation_id=context.correlation_id,
                payload={"status": task.status},
            ),
        )
        return {
            "id": str(task.id),
            "workspace_id": str(task.workspace_id),
            "title": task.title,
            "priority": task.priority,
            "status": task.status,
            "estimate_minutes": task.estimate_minutes,
            "due_at": task.due_at.isoformat() if task.due_at else None,
        }

    return TaskResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope=f"tasks.{task_id}.status",
            key=idempotency_key,
            operation=operation,
        )
    )
