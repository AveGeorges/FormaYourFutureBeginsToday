from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request

import app.models_registry  # noqa: F401
from app.cache import redis_adapter
from app.core.config import get_settings
from app.core.database import Base
from app.core.errors import DomainError
from app.core.request_context import get_request_context
from app.events.outbox import OutboxEvent, mark_publish_failure
from app.main import create_app
from app.modules.ai_planning.domain import ALLOWED_AI_COMMANDS
from app.modules.ai_planning.infrastructure.models import AIPlan
from app.modules.identity.infrastructure import email_verification
from app.modules.identity.infrastructure.models import (
    EmailVerificationToken,
    UserProfile,
    Workspace,
)
from app.modules.integrations.infrastructure import token_cipher
from app.modules.integrations.infrastructure.models import CalendarConnection
from app.presentation import ai_planning, bff, identity, integrations
from app.presentation.integrations import _oauth_state


def test_health_contract() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "forma-api"}


def test_fastapi_serves_spa_assets_and_falls_back_without_intercepting_api_routes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (tmp_path / "index.html").write_text("<main>Forma SPA</main>", encoding="utf-8")
    (assets_dir / "forma.js").write_text("console.log('forma');", encoding="utf-8")
    monkeypatch.setenv("FORMA_WEB_STATIC_DIR", str(tmp_path))
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())

        asset_response = client.get("/assets/forma.js")
        fallback_response = client.get("/calendar/2026-08-18")
        api_response = client.get("/api/v1/not-a-route")

        assert asset_response.status_code == 200
        assert asset_response.text == "console.log('forma');"
        assert asset_response.headers["cache-control"] == "public, max-age=31536000, immutable"
        assert fallback_response.status_code == 200
        assert fallback_response.text == "<main>Forma SPA</main>"
        assert api_response.status_code == 404
        assert api_response.json() == {"detail": "Not Found"}
    finally:
        get_settings.cache_clear()


def test_rest_contract_exposes_required_vertical_slice_routes() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]
    assert "/api/v1/workspaces" in paths
    assert "/api/v1/dreams" in paths
    assert "/api/v1/goals" in paths
    assert "/api/v1/tasks" in paths
    assert "/api/v1/calendars" in paths
    assert "/api/v1/calendar-events" in paths
    assert "/api/v1/time-entries" in paths


def test_ai_command_allow_list_has_only_user_approved_commands() -> None:
    assert {
        "CreateGoal",
        "CreateRoadmap",
        "CreateTask",
        "SuggestCalendarSlots",
        "ProjectTaskToCalendar",
    } == ALLOWED_AI_COMMANDS


@pytest.mark.asyncio
async def test_jwt_bearer_creates_authenticated_request_context() -> None:
    user_id = uuid4()
    token = jwt.encode({"sub": str(user_id)}, get_settings().jwt_secret, algorithm="HS256")
    request = Request({"type": "http", "headers": []})

    context = await get_request_context(
        request,
        authorization=f"Bearer {token}",
        x_user_id=None,
        x_correlation_id="contract-test",
    )

    assert context.user_id == user_id
    assert context.correlation_id == "contract-test"


def test_outbox_event_moves_to_dead_letter_after_retry_limit() -> None:
    event = OutboxEvent(
        id=uuid4(),
        event_type="TaskCreated",
        workspace_id=uuid4(),
        correlation_id="contract-test",
        payload={},
        occurred_at=datetime.now(UTC),
    )
    for _ in range(5):
        mark_publish_failure(event)

    assert event.failed_attempts == 5
    assert event.is_dead_lettered is True


def test_integration_token_cipher_requires_valid_environment_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        token_cipher,
        "get_settings",
        lambda: SimpleNamespace(integration_encryption_key=""),
    )
    with pytest.raises(Exception, match="Integration token encryption is not configured"):
        token_cipher.encrypt_token("secret-token")


def test_google_oauth_state_is_signed_and_short_lived() -> None:
    connection = SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        owner_id=uuid4(),
    )
    state = _oauth_state(connection)  # type: ignore[arg-type]
    assert str(connection.id) not in state
    assert state.count(".") == 2


