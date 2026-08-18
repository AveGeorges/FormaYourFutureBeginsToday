from urllib.parse import urlencode

from app.core.config import get_settings
from app.modules.integrations.domain import CalendarProvider, ExternalEvent


class GoogleCalendarProvider(CalendarProvider):
    provider_name = "google_calendar"

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

    async def list_events(self, connection_id: str, sync_cursor: str | None) -> list[ExternalEvent]:
        _ = connection_id, sync_cursor
        return []
