from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.time_tracking.infrastructure.models import TimeEntry


async def get_workspace_time_entry_projection(
    session: AsyncSession, *, workspace_id: UUID
) -> list[dict[str, object]]:
    entries = (
        await session.scalars(select(TimeEntry).where(TimeEntry.workspace_id == workspace_id))
    ).all()
    return [
        {
            "id": str(item.id),
            "taskId": str(item.task_id),
            "startedAt": item.started_at,
            "endedAt": item.ended_at,
            "durationSeconds": item.duration_seconds,
            "source": item.source,
        }
        for item in entries
    ]