def test_verification_link_is_signed_short_lived_and_binds_user_email() -> None:
    user_id = uuid4()
    token = email_verification.create_verification_link_token(user_id, "person@example.com")

    assert token.count(".") == 2
    assert email_verification.parse_verification_link_token(token) == (
        user_id,
        "person@example.com",
    )


def test_expired_verification_link_is_rejected() -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "email": "person@example.com",
            "aud": "forma-email-verification",
            "exp": datetime.now(UTC) - timedelta(seconds=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(DomainError, match="invalid or expired"):
        email_verification.parse_verification_link_token(token)


@pytest.mark.asyncio
async def test_signed_verification_link_confirms_matching_profile_without_raw_token_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    user_id = uuid4()
    async with session_factory() as session:
        session.add(
            UserProfile(
                user_id=user_id,
                email="person@example.com",
                email_notifications_enabled=True,
            )
        )
        await session.commit()

    token = email_verification.create_verification_link_token(user_id, "person@example.com")
    async with session_factory() as session:
        response = await identity.confirm_email_verification_link(token, session)

    assert response.email_verified is True
    async with session_factory() as session:
        profile = await session.get(UserProfile, user_id)
    assert profile is not None
    assert profile.email_verified_at is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_profile_email_change_emits_empty_outbox_verification_request_without_raw_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    user_id = uuid4()
    context = SimpleNamespace(user_id=user_id, correlation_id="profile-verification-outbox")
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=user_id, name="Profile update space"))
        await session.commit()

    async with session_factory() as session:
        response = await identity.update_profile(
            identity.UpdateUserProfileRequest(
                email="person@example.com", email_notifications_enabled=True
            ),
            context,  # type: ignore[arg-type]
            session,
            "profile-verification-outbox-key",
        )

    assert response.email_verified is False
    assert "token" not in response.model_dump()
    async with session_factory() as session:
        events = list(
            (
                await session.scalars(
                    select(OutboxEvent).where(
                        OutboxEvent.event_type == "EmailVerificationRequested"
                    )
                )
            ).all()
        )
        verification_tokens = list((await session.scalars(select(EmailVerificationToken))).all())

    assert len(events) == 1
    assert events[0].workspace_id == workspace_id
    assert events[0].payload["event_type"] == "EmailVerificationRequested"
    assert events[0].payload["payload"] == {}
    assert "token" not in events[0].payload["payload"]
    assert verification_tokens == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_profile_email_change_without_workspace_is_rejected_before_mutation() -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    user_id = uuid4()
    context = SimpleNamespace(user_id=user_id, correlation_id="profile-without-workspace")
    async with session_factory() as session:
        with pytest.raises(ValueError, match="Create a workspace"):
            await identity.update_profile(
                identity.UpdateUserProfileRequest(
                    email="person@example.com", email_notifications_enabled=True
                ),
                context,  # type: ignore[arg-type]
                session,
                "profile-without-workspace-key",
            )

    async with session_factory() as session:
        profile = await session.get(UserProfile, user_id)
        events = list((await session.scalars(select(OutboxEvent))).all())
    assert profile is None
    assert events == []
    await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_overview_uses_short_lived_redis_cache_after_first_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    class FakeRedis:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.get_calls: list[str] = []
            self.set_calls: list[tuple[str, str, int]] = []
            self.close_calls = 0

        async def get(self, key: str) -> str | None:
            self.get_calls.append(key)
            return self.values.get(key)

        async def set(self, key: str, value: str, *, ex: int) -> None:
            self.values[key] = value
            self.set_calls.append((key, value, ex))

        async def aclose(self) -> None:
            self.close_calls += 1

    redis = FakeRedis()
    access = AsyncMock()
    monkeypatch.setattr(bff, "get_redis", lambda: redis)
    monkeypatch.setattr(bff, "require_workspace_access", access)
    workspace_id = uuid4()
    user_id = uuid4()
    context = SimpleNamespace(user_id=user_id)

    async with session_factory() as session:
        first = await bff.workspace_overview(workspace_id, context, session)  # type: ignore[arg-type]
        second = await bff.workspace_overview(workspace_id, context, session)  # type: ignore[arg-type]

    cache_key = f"forma:bff:overview:{user_id}:{workspace_id}"
    assert first == second
    assert redis.get_calls == [cache_key, cache_key]
    assert len(redis.set_calls) == 1
    assert redis.set_calls[0][0] == cache_key
    assert redis.set_calls[0][2] == 30
    assert redis.close_calls == 2
    assert access.await_count == 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_workspace_overview_cache_invalidation_targets_only_user_workspace_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRedis:
        def __init__(self) -> None:
            self.deleted_keys: list[str] = []
            self.closed = False

        async def delete(self, key: str) -> None:
            self.deleted_keys.append(key)

        async def aclose(self) -> None:
            self.closed = True

    redis = FakeRedis()
    monkeypatch.setattr(redis_adapter, "get_redis", lambda: redis)
    user_id = uuid4()
    workspace_id = uuid4()

    await redis_adapter.invalidate_workspace_overview_cache(str(user_id), str(workspace_id))

    assert redis.deleted_keys == [f"forma:bff:overview:{user_id}:{workspace_id}"]
    assert redis.closed is True


