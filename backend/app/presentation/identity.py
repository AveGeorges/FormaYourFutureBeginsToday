from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_session
from app.core.idempotency import execute_idempotent, require_idempotency_key
from app.core.request_context import RequestContext, get_request_context
from app.modules.identity.infrastructure.models import (
    EmailVerificationToken,
    UserProfile,
    Workspace,
    WorkspaceMembership,
)

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


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


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
    async def operation() -> dict[str, str | bool]:
        profile = await session.get(UserProfile, context.user_id)
        if profile is None:
            profile = UserProfile(user_id=context.user_id, email=str(payload.email))
            session.add(profile)
        elif profile.email != str(payload.email):
            profile.email = str(payload.email)
            profile.email_verified_at = None
        profile.email_notifications_enabled = payload.email_notifications_enabled
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

    async def operation() -> dict[str, str]:
        raw_token = token_urlsafe(32)
        session.add(
            EmailVerificationToken(
                id=uuid4(),
                user_id=context.user_id,
                token_hash=sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + timedelta(hours=24),
            )
        )
        # The raw token is intentionally not returned. The external email adapter will deliver it.
        return {"status": "verification_queued"}

    return await execute_idempotent(
        session,
        user_id=context.user_id,
        scope="identity.profile.email_verification.issue",
        key=idempotency_key,
        operation=operation,
    )


@router.post("/profile/email-verification/confirm", response_model=UserProfileResponse)
async def confirm_email_verification(
    payload: VerifyEmailRequest,
    context: RequestContext = Depends(get_request_context),
    session: AsyncSession = Depends(get_session),
    idempotency_key: str = Depends(require_idempotency_key),
) -> UserProfileResponse:
    async def operation() -> dict[str, str | bool]:
        token = await session.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == context.user_id,
                EmailVerificationToken.token_hash == sha256(payload.token.encode()).hexdigest(),
                EmailVerificationToken.consumed_at.is_(None),
                EmailVerificationToken.expires_at > datetime.now(UTC),
            )
        )
        profile = await session.get(UserProfile, context.user_id)
        if token is None or profile is None:
            raise ValueError("Email verification token is invalid or expired.")
        token.consumed_at = datetime.now(UTC)
        profile.email_verified_at = datetime.now(UTC)
        return {
            "email": profile.email,
            "email_verified": True,
            "email_notifications_enabled": profile.email_notifications_enabled,
        }

    return UserProfileResponse(
        **await execute_idempotent(
            session,
            user_id=context.user_id,
            scope="identity.profile.email_verification.confirm",
            key=idempotency_key,
            operation=operation,
        )
    )
