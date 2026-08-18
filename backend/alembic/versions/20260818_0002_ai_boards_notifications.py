"""Add board, AI planning, notification and audit persistence.

Revision ID: 20260818_0002
Revises: 20260818_0001
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260818_0002"
down_revision: str | Sequence[str] | None = "20260818_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def uuid_column(name: str, *constraints: object, **kwargs: object) -> sa.Column[object]:
    return sa.Column(name, postgresql.UUID(as_uuid=True), *constraints, **kwargs)


def upgrade() -> None:
    op.create_table(
        "boards",
        uuid_column("id", primary_key=True),
        uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("view_mode", sa.String(32), nullable=False),
    )
    op.create_index("ix_boards_workspace_id", "boards", ["workspace_id"])
    op.create_table(
        "board_nodes",
        uuid_column("id", primary_key=True),
        uuid_column("board_id", sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("object_type", sa.String(48), nullable=False),
        uuid_column("object_id", nullable=False),
        sa.Column("x", sa.Integer(), nullable=False),
        sa.Column("y", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
    )
    op.create_index("ix_board_nodes_board_id", "board_nodes", ["board_id"])
    op.create_index("ix_board_nodes_object_id", "board_nodes", ["object_id"])
    op.create_table(
        "board_edges",
        uuid_column("id", primary_key=True),
        uuid_column("board_id", sa.ForeignKey("boards.id", ondelete="CASCADE"), nullable=False),
        uuid_column("source_node_id", sa.ForeignKey("board_nodes.id", ondelete="CASCADE"), nullable=False),
        uuid_column("target_node_id", sa.ForeignKey("board_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("edge_type", sa.String(48), nullable=False),
    )
    op.create_index("ix_board_edges_board_id", "board_edges", ["board_id"])
    op.create_index("ix_board_edges_source_node_id", "board_edges", ["source_node_id"])
    op.create_index("ix_board_edges_target_node_id", "board_edges", ["target_node_id"])
    op.create_table(
        "ai_plans",
        uuid_column("id", primary_key=True),
        uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("proposal_json", postgresql.JSONB(), nullable=False),
        sa.Column("approval_key", sa.String(255), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_plans_workspace_id", "ai_plans", ["workspace_id"])
    op.create_table(
        "notifications",
        uuid_column("id", primary_key=True),
        uuid_column("workspace_id", sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        uuid_column("user_id", nullable=False),
        sa.Column("notification_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notifications_workspace_id", "notifications", ["workspace_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_table(
        "audit_records",
        uuid_column("id", primary_key=True),
        uuid_column("workspace_id", nullable=False),
        uuid_column("actor_id", nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("aggregate_type", sa.String(80), nullable=False),
        uuid_column("aggregate_id", nullable=False),
        sa.Column("correlation_id", sa.String(120), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_records_workspace_id", "audit_records", ["workspace_id"])
    op.create_index("ix_audit_records_actor_id", "audit_records", ["actor_id"])
    op.create_index("ix_audit_records_aggregate_id", "audit_records", ["aggregate_id"])
    op.create_index("ix_audit_records_correlation_id", "audit_records", ["correlation_id"])


def downgrade() -> None:
    for table in ["audit_records", "notifications", "ai_plans", "board_edges", "board_nodes", "boards"]:
        op.drop_table(table)
