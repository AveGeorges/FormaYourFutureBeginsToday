from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.identity.application.permissions import require_workspace_access
from app.modules.integrations.infrastructure.google_calendar import GoogleCalendarProvider
from app.modules.integrations.infrastructure.models import CalendarConnection
from app.modules.integrations.infrastructure.token_cipher import encrypt_token

router = APIRouter()


def _oauth_state(connection: CalendarConnection) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    return jwt.encode(
        {
            "connection_id": str(connection.id),
            "workspace_id": str(connection.workspace_id),
            "owner_id": str(connection.owner_id),
            "exp": expires_at,
            "purpose": "google_calendar_oauth",
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decode_oauth_state(state: str) -> dict[str, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise DomainError(
            "CALENDAR_OAUTH_STATE_INVALID", "Google OAuth state is invalid or expired."
        ) from exc
    required = ("connection_id", "workspace_id", "owner_id")
    if payload.get("purpose") != "google_calendar_oauth" or any(
        not isinstance(payload.get(key), str) for key in required
    ):
        raise DomainError("CALENDAR_OAUTH_STATE_INVALID", "Google OAuth state has invalid claims.")
    return {key: payload[key] for key in required}


class CalendarConnectRequest(BaseModel):
    workspace_id: UUID
    provider: str = "google_calendar"


class CalendarConnectResponse(BaseModel):
    connection_id: UUID
    authorization_url: str


class CalendarSyncRequest(BaseModel):
    workspace_id: UUID
    connection_id: UUID


@router.post("/integrations/calendar/connect", response_model=CalendarConnectResponse)
async def connect_calendar(
    payload: CalendarConnectRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> CalendarConnectResponse:
    if payload.provider != "google_calendar":
        raise DomainError(
            "PROVIDER_UNSUPPORTED", "Only Google Calendar is available in iteration one."
        )
    await require_workspace_access(session, payload.workspace_id, context.user_id)

    async def operation() -> dict[str, str]:
        connection = CalendarConnection(
            id=uuid4(),
            workspace_id=payload.workspace_id,
            owner_id=context.user_id,
            provider=payload.provider,
        )
        provider = GoogleCalendarProvider()
        try:
            url = provider.authorization_url(state=_oauth_state(connection))
        except RuntimeError as exc:
            raise DomainError("CALENDAR_OAUTH_NOT_CONFIGURED", str(exc)) from exc
        session.add(connection)
        record_audit(
            session,
            workspace_id=connection.workspace_id,
            actor_id=context.user_id,
            action="CalendarOAuthStarted",
            aggregate_type="CalendarConnection",
            aggregate_id=connection.id,
            correlation_id=context.correlation_id,
            details={"provider": connection.provider},
        )
        return {"connection_id": str(connection.id), "authorization_url": url}

    return CalendarConnectResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="integrations.calendar.connect",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.get("/integrations/calendar/google/callback")
async def google_calendar_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if error:
        raise DomainError(
            "CALENDAR_OAUTH_DENIED", f"Google Calendar authorization failed: {error}."
        )
    if not code or not state:
        raise DomainError(
            "CALENDAR_OAUTH_CALLBACK_INVALID", "OAuth callback requires code and state."
        )
    claims = _decode_oauth_state(state)
    connection = await session.scalar(
        select(CalendarConnection).where(
            CalendarConnection.id == UUID(claims["connection_id"]),
            CalendarConnection.workspace_id == UUID(claims["workspace_id"]),
            CalendarConnection.owner_id == UUID(claims["owner_id"]),
            CalendarConnection.provider == "google_calendar",
        )
    )
    if connection is None:
        raise DomainError("CALENDAR_CONNECTION_NOT_FOUND", "Calendar connection no longer exists.")
    access_token, refresh_token = await GoogleCalendarProvider().exchange_code(code)
    connection.encrypted_access_token = encrypt_token(access_token)
    if refresh_token:
        connection.encrypted_refresh_token = encrypt_token(refresh_token)
    connection.status = "connected"
    record_audit(
        session,
        workspace_id=connection.workspace_id,
        actor_id=connection.owner_id,
        action="CalendarOAuthConnected",
        aggregate_type="CalendarConnection",
        aggregate_id=connection.id,
        correlation_id="google-calendar-oauth-callback",
        details={"provider": connection.provider},
    )
    await session.commit()
    return {"connection_id": str(connection.id), "status": connection.status}


@router.post("/integrations/calendar/sync")
async def sync_calendar(
    payload: CalendarSyncRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict[str, str]:
    await require_workspace_access(session, payload.workspace_id, context.user_id)
    connection = await session.scalar(
        select(CalendarConnection).where(
            CalendarConnection.id == payload.connection_id,
            CalendarConnection.workspace_id == payload.workspace_id,
        )
    )
    if connection is None:
        raise DomainError(
            "CALENDAR_CONNECTION_NOT_FOUND", "Calendar connection does not exist in this workspace."
        )
    if connection.status not in {"connected", "sync_failed"}:
        raise DomainError(
            "CALENDAR_CONNECTION_NOT_READY", "Calendar connection must be connected before sync."
        )

    async def operation() -> dict[str, str]:
        connection.status = "sync_queued"
        record_audit(
            session,
            workspace_id=connection.workspace_id,
            actor_id=context.user_id,
            action="CalendarSyncRequested",
            aggregate_type="CalendarConnection",
            aggregate_id=connection.id,
            correlation_id=context.correlation_id,
            details={"provider": connection.provider},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="CalendarSyncRequested",
                aggregate_id=connection.id,
                workspace_id=connection.workspace_id,
                correlation_id=context.correlation_id,
                payload={"provider": connection.provider},
            ),
        )
        return {"connection_id": str(connection.id), "status": connection.status}

    return await execute_idempotent(
        session,
        user_id=context.user_id,
        scope=f"integrations.calendar.{connection.id}.sync",
        key=idempotency_key,
        operation=operation,
    )
