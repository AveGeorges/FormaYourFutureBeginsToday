from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.infrastructure.models import Notification


async def get_workspace_notification_projection(
    session: AsyncSession, *, workspace_id: UUID
) -> list[dict[str, object]]:
    notifications = (
        await session.scalars(select(Notification).where(Notification.workspace_id == workspace_id))
    ).all()
    return [
        {
            "id": str(item.id),
            "title": item.notification_type,
            "body": str(item.payload),
            "readAt": None if item.status != "read" else item.created_at,
        }
        for item in notifications
    ]
