"""External email delivery, gated by the self-hosted verified profile."""

from uuid import UUID, uuid4

from app.core.database import SessionLocal
from app.core.errors import DomainError
from app.modules.identity.infrastructure.models import UserProfile
from app.modules.notifications.infrastructure.models import EmailDeliveryAttempt, Notification
from app.modules.notifications.infrastructure.resend import ResendEmailProvider


async def deliver_notification_email(notification_id: UUID) -> str:
    """Deliver one in-app notification externally when the profile permits it.

    Return values are persisted operational states: delivered, skipped_unverified, skipped_opt_out,
    skipped_missing_profile or failed. Provider failure is recorded instead of changing the in-app
    notification outcome.
    """
    async with SessionLocal() as session:
        notification = await session.get(Notification, notification_id)
        if notification is None:
            return "skipped_missing_notification"
        profile = await session.get(UserProfile, notification.user_id)
        if profile is None:
            return "skipped_missing_profile"
        if profile.email_verified_at is None:
            return "skipped_unverified"
        if not profile.email_notifications_enabled:
            return "skipped_opt_out"

        attempt = EmailDeliveryAttempt(
            id=uuid4(),
            notification_id=notification.id,
            provider="resend",
            status="sending",
        )
        session.add(attempt)
        await session.flush()

        try:
            provider_message_id = await ResendEmailProvider().send(
                recipient=profile.email,
                subject=f"Forma: {notification.notification_type}",
                text=str(notification.payload),
            )
        except DomainError as exc:
            attempt.status = "failed"
            attempt.error_message = exc.message
            await session.commit()
            return "failed"

        attempt.status = "delivered"
        attempt.provider_message_id = provider_message_id
        await session.commit()
        return "delivered"
