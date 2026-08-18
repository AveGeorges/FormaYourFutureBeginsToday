from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.config import get_settings
from app.core.errors import DomainError, domain_error_handler
from app.core.logging import configure_logging


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id", str(uuid4()))
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def _configure_spa_fallback(app: FastAPI, *, api_prefix: str, static_dir: str) -> None:
    if not static_dir:
        return

    static_root = Path(static_dir).resolve()
    index_file = static_root / "index.html"
    if not index_file.is_file():
        return

    assets_root = static_root / "assets"
    normalized_api_prefix = api_prefix.strip("/")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str) -> Response:
        if full_path == normalized_api_prefix or full_path.startswith(
            f"{normalized_api_prefix}/"
        ):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        requested_file = (static_root / full_path).resolve()
        try:
            requested_file.relative_to(static_root)
        except ValueError:
            return FileResponse(index_file)

        if full_path and requested_file.is_file():
            response = FileResponse(requested_file)
            if assets_root.is_dir() and requested_file.is_relative_to(assets_root):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return response
        return FileResponse(index_file)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Forma API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(DomainError, domain_error_handler)

    @app.get("/health", tags=["system"])
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "forma-api"})

    from app.presentation.api import api_router

    app.include_router(api_router, prefix=settings.api_prefix)
    _configure_spa_fallback(
        app,
        api_prefix=settings.api_prefix,
        static_dir=settings.web_static_dir,
    )
    return app


app = create_app()
