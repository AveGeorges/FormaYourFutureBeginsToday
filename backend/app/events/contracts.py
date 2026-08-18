from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class EventEnvelope:
    event_id: UUID
    event_type: str
    event_version: int
    occurred_at: datetime
    aggregate_id: UUID
    workspace_id: UUID
    correlation_id: str
    payload: dict[str, Any]

    @classmethod
    def create(
        cls,
        *,
        event_type: str,
        aggregate_id: UUID,
        workspace_id: UUID,
        correlation_id: str,
        payload: dict[str, Any],
    ) -> "EventEnvelope":
        return cls(
            event_id=uuid4(),
            event_type=event_type,
            event_version=1,
            occurred_at=datetime.now(UTC),
            aggregate_id=aggregate_id,
            workspace_id=workspace_id,
            correlation_id=correlation_id,
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {
            **data,
            "event_id": str(self.event_id),
            "aggregate_id": str(self.aggregate_id),
            "workspace_id": str(self.workspace_id),
            "occurred_at": self.occurred_at.isoformat(),
        }
