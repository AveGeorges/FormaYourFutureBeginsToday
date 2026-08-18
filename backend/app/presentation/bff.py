import json
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_adapter import get_redis
from app.core.database import get_session
from app.core.request_context import RequestContext, get_request_context
from app.modules.identity.application.permissions import require_workspace_access
from app.modules.identity.application.queries import get_workspace_summary
from app.modules.notifications.application.queries import get_workspace_notification_projection
from app.modules.planning.application.queries import get_workspace_planning_projection
from app.modules.scheduling.application.queries import get_workspace_scheduling_projection
from app.modules.tasks.application.queries import (
    count_open_tasks,
    get_workspace_task_projection,
)
from app.modules.time_tracking.application.queries import get_workspace_time_entry_projection

router = APIRouter()


class WorkspaceOverview(BaseModel):
    workspace_id: UUID
    dreams: int
    goals: int
    open_tasks: int


class WorkspaceDashboard(BaseModel):
    workspace: dict[str, object]
    dreams: list[dict[str, object]]
    goals: list[dict[str, object]]
    roadmaps: list[dict[str, object]]
    milestones: list[dict[str, object]]
    actions: list[dict[str, object]]
    tasks: list[dict[str, object]]
    calendars: list[dict[str, object]]
    events: list[dict[str, object]]
    time_entries: list[dict[str, object]]
    notifications: list[dict[str, object]]


@router.get("/workspaces/{workspace_id}/overview", response_model=WorkspaceOverview)
async def workspace_overview(
    workspace_id: UUID,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceOverview:
    await require_workspace_access(session, workspace_id, context.user_id)
    cache = get_redis()
    cache_key = f"forma:bff:overview:{context.user_id}:{workspace_id}"
    cached = await cache.get(cache_key)
    if cached:
        await cache.aclose()
        return WorkspaceOverview.model_validate_json(cached)
    planning = await get_workspace_planning_projection(session, workspace_id=workspace_id)
    open_tasks = await count_open_tasks(session, workspace_id=workspace_id)
    response = WorkspaceOverview(
        workspace_id=workspace_id,
        dreams=len(planning["dreams"]),
        goals=len(planning["goals"]),
        open_tasks=open_tasks,
    )
    await cache.set(cache_key, json.dumps(response.model_dump(), default=str), ex=30)
    await cache.aclose()
    return response


@router.get("/workspaces/{workspace_id}/dashboard", response_model=WorkspaceDashboard)
async def workspace_dashboard(
    workspace_id: UUID,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
) -> WorkspaceDashboard:
    await require_workspace_access(session, workspace_id, context.user_id)
    workspace = await get_workspace_summary(session, workspace_id=workspace_id)
    planning = await get_workspace_planning_projection(session, workspace_id=workspace_id)
    scheduling = await get_workspace_scheduling_projection(session, workspace_id=workspace_id)
    return WorkspaceDashboard(
        workspace=workspace,
        **planning,
        tasks=await get_workspace_task_projection(session, workspace_id=workspace_id),
        **scheduling,
        time_entries=await get_workspace_time_entry_projection(session, workspace_id=workspace_id),
        notifications=await get_workspace_notification_projection(
            session, workspace_id=workspace_id
        ),
    )
