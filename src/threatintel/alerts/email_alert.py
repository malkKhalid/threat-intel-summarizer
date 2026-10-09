"""SMTP email alert channel."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from ..config import Settings
from ..models import Alert
from . import AlertChannel
from .formatting import plain_body, subject

log = logging.getLogger(__name__)


class EmailChannel(AlertChannel):
    name = "email"

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def is_enabled(self) -> bool:
        return bool(self.s.smtp_enabled and self.s.smtp_host and self.s.smtp_to)

    def send(self, alert: Alert) -> bool:
        msg = EmailMessage()
        msg["Subject"] = subject(alert)
        msg["From"] = self.s.smtp_from or self.s.smtp_user
        recipients = [addr.strip() for addr in self.s.smtp_to.split(",") if addr.strip()]
        msg["To"] = ", ".join(recipients)
        msg.set_content(plain_body(alert))

        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=30) as server:
            if self.s.smtp_use_tls:
                server.starttls()
            if self.s.smtp_user:
                server.login(self.s.smtp_user, self.s.smtp_password)
            server.send_message(msg, to_addrs=recipients)
        log.info("Email alert sent: %s", alert.title)
        return True
