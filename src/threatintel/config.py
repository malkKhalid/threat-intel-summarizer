"""Central configuration loaded from environment / .env with safe defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional dependency, degrade gracefully
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional at runtime
    pass

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


def _path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default))
    return p if p.is_absolute() else (PROJECT_ROOT / p)


@dataclass
class Settings:
    """Runtime settings. Instantiate with :func:`get_settings`."""

    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "extractive").strip())
    hf_summarizer_model: str = field(
        default_factory=lambda: os.getenv("HF_SUMMARIZER_MODEL", "sshleifer/distilbart-cnn-12-6")
    )
    hf_classifier_model: str = field(
        default_factory=lambda: os.getenv("HF_CLASSIFIER_MODEL", "facebook/bart-large-mnli")
    )
    hf_cache_dir: Path = field(default_factory=lambda: _path("HF_CACHE_DIR", "./hf_cache"))
    trend_labels: list[str] = field(
        default_factory=lambda: [
            x.strip()
            for x in os.getenv(
                "TREND_LABELS",
                "zero-day exploit,ransomware,data breach,phishing,malware,"
                "denial of service,supply chain attack,vulnerability,APT campaign",
            ).split(",")
            if x.strip()
        ]
    )

    database_path: Path = field(default_factory=lambda: _path("DATABASE_PATH", "./data/threatintel.db"))
    report_output_dir: Path = field(default_factory=lambda: _path("REPORT_OUTPUT_DIR", "./data/reports"))

    max_articles_per_feed: int = field(default_factory=lambda: _int("MAX_ARTICLES_PER_FEED", 10))
    freshness_hours: int = field(default_factory=lambda: _int("FRESHNESS_HOURS", 24))
    urgency_alert_threshold: int = field(default_factory=lambda: _int("URGENCY_ALERT_THRESHOLD", 70))

    smtp_enabled: bool = field(default_factory=lambda: _bool("SMTP_ENABLED"))
    smtp_host: str = field(default_factory=lambda: os.getenv("SMTP_HOST", "smtp.gmail.com"))
    smtp_port: int = field(default_factory=lambda: _int("SMTP_PORT", 587))
    smtp_user: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    smtp_from: str = field(default_factory=lambda: os.getenv("SMTP_FROM", ""))
    smtp_to: str = field(default_factory=lambda: os.getenv("SMTP_TO", ""))
    smtp_use_tls: bool = field(default_factory=lambda: _bool("SMTP_USE_TLS", True))

    slack_enabled: bool = field(default_factory=lambda: _bool("SLACK_ENABLED"))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))

    twilio_enabled: bool = field(default_factory=lambda: _bool("TWILIO_ENABLED"))
    twilio_account_sid: str = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID", ""))
    twilio_auth_token: str = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN", ""))
    twilio_from: str = field(default_factory=lambda: os.getenv("TWILIO_FROM", ""))
    twilio_to: str = field(default_factory=lambda: os.getenv("TWILIO_TO", ""))

    flask_secret_key: str = field(default_factory=lambda: os.getenv("FLASK_SECRET_KEY", "change-me"))

    def ensure_dirs(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_output_dir.mkdir(parents=True, exist_ok=True)


_settings: Settings | None = None


def get_settings(refresh: bool = False) -> Settings:
    """Return a cached :class:`Settings` instance."""
    global _settings
    if _settings is None or refresh:
        _settings = Settings()
    return _settings
