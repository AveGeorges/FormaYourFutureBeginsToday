# Local REST Smoke Test

**Date:** 2026-08-18

The production contract remains PostgreSQL plus Alembic. In a Docker-less sandbox, a disposable SQLite database was used only to exercise the FastAPI REST boundary.

| Check | Result |
|---|---|
| ORM metadata bootstrap on temporary SQLite | Passed |
| `POST /api/v1/workspaces` with dev `X-User-Id` and `Idempotency-Key` | Passed |
| `GET /api/v1/bff/workspaces/{id}/dashboard` | Passed |
| CORS preflight for development origin | Passed (`200`) |
| Same-origin development `/api/v1` proxy | Passed; FastAPI JSON returned instead of SPA HTML |
| Browser onboarding React → proxy → FastAPI → BFF dashboard | Passed |
| Full REST vertical slice: workspace → dream → goal → roadmap → milestone/action → task → calendar event → time entry → BFF | Passed |
| Browser projection of full BFF vertical slice: calendar event, task/time, dream/goal and Flow Map links | Passed |

> This is not a substitute for validating `deploy/docker-compose.production.yml` against real PostgreSQL, Redis and RabbitMQ on a Docker-capable server.

During the full scenario, the first `Dream` response exposed a real issue: SQLAlchemy column defaults were not materialized before the handler assembled its idempotent response. Planning, task and calendar-event handlers now assign their canonical `status` values explicitly, and the clean rerun passed.
