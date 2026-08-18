from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_session
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.modules.identity.infrastructure.models import Workspace, WorkspaceMembership

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> WorkspaceResponse:
    async def operation() -> dict[str, str]:
        workspace = Workspace(id=uuid4(), owner_id=context.user_id, name=payload.name)
        session.add(workspace)
        session.add(
            WorkspaceMembership(workspace_id=workspace.id, user_id=context.user_id, role="owner")
        )
        record_audit(
            session,
            workspace_id=workspace.id,
            actor_id=context.user_id,
            action="WorkspaceCreated",
            aggregate_type="Workspace",
            aggregate_id=workspace.id,
            correlation_id=context.correlation_id,
            details={"name": workspace.name},
        )
        return {"id": str(workspace.id), "name": workspace.name}

    return WorkspaceResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="workspaces.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
) -> list[WorkspaceResponse]:
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == context.user_id)
    )
    return [WorkspaceResponse(id=item.id, name=item.name) for item in result.scalars().all()]
