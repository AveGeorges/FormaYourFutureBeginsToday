"""Imports every infrastructure model so Alembic sees one PostgreSQL metadata graph."""

from app.core.idempotency import IdempotencyRecord  # noqa: F401
from app.events.outbox import OutboxEvent  # noqa: F401
from app.modules.ai_planning.infrastructure.models import AIPlan  # noqa: F401
from app.modules.boards.infrastructure.models import Board, BoardEdge, BoardNode  # noqa: F401
from app.modules.identity.infrastructure.models import Workspace, WorkspaceMembership  # noqa: F401
from app.modules.notifications.infrastructure.models import (  # noqa: F401
    AuditRecord,
    Notification,
    WorkerReceipt,
)
from app.modules.planning.infrastructure.models import (  # noqa: F401
    Action,
    Dream,
    Goal,
    Milestone,
    Roadmap,
)
from app.modules.scheduling.infrastructure.models import (  # noqa: F401
    Calendar,
    CalendarEvent,
    ExternalEventLink,
)
from app.modules.tasks.infrastructure.models import Task  # noqa: F401
from app.modules.time_tracking.infrastructure.models import TimeEntry  # noqa: F401