@pytest.mark.asyncio
async def test_approved_ai_plan_invalidates_workspace_overview_cache_after_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    user_id = uuid4()
    plan_id = uuid4()
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=user_id, name="AI cache space"))
        session.add(
            AIPlan(
                id=plan_id,
                workspace_id=workspace_id,
                prompt="Подтвердить пустое безопасное предложение",
                proposal_json={"commands": []},
                status="proposed",
            )
        )
        await session.commit()

    @asynccontextmanager
    async def fake_workspace_lock(_: str, ttl_seconds: int = 30):
        _ = ttl_seconds
        yield

    invalidate = AsyncMock()
    monkeypatch.setattr(ai_planning, "workspace_lock", fake_workspace_lock)
    monkeypatch.setattr(ai_planning, "require_workspace_access", AsyncMock())
    monkeypatch.setattr(ai_planning, "invalidate_workspace_overview_cache", invalidate)
    context = SimpleNamespace(user_id=user_id, correlation_id="ai-cache-invalidation")

    async with session_factory() as session:
        response = await ai_planning.approve_ai_plan(
            plan_id,
            workspace_id,
            context,  # type: ignore[arg-type]
            session,
            "ai-cache-invalidation-key",
        )

    assert response["status"] == "approved"
    invalidate.assert_awaited_once_with(str(user_id), str(workspace_id))
    async with session_factory() as session:
        persisted = await session.get(AIPlan, plan_id)
    assert persisted is not None
    assert persisted.status == "approved"

    await engine.dispose()


