from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from redis.asyncio import Redis

from app.core.config import get_settings


def get_redis() -> Redis:
    return cast(Redis, Redis.from_url(get_settings().redis_url, decode_responses=True))


async def invalidate_workspace_overview_cache(user_id: str, workspace_id: str) -> None:
    """Clear only temporary BFF summary data after a committed workspace mutation."""
    redis = get_redis()
    try:
        await redis.delete(f"forma:bff:overview:{user_id}:{workspace_id}")
    finally:
        await redis.aclose()


@asynccontextmanager
async def workspace_lock(workspace_id: str, ttl_seconds: int = 30) -> AsyncIterator[None]:
    redis = get_redis()
    lock = redis.lock(f"forma:workspace:{workspace_id}", timeout=ttl_seconds)
    acquired = await lock.acquire(blocking_timeout=1)
    if not acquired:
        raise TimeoutError("Unable to acquire workspace lock")
    try:
        yield
    finally:
        await lock.release()
        await redis.aclose()
