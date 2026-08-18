from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
    return app


app = create_app()
