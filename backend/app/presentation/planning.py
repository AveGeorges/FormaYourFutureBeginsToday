from datetime import datetime
from typing import Any
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
from app.modules.planning.infrastructure.models import Action, Dream, Goal, Milestone, Roadmap

router = APIRouter()


class CreateDreamRequest(BaseModel):
    workspace_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    visual_config: dict[str, Any] = Field(default_factory=dict)


class DreamResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    title: str
    description: str | None
    visual_config: dict[str, Any]
    status: str


class CreateGoalRequest(BaseModel):
    workspace_id: UUID
    dream_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_date: datetime | None = None


class GoalResponse(BaseModel):
    id: UUID
    dream_id: UUID
    workspace_id: UUID
    title: str
    status: str


class CreateRoadmapRequest(BaseModel):
    workspace_id: UUID
    goal_id: UUID
    title: str = Field(min_length=1, max_length=200)


class RoadmapResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    goal_id: UUID
    title: str
    status: str


class CreateMilestoneRequest(BaseModel):
    workspace_id: UUID
    roadmap_id: UUID
    title: str = Field(min_length=1, max_length=200)
    position: int = Field(default=0, ge=0)
    target_date: datetime | None = None


class MilestoneResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    roadmap_id: UUID
    title: str
    position: int
    status: str


class CreateActionRequest(BaseModel):
    workspace_id: UUID
    goal_id: UUID
    milestone_id: UUID | None = None
    title: str = Field(min_length=1, max_length=200)
    estimate_minutes: int = Field(default=0, ge=0)


class ActionResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    goal_id: UUID
    milestone_id: UUID | None
    title: str
    estimate_minutes: int
    status: str


@router.post("/dreams", response_model=DreamResponse, status_code=201)
async def create_dream(
    payload: CreateDreamRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> DreamResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)

    async def operation() -> dict[str, Any]:
        dream = Dream(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            title=payload.title,
            description=payload.description,
            visual_config=payload.visual_config,
            status="active",
        )
        session.add(dream)
        record_audit(
            session,
            workspace_id=dream.workspace_id,
            actor_id=context.user_id,
            action="DreamCreated",
            aggregate_type="Dream",
            aggregate_id=dream.id,
            correlation_id=context.correlation_id,
            details={"title": dream.title},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="DreamCreated",
                aggregate_id=dream.id,
                workspace_id=payload.workspace_id,
                correlation_id=context.correlation_id,
                payload={"title": dream.title},
            ),
        )
        return {
            "id": str(dream.id),
            "workspace_id": str(dream.workspace_id),
            "title": dream.title,
            "description": dream.description,
            "visual_config": dream.visual_config,
            "status": dream.status,
        }

    return DreamResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="dreams.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/goals", response_model=GoalResponse, status_code=201)
async def create_goal(
    payload: CreateGoalRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> GoalResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    dream = await session.scalar(
        select(Dream).where(
            Dream.id == payload.dream_id, Dream.workspace_id == payload.workspace_id
        )
    )
    if dream is None:
        raise DomainError("DREAM_NOT_FOUND", "Dream does not exist in this workspace.")

    async def operation() -> dict[str, Any]:
        goal = Goal(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            dream_id=payload.dream_id,
            title=payload.title,
            description=payload.description,
            target_date=payload.target_date,
            status="active",
        )
        session.add(goal)
        record_audit(
            session,
            workspace_id=goal.workspace_id,
            actor_id=context.user_id,
            action="GoalCreated",
            aggregate_type="Goal",
            aggregate_id=goal.id,
            correlation_id=context.correlation_id,
            details={"dream_id": str(goal.dream_id), "title": goal.title},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="GoalCreated",
                aggregate_id=goal.id,
                workspace_id=payload.workspace_id,
                correlation_id=context.correlation_id,
                payload={"dream_id": str(goal.dream_id), "title": goal.title},
            ),
        )
        return {
            "id": str(goal.id),
            "dream_id": str(goal.dream_id),
            "workspace_id": str(goal.workspace_id),
            "title": goal.title,
            "status": goal.status,
        }

    return GoalResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="goals.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/roadmaps", response_model=RoadmapResponse, status_code=201)
