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


@dataclass(frozen=True)
class CalendarSyncPage:
    events: list[ExternalEvent]
    next_sync_cursor: str | None


class CalendarProvider(Protocol):
    provider_name: str

    def authorization_url(self, state: str) -> str: ...

    async def list_events(
        self, access_token: str, sync_cursor: str | None
    ) -> CalendarSyncPage: ...
