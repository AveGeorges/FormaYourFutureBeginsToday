from dataclasses import dataclass
from uuid import UUID, uuid4

import jwt
import structlog
from fastapi import Header, HTTPException, Request, status

from app.core.config import get_settings


@dataclass(frozen=True)
class RequestContext:
    user_id: UUID
    request_id: str
    correlation_id: str


async def get_request_context(
    request: Request,
    authorization: str | None = Header(default=None),
    x_user_id: UUID | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None),
) -> RequestContext:
    settings = get_settings()
    user_id: UUID | None = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        try:
            claims = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
            user_id = UUID(str(claims["sub"]))
        except (KeyError, ValueError, jwt.PyJWTError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_ACCESS_TOKEN", "message": "Bearer token is invalid."},
            ) from exc
    elif settings.environment == "development" and x_user_id is not None:
        user_id = x_user_id
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHENTICATED", "message": "Authentication is required."},
        )
    request_id = request.headers.get("X-Request-Id", str(uuid4()))
    correlation_id = x_correlation_id or request_id
    structlog.contextvars.bind_contextvars(
        request_id=request_id, correlation_id=correlation_id, user_id=str(user_id)
    )
    return RequestContext(user_id=user_id, request_id=request_id, correlation_id=correlation_id)
