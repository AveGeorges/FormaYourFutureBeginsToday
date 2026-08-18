from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.modules.identity.infrastructure.models import WorkspaceMembership


async def require_workspace_access(
    session: AsyncSession, workspace_id: UUID, user_id: UUID
) -> None:
    membership = await session.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.user_id == user_id,
        )
    )
    if membership is None:
        raise DomainError("WORKSPACE_FORBIDDEN", "You do not have access to this workspace.")
