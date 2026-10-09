"""Alerting subpackage and dispatcher."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config import get_settings
from ..models import Alert

log = logging.getLogger(__name__)


class AlertChannel(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, alert: Alert) -> bool:
        """Send the alert. Return True on success."""

    def is_enabled(self) -> bool:
        return True


class AlertDispatcher:
    """Fan-out alerts to every enabled channel."""

    def __init__(self, channels: list[AlertChannel] | None = None) -> None:
        self.channels = channels if channels is not None else build_channels()

    def dispatch(self, alert: Alert) -> list[str]:
        delivered: list[str] = []
        for channel in self.channels:
            if not channel.is_enabled():
                continue
            try:
                if channel.send(alert):
                    delivered.append(channel.name)
            except Exception as exc:  # noqa: BLE001 - never fail the pipeline on alerts
                log.error("Alert channel %s failed: %s", channel.name, exc)
        alert.sent = bool(delivered)
        alert.channels = delivered
        return delivered


def build_channels() -> list[AlertChannel]:
    """Instantiate channels according to settings."""
    from .email_alert import EmailChannel
    from .slack_alert import SlackChannel
    from .twilio_alert import TwilioChannel

    settings = get_settings()
    return [
        EmailChannel(settings),
        SlackChannel(settings),
        TwilioChannel(settings),
    ]


__all__ = ["AlertChannel", "AlertDispatcher", "build_channels"]
