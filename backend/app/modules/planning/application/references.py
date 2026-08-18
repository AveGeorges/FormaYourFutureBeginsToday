from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.modules.planning.infrastructure.models import Action, Milestone


async def require_action_reference(
    session: AsyncSession, *, action_id: UUID | None, workspace_id: UUID
) -> None:
    if action_id is None:
        return
    action = await session.scalar(
        select(Action).where(Action.id == action_id, Action.workspace_id == workspace_id)
    )
    if action is None:
        raise DomainError("ACTION_NOT_FOUND", "Linked object does not exist in this workspace.")


async def require_milestone_reference(
    session: AsyncSession, *, milestone_id: UUID | None, workspace_id: UUID
) -> None:
    if milestone_id is None:
        return
    milestone = await session.scalar(
        select(Milestone).where(
            Milestone.id == milestone_id, Milestone.workspace_id == workspace_id
        )
    )
    if milestone is None:
        raise DomainError("MILESTONE_NOT_FOUND", "Linked object does not exist in this workspace.")
