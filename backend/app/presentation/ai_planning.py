from contextlib import suppress
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_adapter import invalidate_workspace_overview_cache, workspace_lock
from app.core.audit import record_audit
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.ai_planning.domain import ALLOWED_AI_COMMANDS
from app.modules.ai_planning.infrastructure.models import AIPlan
from app.modules.identity.application.permissions import require_workspace_access
from app.modules.planning.infrastructure.models import Dream, Goal, Roadmap
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent
from app.modules.tasks.infrastructure.models import Task

router = APIRouter()


class ProposedCommand(BaseModel):
    command: str
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str) -> str:
        if value not in ALLOWED_AI_COMMANDS:
            raise ValueError(f"Command {value} is not allowed.")
        return value


class CreateAIPlanRequest(BaseModel):
    workspace_id: UUID
    prompt: str = Field(min_length=1, max_length=6000)
    commands: list[ProposedCommand] = Field(min_length=1, max_length=20)


class AIPlanResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    status: str
    commands: list[ProposedCommand]


async def _apply_command(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    command: ProposedCommand,
    correlation_id: str,
) -> dict[str, str]:
    args = command.arguments
    if command.command == "CreateGoal":
        dream_id = UUID(str(args["dream_id"]))
        dream = await session.scalar(
            select(Dream).where(Dream.id == dream_id, Dream.workspace_id == workspace_id)
        )
        if dream is None:
            raise DomainError(
                "DREAM_NOT_FOUND", "AI proposal references a dream outside this workspace."
            )
        goal = Goal(
            id=uuid4(), workspace_id=workspace_id, dream_id=dream_id, title=str(args["title"])
        )
        session.add(goal)
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="GoalCreated",
                aggregate_id=goal.id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                payload={"dream_id": str(dream_id), "source": "ai_plan"},
            ),
        )
        return {"command": command.command, "id": str(goal.id)}

    if command.command == "CreateRoadmap":
        goal_id = UUID(str(args["goal_id"]))
        existing_goal = await session.scalar(
            select(Goal).where(Goal.id == goal_id, Goal.workspace_id == workspace_id)
        )
        if existing_goal is None:
            raise DomainError(
                "GOAL_NOT_FOUND", "AI proposal references a goal outside this workspace."
            )
        roadmap = Roadmap(
            id=uuid4(), workspace_id=workspace_id, goal_id=goal_id, title=str(args["title"])
        )
        session.add(roadmap)
        return {"command": command.command, "id": str(roadmap.id)}

    if command.command == "CreateTask":
        task = Task(
            id=uuid4(),
            workspace_id=workspace_id,
            title=str(args["title"]),
            priority=str(args.get("priority", "medium")),
            estimate_minutes=int(args.get("estimate_minutes", 0)),
        )
        session.add(task)
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="TaskCreated",
                aggregate_id=task.id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                payload={"source": "ai_plan"},
            ),
        )
        return {"command": command.command, "id": str(task.id)}

    if command.command == "ProjectTaskToCalendar":
        task_id = UUID(str(args["task_id"]))
        calendar_id = UUID(str(args["calendar_id"]))
        existing_task = await session.scalar(
            select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
        )
        calendar = await session.scalar(
            select(Calendar).where(
                Calendar.id == calendar_id, Calendar.workspace_id == workspace_id
            )
        )
        if existing_task is None or calendar is None:
            raise DomainError(
                "SCHEDULING_REFERENCE_NOT_FOUND",
                "AI proposal references an unavailable task or calendar.",
            )
        event = CalendarEvent(
            id=uuid4(),
            workspace_id=workspace_id,
            calendar_id=calendar_id,
            task_id=task_id,
            title=str(args.get("title", task.title)),
            starts_at=datetime.fromisoformat(str(args["starts_at"])),
            ends_at=datetime.fromisoformat(str(args["ends_at"])),
        )
        if event.ends_at <= event.starts_at:
            raise DomainError(
                "INVALID_EVENT_WINDOW", "AI proposal contains an invalid calendar time range."
            )
        session.add(event)
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="CalendarEventScheduled",
                aggregate_id=event.id,
                workspace_id=workspace_id,
                correlation_id=correlation_id,
                payload={"task_id": str(task_id), "source": "ai_plan"},
            ),
        )
        return {"command": command.command, "id": str(event.id)}

    # SuggestCalendarSlots is advice only. Approval records acceptance but creates no domain state.
    return {"command": "SuggestCalendarSlots", "id": "suggestion-accepted"}


@router.post("/ai/plans", response_model=AIPlanResponse, status_code=201)
async def create_ai_plan(
    payload: CreateAIPlanRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> AIPlanResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)

    async def operation() -> dict[str, Any]:
        plan = AIPlan(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            prompt=payload.prompt,
            proposal_json={"commands": [item.model_dump() for item in payload.commands]},
        )
        session.add(plan)
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="AIPlanProposed",
                aggregate_id=plan.id,
                workspace_id=plan.workspace_id,
                correlation_id=context.correlation_id,
                payload={"command_count": len(payload.commands)},
            ),
        )
        return {
            "id": str(plan.id),
            "workspace_id": str(plan.workspace_id),
            "status": plan.status,
            "commands": [item.model_dump() for item in payload.commands],
        }

    return AIPlanResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="ai-plans.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/ai/plans/{plan_id}/approve", response_model=dict[str, Any])
async def approve_ai_plan(
    plan_id: UUID,
    workspace_id: UUID,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict[str, Any]:
    await require_workspace_access(session, workspace_id, context.user_id)
    plan = await session.scalar(
        select(AIPlan).where(AIPlan.id == plan_id, AIPlan.workspace_id == workspace_id)
    )
    if plan is None:
        raise DomainError("AI_PLAN_NOT_FOUND", "AI plan does not exist in this workspace.")
    if plan.status not in {"proposed", "approved"}:
        raise DomainError("AI_PLAN_NOT_APPROVABLE", "Only a proposed AI plan can be approved.")

    async def operation() -> dict[str, Any]:
        commands = [ProposedCommand.model_validate(item) for item in plan.proposal_json["commands"]]
        applied = [
            await _apply_command(
                session,
                workspace_id=workspace_id,
                command=command,
                correlation_id=context.correlation_id,
            )
            for command in commands
        ]
        plan.status = "approved"
        plan.approved_at = datetime.now(UTC)
        plan.approval_key = idempotency_key
        record_audit(
            session,
            workspace_id=workspace_id,
            actor_id=context.user_id,
            action="AIPlanApproved",
            aggregate_type="AIPlan",
            aggregate_id=plan.id,
            correlation_id=context.correlation_id,
            details={"applied": applied},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="AIPlanApproved",
                aggregate_id=plan.id,
                workspace_id=workspace_id,
                correlation_id=context.correlation_id,
                payload={"applied": applied},
            ),
        )
        return {"plan_id": str(plan.id), "status": plan.status, "applied": applied}

    async with workspace_lock(str(workspace_id)):
        result = await execute_idempotent(
            session,
            user_id=context.user_id,
            scope=f"ai-plans.{plan_id}.approve",
            key=idempotency_key,
            operation=operation,
        )
    # Cache failure must not undo a committed, audited AI approval.
    with suppress(Exception):
        await invalidate_workspace_overview_cache(str(context.user_id), str(workspace_id))
    return result
