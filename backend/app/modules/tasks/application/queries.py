from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tasks.infrastructure.models import Task


async def count_open_tasks(session: AsyncSession, *, workspace_id: UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.workspace_id == workspace_id, Task.status != "done")
    )
    return count or 0


async def get_workspace_task_projection(
    session: AsyncSession, *, workspace_id: UUID
) -> list[dict[str, object]]:
    tasks = (await session.scalars(select(Task).where(Task.workspace_id == workspace_id))).all()
    return [
        {
            "id": str(item.id),
            "actionId": str(item.action_id) if item.action_id else None,
            "milestoneId": str(item.milestone_id) if item.milestone_id else None,
            "parentId": str(item.parent_id) if item.parent_id else None,
            "title": item.title,
            "priority": item.priority,
            "status": item.status,
            "estimateMinutes": item.estimate_minutes,
            "dueAt": item.due_at,
        }
        for item in tasks
    ]
