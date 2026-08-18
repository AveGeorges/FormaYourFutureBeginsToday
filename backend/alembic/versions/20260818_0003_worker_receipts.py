"""Add idempotent worker receipts.

Revision ID: 20260818_0003
Revises: 20260818_0002
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260818_0003"
down_revision: str | Sequence[str] | None = "20260818_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("consumer_name", sa.String(100), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("consumer_name", "event_id", name="uq_worker_receipt"),
    )
    op.create_index("ix_worker_receipts_consumer_name", "worker_receipts", ["consumer_name"])
    op.create_index("ix_worker_receipts_event_id", "worker_receipts", ["event_id"])


def downgrade() -> None:
    op.drop_table("worker_receipts")
