from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("actions.id", ondelete="SET NULL"), nullable=True
    )
    milestone_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("milestones.id", ondelete="SET NULL"), nullable=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(240))
    priority: Mapped[str] = mapped_column(String(24), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="todo")
    estimate_minutes: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
