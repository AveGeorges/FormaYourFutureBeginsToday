import httpx

from app.core.config import get_settings
from app.core.errors import DomainError


class ResendEmailProvider:
    endpoint = "https://api.resend.com/emails"

    async def send(self, *, recipient: str, subject: str, text: str) -> str:
        settings = get_settings()
        if not settings.resend_api_key or not settings.resend_from_email:
            raise DomainError(
                "EMAIL_PROVIDER_NOT_CONFIGURED",
                "Resend API key and sender address are not configured.",
            )
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={
                    "from": settings.resend_from_email,
                    "to": [recipient],
                    "subject": subject,
                    "text": text,
                },
            )
        if response.is_error:
            raise DomainError(
                "EMAIL_DELIVERY_FAILED", "Resend did not accept the email delivery request."
            )
        message_id = response.json().get("id")
        if not isinstance(message_id, str) or not message_id:
            raise DomainError(
                "EMAIL_DELIVERY_FAILED", "Resend response does not contain delivery message ID."
            )
        return message_id
