"""Optional Twilio SMS alert channel (only for the most critical alerts)."""

from __future__ import annotations

import logging

import httpx

from ..config import Settings
from ..models import Alert
from . import AlertChannel

log = logging.getLogger(__name__)

SMS_URGENCY_FLOOR = 85


class TwilioChannel(AlertChannel):
    name = "sms"

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def is_enabled(self) -> bool:
        return bool(
            self.s.twilio_enabled
            and self.s.twilio_account_sid
            and self.s.twilio_auth_token
            and self.s.twilio_from
            and self.s.twilio_to
        )

    def send(self, alert: Alert) -> bool:
        if alert.urgency_score < SMS_URGENCY_FLOOR:
            return False
        url = (
            f"https://api.twilio.com/2010-04-01/Accounts/"
            f"{self.s.twilio_account_sid}/Messages.json"
        )
        body = f"[{alert.urgency_score}] {alert.trend}: {alert.title} — {alert.link}"
        resp = httpx.post(
            url,
            data={"From": self.s.twilio_from, "To": self.s.twilio_to, "Body": body[:300]},
            auth=(self.s.twilio_account_sid, self.s.twilio_auth_token),
            timeout=20,
        )
        resp.raise_for_status()
        log.info("SMS alert sent: %s", alert.title)
        return True
