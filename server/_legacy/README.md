# Legacy Express/tRPC Scaffold Archive

This directory preserves the original managed-template Express, tRPC, Drizzle and MySQL implementation as a **historical UI/reference artefact**. It is not mounted by `server/_core/index.ts`, is excluded from active TypeScript and Vitest quality gates, and is not part of the self-hosted production Docker Compose topology. The historical Drizzle configuration and migrations live under `server/_legacy/drizzle*`.

The active application contract is the Python/FastAPI API under `backend/app`, exposed as `/api/v1` and consumed from `client/src/lib/formaApi.ts`. Do not add new product behavior to this archive.
