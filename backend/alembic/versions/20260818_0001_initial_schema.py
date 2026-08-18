"""Initial PostgreSQL schema for Forma modular monolith.

Revision ID: 20260818_0001
Revises:
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260818_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *constraints: object, **kwargs: object) -> sa.Column[object]:
    return sa.Column(name, postgresql.UUID(as_uuid=True), *constraints, **kwargs)


def upgrade() -> None:
    op.create_table("workspaces", uuid_column("id", primary_key=True), uuid_column("owner_id", nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_workspaces_owner_id", "workspaces", ["owner_id"])
    op.create_table("workspace_memberships", sa.Column("id", sa.Integer(), primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("user_id", nullable=False), sa.Column("role", sa.String(32), nullable=False), sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"))
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])
    op.create_table("dreams", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("visual_config", postgresql.JSONB(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_dreams_workspace_id", "dreams", ["workspace_id"])
    op.create_table("goals", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("dream_id", sa.ForeignKey("dreams.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("target_date", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_goals_workspace_id", "goals", ["workspace_id"])
    op.create_index("ix_goals_dream_id", "goals", ["dream_id"])
    op.create_table("roadmaps", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("goal_id", sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("status", sa.String(32), nullable=False))
    op.create_index("ix_roadmaps_workspace_id", "roadmaps", ["workspace_id"])
    op.create_index("ix_roadmaps_goal_id", "roadmaps", ["goal_id"])
    op.create_table("milestones", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("roadmap_id", sa.ForeignKey("roadmaps.id", ondelete="CASCADE"), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("position", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("target_date", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_milestones_workspace_id", "milestones", ["workspace_id"])
    op.create_index("ix_milestones_roadmap_id", "milestones", ["roadmap_id"])
    op.create_table("actions", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("goal_id", sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False), uuid_column("milestone_id", sa.ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True), sa.Column("title", sa.String(200), nullable=False), sa.Column("estimate_minutes", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False))
    op.create_index("ix_actions_workspace_id", "actions", ["workspace_id"])
    op.create_index("ix_actions_goal_id", "actions", ["goal_id"])
    op.create_table("tasks", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("action_id", sa.ForeignKey("actions.id", ondelete="SET NULL"), nullable=True), uuid_column("milestone_id", sa.ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True), uuid_column("parent_id", sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("priority", sa.String(24), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("estimate_minutes", sa.Integer(), nullable=False), sa.Column("due_at", sa.DateTime(timezone=True), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_tasks_workspace_id", "tasks", ["workspace_id"])
    op.create_table("calendars", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("calendar_type", sa.String(48), nullable=False), sa.Column("timezone", sa.String(64), nullable=False), sa.Column("provider", sa.String(48), nullable=False))
    op.create_index("ix_calendars_workspace_id", "calendars", ["workspace_id"])
    op.create_table("calendar_events", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("calendar_id", sa.ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False), uuid_column("task_id", sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True), uuid_column("action_id", sa.ForeignKey("actions.id", ondelete="SET NULL"), nullable=True), sa.Column("title", sa.String(240), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_calendar_events_workspace_id", "calendar_events", ["workspace_id"])
    op.create_index("ix_calendar_events_calendar_id", "calendar_events", ["calendar_id"])
    op.create_table("external_event_links", uuid_column("id", primary_key=True), uuid_column("calendar_event_id", sa.ForeignKey("calendar_events.id", ondelete="CASCADE"), nullable=False), sa.Column("provider", sa.String(48), nullable=False), sa.Column("external_calendar_id", sa.String(255), nullable=False), sa.Column("external_event_id", sa.String(255), nullable=False), sa.Column("etag", sa.String(255), nullable=True), sa.Column("sync_state", sa.String(32), nullable=False), sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True), sa.Column("sync_cursor", sa.Text(), nullable=True))
    op.create_index("ix_external_event_links_calendar_event_id", "external_event_links", ["calendar_event_id"])
    op.create_table("time_entries", uuid_column("id", primary_key=True), uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False), uuid_column("task_id", sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True), sa.Column("duration_seconds", sa.Integer(), nullable=False), sa.Column("source", sa.String(32), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_time_entries_workspace_id", "time_entries", ["workspace_id"])
    op.create_index("ix_time_entries_task_id", "time_entries", ["task_id"])
    op.create_table("idempotency_records", sa.Column("id", sa.Integer(), primary_key=True), uuid_column("user_id", nullable=False), sa.Column("scope", sa.String(160), nullable=False), sa.Column("key", sa.String(255), nullable=False), sa.Column("response_json", postgresql.JSONB(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_scope_key"))
    op.create_index("ix_idempotency_records_user_id", "idempotency_records", ["user_id"])
    op.create_table("outbox_events", uuid_column("id", primary_key=True), sa.Column("event_type", sa.String(120), nullable=False), uuid_column("workspace_id", nullable=False), sa.Column("correlation_id", sa.String(120), nullable=False), sa.Column("payload", postgresql.JSONB(), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True), nullable=True), sa.Column("failed_attempts", sa.Integer(), nullable=False), sa.Column("is_dead_lettered", sa.Boolean(), nullable=False))
    op.create_index("ix_outbox_events_event_type", "outbox_events", ["event_type"])
    op.create_index("ix_outbox_events_workspace_id", "outbox_events", ["workspace_id"])
    op.create_index("ix_outbox_events_correlation_id", "outbox_events", ["correlation_id"])


def downgrade() -> None:
    for table in ["outbox_events", "idempotency_records", "time_entries", "external_event_links", "calendar_events", "calendars", "tasks", "actions", "milestones", "roadmaps", "goals", "dreams", "workspace_memberships", "workspaces"]:
        op.drop_table(table)
