from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.modules.identity.infrastructure.models import Workspace


async def get_workspace_summary(session: AsyncSession, *, workspace_id: UUID) -> dict[str, object]:
    workspace = await session.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if workspace is None:
        raise DomainError("WORKSPACE_NOT_FOUND", "Workspace does not exist.")
    return {"id": str(workspace.id), "name": workspace.name}