@pytest.mark.asyncio
async def test_ai_task_approval_invalidates_warm_overview_cache_and_forces_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    class FakeRedis:
        def __init__(self) -> None:
            self.values: dict[str, str] = {}
            self.deleted_keys: list[str] = []

        async def get(self, key: str) -> str | None:
            return self.values.get(key)

        async def set(self, key: str, value: str, *, ex: int) -> None:
            _ = ex
            self.values[key] = value

        async def delete(self, key: str) -> None:
            self.deleted_keys.append(key)
            self.values.pop(key, None)

        async def aclose(self) -> None:
            return None

    @asynccontextmanager
    async def fake_workspace_lock(_: str, ttl_seconds: int = 30):
        _ = ttl_seconds
        yield

    redis = FakeRedis()
    workspace_id = uuid4()
    user_id = uuid4()
    plan_id = uuid4()
    context = SimpleNamespace(user_id=user_id, correlation_id="ai-cache-refresh")
    monkeypatch.setattr(bff, "get_redis", lambda: redis)
    monkeypatch.setattr(redis_adapter, "get_redis", lambda: redis)
    monkeypatch.setattr(bff, "require_workspace_access", AsyncMock())
    monkeypatch.setattr(ai_planning, "require_workspace_access", AsyncMock())
    monkeypatch.setattr(ai_planning, "workspace_lock", fake_workspace_lock)

    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=user_id, name="AI refresh space"))
        session.add(
            AIPlan(
                id=plan_id,
                workspace_id=workspace_id,
                prompt="Добавить задачу и обновить кэш",
                proposal_json={
                    "commands": [
                        {
                            "command": "CreateTask",
                            "arguments": {"title": "Задача после AI approval"},
                        }
                    ]
                },
                status="proposed",
            )
        )
        await session.commit()

    async with session_factory() as session:
        warm = await bff.workspace_overview(workspace_id, context, session)  # type: ignore[arg-type]
    assert warm.open_tasks == 0

    async with session_factory() as session:
        approval = await ai_planning.approve_ai_plan(
            plan_id,
            workspace_id,
            context,  # type: ignore[arg-type]
            session,
            "ai-cache-refresh-key",
        )
    assert approval["status"] == "approved"

    cache_key = f"forma:bff:overview:{user_id}:{workspace_id}"
    assert redis.deleted_keys == [cache_key]
    assert cache_key not in redis.values

    async with session_factory() as session:
        refreshed = await bff.workspace_overview(workspace_id, context, session)  # type: ignore[arg-type]
    assert refreshed.open_tasks == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_google_oauth_callback_exchanges_encrypts_and_persists_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    owner_id = uuid4()
    connection_id = uuid4()
    calendar_connection = CalendarConnection(
        id=connection_id,
        workspace_id=workspace_id,
        owner_id=owner_id,
        provider="google_calendar",
        status="pending",
    )
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=owner_id, name="OAuth test space"))
        session.add(calendar_connection)
        await session.commit()

    encryption_key = Fernet.generate_key().decode()
    monkeypatch.setattr(
        token_cipher,
        "get_settings",
        lambda: SimpleNamespace(integration_encryption_key=encryption_key),
    )
    exchange_code = AsyncMock(return_value=("google-access-token", "google-refresh-token"))
    monkeypatch.setattr(integrations.GoogleCalendarProvider, "exchange_code", exchange_code)

    async with session_factory() as session:
        response = await integrations.google_calendar_callback(
            code="authorization-code",
            state=_oauth_state(calendar_connection),
            error=None,
            session=session,
        )

    assert response == {"connection_id": str(connection_id), "status": "connected"}
    exchange_code.assert_awaited_once_with("authorization-code")

    async with session_factory() as session:
        persisted = await session.get(CalendarConnection, connection_id)

    assert persisted is not None
    assert persisted.status == "connected"
    assert persisted.encrypted_access_token != "google-access-token"
    assert persisted.encrypted_refresh_token != "google-refresh-token"
    assert (
        token_cipher.decrypt_token(persisted.encrypted_access_token or "") == "google-access-token"
    )
    decrypted_refresh_token = token_cipher.decrypt_token(persisted.encrypted_refresh_token or "")
    assert decrypted_refresh_token == "google-refresh-token"

    await engine.dispose()


@pytest.mark.asyncio
async def test_google_oauth_callback_rejects_invalid_state_before_exchange(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange_code = AsyncMock()
    monkeypatch.setattr(integrations.GoogleCalendarProvider, "exchange_code", exchange_code)
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        with pytest.raises(DomainError, match="state is invalid or expired"):
            await integrations.google_calendar_callback(
                code="authorization-code",
                state="not-a-signed-state",
                error=None,
                session=session,
            )

    exchange_code.assert_not_awaited()
    await engine.dispose()


@pytest.mark.asyncio
async def test_google_oauth_callback_keeps_connection_pending_when_exchange_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    workspace_id = uuid4()
    owner_id = uuid4()
    calendar_connection = CalendarConnection(
        id=uuid4(),
        workspace_id=workspace_id,
        owner_id=owner_id,
        provider="google_calendar",
        status="pending",
    )
    async with session_factory() as session:
        session.add(Workspace(id=workspace_id, owner_id=owner_id, name="OAuth failure space"))
        session.add(calendar_connection)
        await session.commit()

    exchange_code = AsyncMock(
        side_effect=DomainError("CALENDAR_OAUTH_EXCHANGE_FAILED", "Google exchange failed.")
    )
    monkeypatch.setattr(integrations.GoogleCalendarProvider, "exchange_code", exchange_code)

    async with session_factory() as session:
        with pytest.raises(DomainError, match="Google exchange failed"):
            await integrations.google_calendar_callback(
                code="authorization-code",
                state=_oauth_state(calendar_connection),
                error=None,
                session=session,
            )

    async with session_factory() as session:
        persisted = await session.get(CalendarConnection, calendar_connection.id)

    assert persisted is not None
    assert persisted.status == "pending"
    assert persisted.encrypted_access_token is None
    assert persisted.encrypted_refresh_token is None
    await engine.dispose()
