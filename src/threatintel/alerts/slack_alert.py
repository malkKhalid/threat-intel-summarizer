"""Slack incoming-webhook alert channel."""

from __future__ import annotations

import logging

import httpx

from ..config import Settings
from ..models import Alert
from . import AlertChannel
from .formatting import slack_blocks

log = logging.getLogger(__name__)


class SlackChannel(AlertChannel):
    name = "slack"

    def __init__(self, settings: Settings) -> None:
        self.s = settings

    def is_enabled(self) -> bool:
        return bool(self.s.slack_enabled and self.s.slack_webhook_url)

    def send(self, alert: Alert) -> bool:
        payload = slack_blocks(alert)
        payload["text"] = f"[{alert.urgency_score}] {alert.title}"
        resp = httpx.post(self.s.slack_webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        log.info("Slack alert sent: %s", alert.title)
        return True