async def create_roadmap(
    payload: CreateRoadmapRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> RoadmapResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    goal = await session.scalar(
        select(Goal).where(Goal.id == payload.goal_id, Goal.workspace_id == payload.workspace_id)
    )
    if goal is None:
        raise DomainError("GOAL_NOT_FOUND", "Goal does not exist in this workspace.")

    async def operation() -> dict[str, Any]:
        roadmap = Roadmap(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            goal_id=payload.goal_id,
            title=payload.title,
            status="active",
        )
        session.add(roadmap)
        record_audit(
            session,
            workspace_id=roadmap.workspace_id,
            actor_id=context.user_id,
            action="RoadmapCreated",
            aggregate_type="Roadmap",
            aggregate_id=roadmap.id,
            correlation_id=context.correlation_id,
            details={"goal_id": str(roadmap.goal_id), "title": roadmap.title},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="RoadmapUpdated",
                aggregate_id=roadmap.id,
                workspace_id=roadmap.workspace_id,
                correlation_id=context.correlation_id,
                payload={"goal_id": str(roadmap.goal_id), "title": roadmap.title},
            ),
        )
        return {
            "id": str(roadmap.id),
            "workspace_id": str(roadmap.workspace_id),
            "goal_id": str(roadmap.goal_id),
            "title": roadmap.title,
            "status": roadmap.status,
        }

    return RoadmapResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="roadmaps.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/milestones", response_model=MilestoneResponse, status_code=201)
async def create_milestone(
    payload: CreateMilestoneRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> MilestoneResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    roadmap = await session.scalar(
        select(Roadmap).where(
            Roadmap.id == payload.roadmap_id, Roadmap.workspace_id == payload.workspace_id
        )
    )
    if roadmap is None:
        raise DomainError("ROADMAP_NOT_FOUND", "Roadmap does not exist in this workspace.")

    async def operation() -> dict[str, Any]:
        milestone = Milestone(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            roadmap_id=payload.roadmap_id,
            title=payload.title,
            position=payload.position,
            target_date=payload.target_date,
            status="planned",
        )
        session.add(milestone)
        record_audit(
            session,
            workspace_id=milestone.workspace_id,
            actor_id=context.user_id,
            action="MilestoneCreated",
            aggregate_type="Milestone",
            aggregate_id=milestone.id,
            correlation_id=context.correlation_id,
            details={"roadmap_id": str(milestone.roadmap_id), "title": milestone.title},
        )
        return {
            "id": str(milestone.id),
            "workspace_id": str(milestone.workspace_id),
            "roadmap_id": str(milestone.roadmap_id),
            "title": milestone.title,
            "position": milestone.position,
            "status": milestone.status,
        }

    return MilestoneResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="milestones.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/actions", response_model=ActionResponse, status_code=201)
async def create_action(
    payload: CreateActionRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> ActionResponse:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    goal = await session.scalar(
        select(Goal).where(Goal.id == payload.goal_id, Goal.workspace_id == payload.workspace_id)
    )
    if goal is None:
        raise DomainError("GOAL_NOT_FOUND", "Goal does not exist in this workspace.")
    if payload.milestone_id:
        milestone = await session.scalar(
            select(Milestone).where(
                Milestone.id == payload.milestone_id, Milestone.workspace_id == payload.workspace_id
            )
        )
        if milestone is None:
            raise DomainError("MILESTONE_NOT_FOUND", "Milestone does not exist in this workspace.")

    async def operation() -> dict[str, Any]:
        action = Action(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            goal_id=payload.goal_id,
            milestone_id=payload.milestone_id,
            title=payload.title,
            estimate_minutes=payload.estimate_minutes,
            status="planned",
        )
        session.add(action)
        record_audit(
            session,
            workspace_id=action.workspace_id,
            actor_id=context.user_id,
            action="ActionCreated",
            aggregate_type="Action",
            aggregate_id=action.id,
            correlation_id=context.correlation_id,
            details={"goal_id": str(action.goal_id), "title": action.title},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="ActionCreated",
                aggregate_id=action.id,
                workspace_id=action.workspace_id,
                correlation_id=context.correlation_id,
                payload={"goal_id": str(action.goal_id), "title": action.title},
            ),
        )
        return {
            "id": str(action.id),
            "workspace_id": str(action.workspace_id),
            "goal_id": str(action.goal_id),
            "milestone_id": str(action.milestone_id) if action.milestone_id else None,
            "title": action.title,
            "estimate_minutes": action.estimate_minutes,
            "status": action.status,
        }

    return ActionResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="actions.create",
            key=idempotency_key,
            operation=operation,
        )
    )
