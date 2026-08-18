from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.errors import DomainError
from app.modules.integrations.domain import CalendarProvider, ExternalEvent


class GoogleCalendarProvider(CalendarProvider):
    provider_name = "google_calendar"
    token_endpoint = "https://oauth2.googleapis.com/token"

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

    async def list_events(self, connection_id: str, sync_cursor: str | None) -> list[ExternalEvent]:
        _ = connection_id, sync_cursor
        return []
