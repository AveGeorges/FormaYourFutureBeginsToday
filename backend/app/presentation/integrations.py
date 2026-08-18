from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_session
from app.core.errors import DomainError
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.modules.identity.application.permissions import require_workspace_access
from app.modules.integrations.infrastructure.google_calendar import GoogleCalendarProvider
from app.modules.integrations.infrastructure.models import CalendarConnection

router = APIRouter()


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
            url = provider.authorization_url(state=str(connection.id))
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

    async def operation() -> dict[str, str]:
        connection.status = "sync_queued"
        return {"connection_id": str(connection.id), "status": connection.status}

    return await execute_idempotent(
        session,
        user_id=context.user_id,
        scope=f"integrations.calendar.{connection.id}.sync",
        key=idempotency_key,
        operation=operation,
    )
