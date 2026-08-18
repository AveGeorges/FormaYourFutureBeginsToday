from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.planning.infrastructure.models import Action, Dream, Goal, Milestone, Roadmap


async def get_workspace_planning_projection(
    session: AsyncSession, *, workspace_id: UUID
) -> dict[str, list[dict[str, object]]]:
    dreams = (await session.scalars(select(Dream).where(Dream.workspace_id == workspace_id))).all()
    goals = (await session.scalars(select(Goal).where(Goal.workspace_id == workspace_id))).all()
    roadmaps = (
        await session.scalars(select(Roadmap).where(Roadmap.workspace_id == workspace_id))
    ).all()
    milestones = (
        await session.scalars(select(Milestone).where(Milestone.workspace_id == workspace_id))
    ).all()
    actions = (
        await session.scalars(select(Action).where(Action.workspace_id == workspace_id))
    ).all()
    return {
        "dreams": [
            {"id": str(item.id), "title": item.title, "description": item.description,
             "visualConfig": item.visual_config, "status": item.status}
            for item in dreams
        ],
        "goals": [
            {"id": str(item.id), "dreamId": str(item.dream_id), "title": item.title,
             "status": item.status, "targetDate": item.target_date}
            for item in goals
        ],
        "roadmaps": [
            {"id": str(item.id), "goalId": str(item.goal_id), "title": item.title,
             "status": item.status}
            for item in roadmaps
        ],
        "milestones": [
            {"id": str(item.id), "roadmapId": str(item.roadmap_id), "title": item.title,
             "position": item.position, "status": item.status, "targetDate": item.target_date}
            for item in milestones
        ],
        "actions": [
            {"id": str(item.id), "goalId": str(item.goal_id),
             "milestoneId": str(item.milestone_id) if item.milestone_id else None,
             "title": item.title, "estimateMinutes": item.estimate_minutes, "status": item.status}
            for item in actions
        ],
    }
