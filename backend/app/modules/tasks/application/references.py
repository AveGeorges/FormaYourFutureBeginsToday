from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.modules.tasks.infrastructure.models import Task


async def require_task_reference(
    session: AsyncSession,
    *,
    task_id: UUID | None,
    workspace_id: UUID,
    not_found_code: str = "TASK_NOT_FOUND",
) -> None:
    if task_id is None:
        return
    task = await session.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
    )
    if task is None:
        raise DomainError(not_found_code, "Linked object does not exist in this workspace.")


async def get_task_title(session: AsyncSession, *, task_id: UUID, workspace_id: UUID) -> str:
    task = await session.scalar(
        select(Task).where(Task.id == task_id, Task.workspace_id == workspace_id)
    )
    if task is None:
        raise DomainError("TASK_NOT_FOUND", "Task does not exist in this workspace.")
    return task.title
