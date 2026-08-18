from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import Header, HTTPException, status
from sqlalchemy import JSON, DateTime, String, UniqueConstraint, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("user_id", "scope", "key", name="uq_idempotency_scope_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(index=True)
    scope: Mapped[str] = mapped_column(String(160))
    key: Mapped[str] = mapped_column(String(255))
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


async def require_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "Idempotency-Key is required."},
        )
    return idempotency_key


async def execute_idempotent(
    session: AsyncSession,
    *,
    user_id: UUID,
    scope: str,
    key: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    existing = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.scope == scope,
            IdempotencyRecord.key == key,
        )
    )
    if existing and existing.response_json is not None:
        return existing.response_json
    response = await operation()
    if existing is None:
        session.add(
            IdempotencyRecord(user_id=user_id, scope=scope, key=key, response_json=response)
        )
    else:
        existing.response_json = response
    await session.commit()
    return response
