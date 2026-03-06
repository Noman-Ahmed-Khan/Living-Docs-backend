"""SMTP email service — infrastructure implementation wrapping app/utils/email.py."""

from app.domain.users.interfaces import IEmailService
from .utils import (
    send_verification_email as _send_verification,
    send_password_reset_email as _send_reset,
    send_password_changed_email as _send_changed,
    send_email_change_verification as _send_email_change,
    send_account_deleted_email as _send_deleted,
    send_security_alert_email as _send_alert,
)


class SMTPEmailService(IEmailService):
    """Email service delegating to the existing email utilities."""

    async def send_verification_email(self, email: str, token: str) -> None:
        """Send email verification link."""
        _send_verification(email, token)

    async def send_password_reset_email(self, email: str, token: str) -> None:
        """Send password reset link."""
        _send_reset(email, token)

    async def send_password_changed_notification(self, email: str) -> None:
        """Send password change notification."""
        _send_changed(email)

    async def send_email_change_verification(
        self,
        new_email: str,
        token: str
    ) -> None:
        """Send email change verification to new address."""
        _send_email_change(new_email, token)

    async def send_account_deleted_notification(self, email: str) -> None:
        """Send account deletion confirmation."""
        _send_deleted(email)

    async def send_security_alert(self, email: str, message: str) -> None:
        """Send security alert email."""
        _send_alert(email, message)
