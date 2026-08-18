from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.tasks.infrastructure.models import Task


async def create_task_from_ai(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    title: str,
    priority: str,
    estimate_minutes: int,
    correlation_id: str,
) -> UUID:
    task = Task(
        id=uuid4(),
        workspace_id=workspace_id,
        title=title,
        priority=priority,
        estimate_minutes=estimate_minutes,
    )
    session.add(task)
    record_outbox_event(
        session,
        EventEnvelope.create(
            event_type="TaskCreated",
            aggregate_id=task.id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            payload={"source": "ai_plan"},
        ),
    )
    return task.id
