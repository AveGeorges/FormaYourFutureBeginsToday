from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_session
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.events.contracts import EventEnvelope
from app.events.outbox import record_outbox_event
from app.modules.identity.infrastructure.email_verification import parse_verification_link_token
from app.modules.identity.infrastructure.models import UserProfile, Workspace, WorkspaceMembership

router = APIRouter()


class CreateWorkspaceRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str


class UserProfileResponse(BaseModel):
    email: EmailStr
    email_verified: bool
    email_notifications_enabled: bool


class UpdateUserProfileRequest(BaseModel):
    email: EmailStr
    email_notifications_enabled: bool = True


@router.post("", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(
    payload: CreateWorkspaceRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> WorkspaceResponse:
    async def operation() -> dict[str, str]:
        workspace = Workspace(id=uuid4(), owner_id=context.user_id, name=payload.name)
        session.add(workspace)
        session.add(
            WorkspaceMembership(workspace_id=workspace.id, user_id=context.user_id, role="owner")
        )
        record_audit(
            session,
            workspace_id=workspace.id,
            actor_id=context.user_id,
            action="WorkspaceCreated",
            aggregate_type="Workspace",
            aggregate_id=workspace.id,
            correlation_id=context.correlation_id,
            details={"name": workspace.name},
        )
        return {"id": str(workspace.id), "name": workspace.name}

    return WorkspaceResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="workspaces.create",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.get("", response_model=list[WorkspaceResponse])
async def list_workspaces(
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
) -> list[WorkspaceResponse]:
    result = await session.execute(
        select(Workspace)
        .join(WorkspaceMembership)
        .where(WorkspaceMembership.user_id == context.user_id)
    )
    return [WorkspaceResponse(id=item.id, name=item.name) for item in result.scalars().all()]


@router.get("/profile", response_model=UserProfileResponse)
async def get_profile(
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
) -> UserProfileResponse:
    profile = await session.get(UserProfile, context.user_id)
    if profile is None:
        raise ValueError("User profile has not been created.")
    return UserProfileResponse(
        email=profile.email,
        email_verified=profile.email_verified_at is not None,
        email_notifications_enabled=profile.email_notifications_enabled,
    )


@router.put("/profile", response_model=UserProfileResponse)
async def update_profile(
    payload: UpdateUserProfileRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> UserProfileResponse:
    workspace = await session.scalar(select(Workspace).where(Workspace.owner_id == context.user_id))
    existing_profile = await session.get(UserProfile, context.user_id)
    email_change_requested = (
        existing_profile is None or existing_profile.email != str(payload.email)
    )
    if email_change_requested and workspace is None:
        raise ValueError("Create a workspace before creating or changing a profile email.")

    async def operation() -> dict[str, str | bool]:
        profile = await session.get(UserProfile, context.user_id)
        verification_required = False
        if profile is None:
            profile = UserProfile(user_id=context.user_id, email=str(payload.email))
            session.add(profile)
            verification_required = True
        elif profile.email != str(payload.email):
            profile.email = str(payload.email)
            profile.email_verified_at = None
            verification_required = True
        profile.email_notifications_enabled = payload.email_notifications_enabled
        if verification_required:
            assert workspace is not None
            record_audit(
                session,
                workspace_id=workspace.id,
                actor_id=context.user_id,
                action="EmailVerificationRequested",
                aggregate_type="UserProfile",
                aggregate_id=context.user_id,
                correlation_id=context.correlation_id,
                details={"delivery": "outbox_signed_link", "source": "profile_update"},
            )
            record_outbox_event(
                session,
                EventEnvelope.create(
                    event_type="EmailVerificationRequested",
                    aggregate_id=context.user_id,
                    workspace_id=workspace.id,
                    correlation_id=context.correlation_id,
                    payload={},
                ),
            )
        return {
            "email": profile.email,
            "email_verified": profile.email_verified_at is not None,
            "email_notifications_enabled": profile.email_notifications_enabled,
        }

    return UserProfileResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="identity.profile.update",
            key=idempotency_key,
            operation=operation,
        )
    )


@router.post("/profile/email-verification")
async def issue_email_verification(
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> dict[str, str]:
    profile = await session.get(UserProfile, context.user_id)
    if profile is None:
        raise ValueError("Create a user profile before requesting email verification.")
    workspace = await session.scalar(select(Workspace).where(Workspace.owner_id == context.user_id))
    if workspace is None:
        raise ValueError("Create a workspace before requesting email verification.")

    async def operation() -> dict[str, str]:
        record_audit(
            session,
            workspace_id=workspace.id,
            actor_id=context.user_id,
            action="EmailVerificationRequested",
            aggregate_type="UserProfile",
            aggregate_id=context.user_id,
            correlation_id=context.correlation_id,
            details={"delivery": "outbox_signed_link"},
        )
        record_outbox_event(
            session,
            EventEnvelope.create(
                event_type="EmailVerificationRequested",
                aggregate_id=context.user_id,
                workspace_id=workspace.id,
                correlation_id=context.correlation_id,
                payload={},
            ),
        )
        return {"status": "verification_queued"}

    return await execute_idempotent(
        session,
        user_id=context.user_id,
        scope="identity.profile.email_verification.issue",
        key=idempotency_key,
        operation=operation,
    )


@router.get("/profile/email-verification/confirm-link", response_model=UserProfileResponse)
async def confirm_email_verification_link(
    token: str = Query(min_length=32, max_length=2048),
    session: AsyncSession = Depends(get_session),
) -> UserProfileResponse:
    user_id, email = parse_verification_link_token(token)
    profile = await session.get(UserProfile, user_id)
    if profile is None or profile.email != email:
        raise ValueError("Email verification link is invalid or expired.")
    profile.email_verified_at = datetime.now(UTC)
    await session.commit()
    return UserProfileResponse(
        email=profile.email,
        email_verified=True,
        email_notifications_enabled=profile.email_notifications_enabled,
    )
