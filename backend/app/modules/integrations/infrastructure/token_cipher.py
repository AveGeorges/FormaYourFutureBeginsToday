from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import DomainError


def _cipher() -> Fernet:
    key = get_settings().integration_encryption_key
    if not key:
        raise DomainError(
            "INTEGRATION_ENCRYPTION_NOT_CONFIGURED",
            "Integration token encryption is not configured.",
        )
    try:
        return Fernet(key.encode())
    except ValueError as exc:
        raise DomainError(
            "INTEGRATION_ENCRYPTION_INVALID",
            "Integration token encryption key is invalid.",
        ) from exc


def encrypt_token(token: str) -> str:
    return _cipher().encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    try:
        return _cipher().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise DomainError(
            "INTEGRATION_TOKEN_INVALID",
            "Stored integration token cannot be decrypted.",
        ) from exc
