"""Transactional-outbox consumer for signed self-hosted verification email delivery."""

from uuid import uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.events.contracts import EventEnvelope
from app.modules.identity.infrastructure.email_verification import create_verification_link_token
from app.modules.identity.infrastructure.models import UserProfile
from app.modules.notifications.infrastructure.models import WorkerReceipt
from app.modules.notifications.infrastructure.resend import ResendEmailProvider


async def deliver_verification_email(event: EventEnvelope) -> bool:
    async with SessionLocal() as session:
        receipt = await session.scalar(
            select(WorkerReceipt).where(
                WorkerReceipt.consumer_name == "verification-email-worker",
                WorkerReceipt.event_id == event.event_id,
            )
        )
        if receipt is not None:
            return False
        profile = await session.get(UserProfile, event.aggregate_id)
        if profile is None or profile.email_verified_at is not None:
            session.add(
                WorkerReceipt(
                    id=uuid4(),
                    consumer_name="verification-email-worker",
                    event_id=event.event_id,
                    status="skipped",
                )
            )
            await session.commit()
            return False
        try:
            base_url = get_settings().web_app_base_url.rstrip("/")
            if not base_url:
                raise RuntimeError("FORMA_WEB_APP_BASE_URL is not configured.")
            signed_token = create_verification_link_token(event.aggregate_id, profile.email)
            verification_url = (
                f"{base_url}/api/v1/workspaces/profile/email-verification/confirm-link?token="
                f"{signed_token}"
            )
            await ResendEmailProvider().send(
                recipient=profile.email,
                subject="Forma: подтвердите адрес электронной почты",
                text=(
                    "Подтвердите адрес электронной почты для Forma, открыв ссылку "
                    "в течение 24 часов:\n\n"
                    f"{verification_url}\n\n"
                    "Если вы не запрашивали подтверждение, просто проигнорируйте это письмо."
                ),
            )
            session.add(
                WorkerReceipt(
                    id=uuid4(),
                    consumer_name="verification-email-worker",
                    event_id=event.event_id,
                    status="delivered",
                )
            )
            await session.commit()
            return True
        except Exception:
            session.add(
                WorkerReceipt(
                    id=uuid4(),
                    consumer_name="verification-email-worker",
                    event_id=event.event_id,
                    status="failed",
                )
            )
            await session.commit()
            raise
