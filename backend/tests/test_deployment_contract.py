from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.modules.integrations.infrastructure import google_calendar
from app.modules.notifications.infrastructure import resend

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_project_file(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def _service_block(compose: str, service_name: str) -> str:
    lines = compose.splitlines()
    start = lines.index(f"  {service_name}:")
    block: list[str] = []
    for line in lines[start:]:
        if block and line.startswith("  ") and not line.startswith("    "):
            break
        block.append(line)
    return "\n".join(block)


class _FakeProviderResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.is_error = False
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeProviderResponse) -> None:
        self.post = AsyncMock(return_value=response)

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def test_production_compose_has_isolated_stateful_topology_and_worker_gating() -> None:
    compose = _read_project_file("deploy/docker-compose.production.yml")

    for service_name in (
        "postgres:",
        "redis:",
        "rabbitmq:",
        "migrate:",
        "api:",
        "worker-outbox:",
        "worker-events:",
    ):
        assert service_name in compose

    assert 'command: ["alembic", "upgrade", "head"]' in compose
    assert "condition: service_completed_successfully" in compose
    assert 'command: ["python", "-m", "app.workers.outbox_publisher"]' in compose
    assert 'command: ["python", "-m", "app.workers.runner"]' in compose
    assert 'command: ["uvicorn", "app.main:app"' in compose
    assert 'ports:\n      - "127.0.0.1:8080:8000"' in compose
    assert "networks: [internal]" in compose
    assert "3306" not in compose
    assert "6379:" not in compose
    assert "5672:" not in compose
    assert "frontend:" not in compose
    assert "nginx" not in compose.lower()

    assert """depends_on:
      postgres:
        condition: service_healthy
""" in _service_block(compose, "migrate")
    assert """depends_on:
      migrate:
        condition: service_completed_successfully
      redis:
        condition: service_healthy
      rabbitmq:
        condition: service_healthy
""" in _service_block(compose, "api")
    for worker_name in ("worker-outbox", "worker-events"):
        assert """depends_on:
      migrate:
        condition: service_completed_successfully
      rabbitmq:
        condition: service_healthy
""" in _service_block(compose, worker_name)
    assert """ports:
      - "127.0.0.1:8080:8000"
""" in _service_block(compose, "api")


def test_production_env_and_compose_mapping_cover_signed_email_and_external_providers() -> None:
    env_example = _read_project_file(".env.production.example")
    compose = _read_project_file("deploy/docker-compose.production.yml")

    expected_env_keys = (
        "FORMA_PUBLIC_ORIGIN",
        "FORMA_WEB_APP_BASE_URL",
        "GOOGLE_CALENDAR_CLIENT_ID",
        "GOOGLE_CALENDAR_CLIENT_SECRET",
        "GOOGLE_CALENDAR_REDIRECT_URI",
        "INTEGRATION_ENCRYPTION_KEY",
        "RESEND_API_KEY",
        "RESEND_FROM_EMAIL",
    )
    for key in expected_env_keys:
        assert f"{key}=" in env_example

    expected_backend_mappings = (
        "FORMA_WEB_APP_BASE_URL: ${FORMA_WEB_APP_BASE_URL}",
        "FORMA_GOOGLE_CALENDAR_CLIENT_ID: ${GOOGLE_CALENDAR_CLIENT_ID}",
        "FORMA_GOOGLE_CALENDAR_CLIENT_SECRET: ${GOOGLE_CALENDAR_CLIENT_SECRET}",
        "FORMA_GOOGLE_CALENDAR_REDIRECT_URI: ${GOOGLE_CALENDAR_REDIRECT_URI}",
        "FORMA_INTEGRATION_ENCRYPTION_KEY: ${INTEGRATION_ENCRYPTION_KEY}",
        "FORMA_RESEND_API_KEY: ${RESEND_API_KEY}",
        "FORMA_RESEND_FROM_EMAIL: ${RESEND_FROM_EMAIL}",
    )
    for mapping in expected_backend_mappings:
        assert mapping in compose

    assert "FORMA_WEB_STATIC_DIR: /app/web" in compose
    assert "express" not in compose.lower()
    assert "trpc" not in compose.lower()

    deployable_dockerfile = _read_project_file("deploy/fastapi-spa.Dockerfile")
    assert "FROM node:22-alpine AS frontend-builder" in deployable_dockerfile
    assert "RUN pnpm exec vite build" in deployable_dockerfile
    assert "COPY --from=frontend-builder /build/dist/public /app/web" in deployable_dockerfile
    assert "CMD [\"uvicorn\", \"app.main:app\"" in deployable_dockerfile
    assert deployable_dockerfile.index("COPY backend ./") < deployable_dockerfile.index(
        "RUN pip install ."
    )

    image_smoke_workflow = _read_project_file(
        ".github/workflows/fastapi-spa-image-smoke.yml"
    )
    assert "docker compose --env-file .env.production.example" in image_smoke_workflow
    assert "build api" in image_smoke_workflow


@pytest.mark.asyncio
async def test_google_oauth_exchange_adapter_accepts_a_simulated_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeAsyncClient(
        _FakeProviderResponse(
            {"access_token": "simulated-google-access", "refresh_token": "simulated-google-refresh"}
        )
    )
    monkeypatch.setattr(
        google_calendar,
        "get_settings",
        lambda: SimpleNamespace(
            google_calendar_client_id="simulated-google-client",
            google_calendar_client_secret="simulated-google-secret",
            google_calendar_redirect_uri="https://forma.example.test/api/v1/integrations/calendar/callback",
        ),
    )
    monkeypatch.setattr(google_calendar.httpx, "AsyncClient", lambda **_: client)

    access_token, refresh_token = await google_calendar.GoogleCalendarProvider().exchange_code(
        "simulated-authorization-code"
    )

    assert access_token == "simulated-google-access"
    assert refresh_token == "simulated-google-refresh"
    client.post.assert_awaited_once_with(
        google_calendar.GoogleCalendarProvider.token_endpoint,
        data={
            "code": "simulated-authorization-code",
            "client_id": "simulated-google-client",
            "client_secret": "simulated-google-secret",
            "redirect_uri": "https://forma.example.test/api/v1/integrations/calendar/callback",
            "grant_type": "authorization_code",
        },
    )


@pytest.mark.asyncio
async def test_resend_delivery_adapter_accepts_a_simulated_provider_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeAsyncClient(_FakeProviderResponse({"id": "simulated-resend-message"}))
    monkeypatch.setattr(
        resend,
        "get_settings",
        lambda: SimpleNamespace(
            resend_api_key="simulated-resend-key",
            resend_from_email="Forma <no-reply@forma.example.test>",
        ),
    )
    monkeypatch.setattr(resend.httpx, "AsyncClient", lambda **_: client)

    message_id = await resend.ResendEmailProvider().send(
        recipient="owner@forma.example.test",
        subject="Проверка Forma",
        text="Это локальная simulated проверка delivery boundary.",
    )

    assert message_id == "simulated-resend-message"
    client.post.assert_awaited_once_with(
        resend.ResendEmailProvider.endpoint,
        headers={"Authorization": "Bearer simulated-resend-key"},
        json={
            "from": "Forma <no-reply@forma.example.test>",
            "to": ["owner@forma.example.test"],
            "subject": "Проверка Forma",
            "text": "Это локальная simulated проверка delivery boundary.",
        },
    )
