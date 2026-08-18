from datetime import UTC, datetime
from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.errors import DomainError
from app.modules.integrations.domain import CalendarProvider, CalendarSyncPage, ExternalEvent


class GoogleCalendarProvider(CalendarProvider):
    provider_name = "google_calendar"
    token_endpoint = "https://oauth2.googleapis.com/token"
    events_endpoint = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

    def authorization_url(self, state: str) -> str:
        settings = get_settings()
        if not settings.google_calendar_client_id or not settings.google_calendar_redirect_uri:
            raise RuntimeError("Google Calendar OAuth is not configured.")
        query = urlencode(
            {
                "client_id": settings.google_calendar_client_id,
                "redirect_uri": settings.google_calendar_redirect_uri,
                "response_type": "code",
                "scope": "https://www.googleapis.com/auth/calendar.events",
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"

    async def exchange_code(self, code: str) -> tuple[str, str | None]:
        settings = get_settings()
        if not settings.google_calendar_client_id or not settings.google_calendar_client_secret:
            raise DomainError(
                "CALENDAR_OAUTH_NOT_CONFIGURED",
                "Google Calendar OAuth client credentials are not configured.",
            )
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self.token_endpoint,
                data={
                    "code": code,
                    "client_id": settings.google_calendar_client_id,
                    "client_secret": settings.google_calendar_client_secret,
                    "redirect_uri": settings.google_calendar_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        if response.is_error:
            raise DomainError(
                "CALENDAR_OAUTH_EXCHANGE_FAILED", "Google OAuth code exchange failed."
            )
        payload = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise DomainError(
                "CALENDAR_OAUTH_EXCHANGE_FAILED", "Google OAuth returned no access token."
            )
        refresh_token = payload.get("refresh_token")
        return access_token, refresh_token if isinstance(refresh_token, str) else None

    async def list_events(
        self, access_token: str, sync_cursor: str | None
    ) -> CalendarSyncPage:
        events: list[ExternalEvent] = []
        page_token: str | None = None
        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                params: dict[str, str | int | bool] = {
                    "singleEvents": True,
                    "showDeleted": False,
                    "maxResults": 2500,
                }
                if sync_cursor:
                    params["syncToken"] = sync_cursor
                if page_token:
                    params["pageToken"] = page_token
                response = await client.get(
                    self.events_endpoint,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if response.is_error:
                    code = (
                        "CALENDAR_SYNC_CURSOR_INVALID"
                        if response.status_code == 410
                        else "CALENDAR_SYNC_FAILED"
                    )
                    raise DomainError(code, "Google Calendar events import failed.")
                payload = response.json()
                for item in payload.get("items", []):
                    if item.get("status") == "cancelled":
                        continue
                    external_event = self._to_external_event(item)
                    if external_event is not None:
                        events.append(external_event)
                page_token = payload.get("nextPageToken")
                if not isinstance(page_token, str) or not page_token:
                    next_cursor = payload.get("nextSyncToken")
                    return CalendarSyncPage(
                        events=events,
                        next_sync_cursor=(
                            next_cursor if isinstance(next_cursor, str) else sync_cursor
                        ),
                    )

    @staticmethod
    def _to_external_event(payload: object) -> ExternalEvent | None:
        if not isinstance(payload, dict):
            return None
        external_event_id = payload.get("id")
        start = GoogleCalendarProvider._parse_event_time(payload.get("start"))
        end = GoogleCalendarProvider._parse_event_time(payload.get("end"))
        if not isinstance(external_event_id, str) or not start or not end:
            return None
        etag = payload.get("etag")
        title = payload.get("summary")
        return ExternalEvent(
            external_event_id=external_event_id,
            calendar_id="primary",
            title=title if isinstance(title, str) else "Без названия",
            starts_at=start,
            ends_at=end,
            etag=etag if isinstance(etag, str) else None,
        )

    @staticmethod
    def _parse_event_time(value: object) -> datetime | None:
        if not isinstance(value, dict):
            return None
        raw = value.get("dateTime") or value.get("date")
        if not isinstance(raw, str):
            return None
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
