"""Signed, short-lived email verification link boundary without raw token persistence."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.errors import DomainError

_AUDIENCE = "forma-email-verification"


def create_verification_link_token(user_id: UUID, email: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "aud": _AUDIENCE,
            "exp": datetime.now(UTC) + timedelta(hours=24),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def parse_verification_link_token(token: str) -> tuple[UUID, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            audience=_AUDIENCE,
        )
        user_id = UUID(str(payload["sub"]))
        email = str(payload["email"])
    except (KeyError, TypeError, ValueError, jwt.PyJWTError) as exc:
        raise DomainError(
            "EMAIL_VERIFICATION_LINK_INVALID", "Email verification link is invalid or expired."
        ) from exc
    return user_id, email
