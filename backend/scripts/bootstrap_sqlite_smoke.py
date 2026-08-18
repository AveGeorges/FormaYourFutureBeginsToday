"""Create a disposable SQLite schema for a local FastAPI smoke test.

This script is deliberately outside the production startup path. Production Forma
uses PostgreSQL and Alembic; the SQLite database exists only to let development
environments without Docker exercise the REST boundary.
"""

import asyncio

import app.models_registry  # noqa: F401
from app.core.database import Base, engine


async def bootstrap() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(bootstrap())
