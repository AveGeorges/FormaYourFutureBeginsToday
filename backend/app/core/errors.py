from fastapi import Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):
        return JSONResponse(
            status_code=500,
            content={"code": "INTERNAL_ERROR", "message": "Unexpected server error."},
        )
    return JSONResponse(
        status_code=400,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "request_id": request.headers.get("X-Request-Id"),
        },
    )
