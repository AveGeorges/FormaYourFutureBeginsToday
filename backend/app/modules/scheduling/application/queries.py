from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scheduling.infrastructure.models import Calendar, CalendarEvent


async def get_workspace_scheduling_projection(
    session: AsyncSession, *, workspace_id: UUID
) -> dict[str, list[dict[str, object]]]:
    calendars = (
        await session.scalars(select(Calendar).where(Calendar.workspace_id == workspace_id))
    ).all()
    events = (
        await session.scalars(
            select(CalendarEvent).where(CalendarEvent.workspace_id == workspace_id)
        )
    ).all()
    return {
        "calendars": [
            {
                "id": str(item.id),
                "name": item.name,
                "calendarType": item.calendar_type,
                "timezone": item.timezone,
            }
            for item in calendars
        ],
        "events": [
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
    }
