import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_verification_email(user, token):
    frontend_url = getattr(settings, "FRONTEND_URL", "http://127.0.0.1:5173")
    verify_url = f"{frontend_url}/verify-email?token={token.token}"

    subject = "Подтверждение email — Store with AI"
    message = (
        f"Здравствуйте, {user.username}!\n\n"
        f"Подтвердите email, перейдя по ссылке:\n{verify_url}\n\n"
        "Если вы не регистрировались — просто проигнорируйте это письмо."
    )

    if not user.email:
        logger.warning("Cannot send verification email: user %s has no email", user.username)
        return False

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.exception("Failed to send verification email to %s", user.email)
        return False
