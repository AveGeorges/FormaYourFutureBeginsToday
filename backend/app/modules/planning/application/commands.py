from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.planning.infrastructure.models import Dream, Goal, Roadmap


async def create_goal_from_ai(
    session: AsyncSession, *, workspace_id: UUID, dream_id: UUID, title: str, correlation_id: str
) -> UUID:
    dream = await session.scalar(
        select(Dream).where(Dream.id == dream_id, Dream.workspace_id == workspace_id)
    )
    if dream is None:
        raise DomainError(
            "DREAM_NOT_FOUND", "AI proposal references a dream outside this workspace."
        )
    goal = Goal(id=uuid4(), workspace_id=workspace_id, dream_id=dream_id, title=title)
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
    return goal.id


async def create_roadmap_from_ai(
    session: AsyncSession, *, workspace_id: UUID, goal_id: UUID, title: str
) -> UUID:
    goal = await session.scalar(
        select(Goal).where(Goal.id == goal_id, Goal.workspace_id == workspace_id)
    )
    if goal is None:
        raise DomainError("GOAL_NOT_FOUND", "AI proposal references a goal outside this workspace.")
    roadmap = Roadmap(id=uuid4(), workspace_id=workspace_id, goal_id=goal_id, title=title)
    session.add(roadmap)
    return roadmap.id
