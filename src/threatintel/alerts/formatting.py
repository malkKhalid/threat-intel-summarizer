"""Shared alert formatting helpers (plain text and Slack blocks)."""

from __future__ import annotations

from ..models import Alert

URGENCY_EMOJI = {0: "🟢", 1: "🟡", 2: "🟠", 3: "🔴"}


def urgency_level(score: int) -> int:
    if score >= 85:
        return 3
    if score >= 70:
        return 2
    if score >= 50:
        return 1
    return 0


def subject(alert: Alert) -> str:
    level = urgency_level(alert.urgency_score)
    return f"{URGENCY_EMOJI[level]} [{alert.urgency_score}][{alert.trend}] {alert.title}"


def plain_body(alert: Alert) -> str:
    lines = [
        "THREAT INTELLIGENCE ALERT",
        "=" * 60,
        f"Title      : {alert.title}",
        f"Source     : {alert.source}",
        f"Trend      : {alert.trend} (conf {alert.trend_confidence:.0%})",
        f"Urgency    : {alert.urgency_score}/100",
        f"Reason     : {alert.reason}",
        f"Link       : {alert.link}",
        f"Detected   : {alert.created_at:%Y-%m-%d %H:%M UTC}",
        "",
        "This alert was generated automatically by the Threat Intelligence Summarizer.",
    ]
    return "\n".join(lines)


def slack_blocks(alert: Alert) -> dict:
    level = urgency_level(alert.urgency_score)
    return {
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Threat Intelligence Alert", "emoji": True},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{URGENCY_EMOJI[level]} *{alert.title}*",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Source:*\n{alert.source}"},
                    {"type": "mrkdwn", "text": f"*Trend:*\n{alert.trend} ({alert.trend_confidence:.0%})"},
                    {"type": "mrkdwn", "text": f"*Urgency:*\n{alert.urgency_score}/100"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n{alert.reason}"},
                ],
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": f"<{alert.link}|Open source>"}],
            },
        ]
    }
