from datetime import UTC, datetime
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.core.config import get_settings
from app.core.request_context import get_request_context
from app.events.outbox import OutboxEvent, mark_publish_failure
from app.main import create_app
from app.modules.ai_planning.domain import ALLOWED_AI_COMMANDS


def test_health_contract() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "forma-api"}


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
