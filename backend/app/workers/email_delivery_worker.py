"""External email delivery, gated by the self-hosted verified profile."""

from uuid import UUID, uuid4

from app.core.database import SessionLocal
from app.core.errors import DomainError
from app.modules.identity.infrastructure.models import UserProfile
from app.modules.notifications.infrastructure.models import EmailDeliveryAttempt, Notification
from app.modules.notifications.infrastructure.resend import ResendEmailProvider


def _notification_email_content(notification: Notification) -> tuple[str, str]:
    """Return user-facing Russian email copy without serializing raw event payloads."""
    templates = {
        "AIPlanProposed": (
            "Forma: предложение AI готово",
            "AI подготовил предложение плана. Откройте Forma, просмотрите изменения и "
            "примите решение: изменения никогда не применяются автоматически.",
        ),
        "AIPlanApproved": (
            "Forma: предложение AI применено",
            "Подтверждённое вами предложение AI применено к вашему пространству Forma.",
        ),
        "TaskCreated": (
            "Forma: задача добавлена",
            "В вашем пространстве Forma появилась новая задача. При необходимости назначьте ей "
            "срок, приоритет и время в календаре.",
        ),
        "TaskStatusUpdated": (
            "Forma: статус задачи изменён",
            "Статус задачи обновлён. Откройте Forma, чтобы проверить следующий шаг.",
        ),
        "TaskDueSoon": (
            "Forma: срок задачи приближается",
            "Срок одной из ваших задач скоро наступит. Откройте Forma, чтобы уточнить "
            "следующее действие или перенести время в календаре.",
        ),
        "TaskReminder": (
            "Forma: напоминание о задаче",
            "Пора вернуться к запланированной задаче. Откройте Forma, чтобы продолжить работу "
            "или скорректировать план.",
        ),
        "CalendarEventReminder": (
            "Forma: напоминание о календарном блоке",
            "Скоро начнётся запланированный блок времени. Откройте Forma, чтобы проверить "
            "контекст и подготовиться к работе.",
        ),
        "CalendarEventScheduled": (
            "Forma: время в календаре запланировано",
            "Для вашего плана добавлен календарный блок. Откройте Forma, чтобы сверить время и "
            "приоритет.",
        ),
        "CalendarEventRescheduled": (
            "Forma: календарный блок перенесён",
            "Время календарного блока изменилось. Откройте Forma, чтобы подтвердить новый план.",
        ),
    }
    return templates.get(
        notification.notification_type,
        (
            "Forma: новое обновление",
            "В вашем пространстве Forma появилось новое обновление. Откройте приложение, "
            "чтобы посмотреть подробности.",
        ),
    )


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

        subject, text = _notification_email_content(notification)

        try:
            provider_message_id = await ResendEmailProvider().send(
                recipient=profile.email,
                subject=subject,
                text=text,
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
