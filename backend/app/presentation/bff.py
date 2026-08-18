import json
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis_adapter import get_redis
from app.core.database import get_session
from app.core.request_context import RequestContext, get_request_context
from app.modules.identity.application.permissions import require_workspace_access
from app.modules.identity.infrastructure.models import Workspace
from app.modules.notifications.infrastructure.models import Notification
from app.modules.planning.infrastructure.models import Action, Dream, Goal, Milestone, Roadmap
from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent
from app.modules.tasks.infrastructure.models import Task
from app.modules.time_tracking.infrastructure.models import TimeEntry

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
    dreams = await session.scalar(
        select(func.count()).select_from(Dream).where(Dream.workspace_id == workspace_id)
    )
    goals = await session.scalar(
        select(func.count()).select_from(Goal).where(Goal.workspace_id == workspace_id)
    )
    tasks = await session.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.workspace_id == workspace_id, Task.status != "done")
    )
    response = WorkspaceOverview(
        workspace_id=workspace_id,
        dreams=dreams or 0,
        goals=goals or 0,
        open_tasks=tasks or 0,
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
    workspace = await session.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if workspace is None:
        raise ValueError("Workspace access was validated but workspace disappeared.")

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
    tasks = (await session.scalars(select(Task).where(Task.workspace_id == workspace_id))).all()
    calendars = (
        await session.scalars(select(Calendar).where(Calendar.workspace_id == workspace_id))
    ).all()
    events = (
        await session.scalars(
            select(CalendarEvent).where(CalendarEvent.workspace_id == workspace_id)
        )
    ).all()
    entries = (
        await session.scalars(select(TimeEntry).where(TimeEntry.workspace_id == workspace_id))
    ).all()
    notifications = (
        await session.scalars(select(Notification).where(Notification.workspace_id == workspace_id))
    ).all()

    return WorkspaceDashboard(
        workspace={"id": str(workspace.id), "name": workspace.name},
        dreams=[
            {
                "id": str(item.id),
                "title": item.title,
                "description": item.description,
                "visualConfig": item.visual_config,
                "status": item.status,
            }
            for item in dreams
        ],
        goals=[
            {
                "id": str(item.id),
                "dreamId": str(item.dream_id),
                "title": item.title,
                "status": item.status,
                "targetDate": item.target_date,
            }
            for item in goals
        ],
        roadmaps=[
            {
                "id": str(item.id),
                "goalId": str(item.goal_id),
                "title": item.title,
                "status": item.status,
            }
            for item in roadmaps
        ],
        milestones=[
            {
                "id": str(item.id),
                "roadmapId": str(item.roadmap_id),
                "title": item.title,
                "position": item.position,
                "status": item.status,
                "targetDate": item.target_date,
            }
            for item in milestones
        ],
        actions=[
            {
                "id": str(item.id),
                "goalId": str(item.goal_id),
                "milestoneId": str(item.milestone_id) if item.milestone_id else None,
                "title": item.title,
                "estimateMinutes": item.estimate_minutes,
                "status": item.status,
            }
            for item in actions
        ],
        tasks=[
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
        ],
        calendars=[
            {
                "id": str(item.id),
                "name": item.name,
                "calendarType": item.calendar_type,
                "timezone": item.timezone,
            }
            for item in calendars
        ],
        events=[
            {
                "id": str(item.id),
                "calendarId": str(item.calendar_id),
                "taskId": str(item.task_id) if item.task_id else None,
                "title": item.title,
                "startsAt": item.starts_at,
                "endsAt": item.ends_at,
                "status": item.status,
            }
            for item in events
        ],
        time_entries=[
            {
                "id": str(item.id),
                "taskId": str(item.task_id),
                "startedAt": item.started_at,
                "endedAt": item.ended_at,
                "durationSeconds": item.duration_seconds,
                "source": item.source,
            }
            for item in entries
        ],
        notifications=[
            {
                "id": str(item.id),
                "title": item.notification_type,
                "body": str(item.payload),
                "readAt": None if item.status != "read" else item.created_at,
            }
            for item in notifications
        ],
    )
