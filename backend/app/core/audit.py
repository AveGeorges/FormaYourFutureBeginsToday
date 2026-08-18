from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.notifications.infrastructure.models import AuditRecord


def record_audit(
    session: AsyncSession,
    *,
    workspace_id: UUID,
    actor_id: UUID,
    action: str,
    aggregate_type: str,
    aggregate_id: UUID,
    correlation_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditRecord(
            id=uuid4(),
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            correlation_id=correlation_id,
            details=str(details or {}),
        )
    )
