from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ExternalEvent:
    external_event_id: str
    calendar_id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    etag: str | None


class CalendarProvider(Protocol):
    provider_name: str

    def authorization_url(self, state: str) -> str: ...

    async def list_events(
        self, connection_id: str, sync_cursor: str | None
    ) -> list[ExternalEvent]: ...
