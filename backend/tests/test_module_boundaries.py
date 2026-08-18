from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.errors import DomainError
from app.modules.planning.application.references import (
    require_action_reference,
    require_milestone_reference,
)
from app.modules.tasks.application.references import require_task_reference

PRESENTATION_DIR = Path(__file__).resolve().parents[1] / "app" / "presentation"


@pytest.mark.asyncio
async def test_reference_ports_preserve_not_found_error_contracts() -> None:
    missing_reference_session = AsyncMock()
    missing_reference_session.scalar = AsyncMock(return_value=None)
    workspace_id = uuid4()

    with pytest.raises(DomainError, match="Linked object") as action_error:
        await require_action_reference(
            missing_reference_session, action_id=uuid4(), workspace_id=workspace_id
        )
    with pytest.raises(DomainError, match="Linked object") as milestone_error:
        await require_milestone_reference(
            missing_reference_session, milestone_id=uuid4(), workspace_id=workspace_id
        )
    with pytest.raises(DomainError, match="Linked object") as parent_error:
        await require_task_reference(
            missing_reference_session,
            task_id=uuid4(),
            workspace_id=workspace_id,
            not_found_code="PARENT_TASK_NOT_FOUND",
        )

    assert action_error.value.code == "ACTION_NOT_FOUND"
    assert milestone_error.value.code == "MILESTONE_NOT_FOUND"
    assert parent_error.value.code == "PARENT_TASK_NOT_FOUND"


def test_write_side_routers_use_public_cross_context_application_ports() -> None:
    tasks_router = (PRESENTATION_DIR / "tasks.py").read_text(encoding="utf-8")
    scheduling_router = (PRESENTATION_DIR / "scheduling.py").read_text(encoding="utf-8")
    time_router = (PRESENTATION_DIR / "time_tracking.py").read_text(encoding="utf-8")

    assert "app.modules.planning.infrastructure.models" not in tasks_router
    assert "app.modules.planning.application.references" in tasks_router
    assert "app.modules.tasks.infrastructure.models" not in scheduling_router
    assert "app.modules.tasks.application.references" in scheduling_router
    assert "app.modules.tasks.infrastructure.models" not in time_router
    assert "app.modules.tasks.application.references" in time_router


def test_bff_router_uses_public_context_query_ports() -> None:
    bff_router = (PRESENTATION_DIR / "bff.py").read_text(encoding="utf-8")

    assert ".infrastructure.models" not in bff_router
    assert "app.modules.identity.application.queries" in bff_router
    assert "app.modules.planning.application.queries" in bff_router
    assert "app.modules.tasks.application.queries" in bff_router
    assert "app.modules.scheduling.application.queries" in bff_router
    assert "app.modules.time_tracking.application.queries" in bff_router
    assert "app.modules.notifications.application.queries" in bff_router
