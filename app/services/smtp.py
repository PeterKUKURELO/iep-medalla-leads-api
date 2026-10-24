from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage

from app.config import SMTPProfile


class SMTPTransport:
    """Authenticated SMTP transport shared by delivery and diagnostics."""

    def __init__(self, profile: SMTPProfile) -> None:
        self.profile = profile

    def verify_connection(self) -> None:
        """Validate DNS/TCP, STARTTLS certificate and credentials without sending."""
        with self._connect():
            return

    def send(self, message: EmailMessage) -> None:
        with self._connect() as smtp:
            smtp.send_message(message)

    def _connect(self) -> smtplib.SMTP:
        profile = self.profile
        smtp = smtplib.SMTP(
            profile.mail_host,
            profile.mail_port,
            timeout=profile.mail_timeout_seconds,
        )
        try:
            smtp.ehlo()
            if profile.mail_use_tls:
                smtp.starttls(context=ssl.create_default_context())
                smtp.ehlo()
            smtp.login(profile.mail_username, profile.mail_password.get_secret_value())
        except Exception:
            smtp.close()
            raise
        return smtp
