"""Domain models used across the pipeline."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def compute_hash(*parts: str) -> str:
    """Stable content hash used for de-duplication."""
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8", "ignore")).hexdigest()[:32]


@dataclass(slots=True)
class Article:
    """A single feed entry before/after enrichment."""

    title: str
    link: str
    source: str
    published: datetime = field(default_factory=utcnow)
    summary: str = ""
    content: str = ""
    article_hash: str = ""
    id: int | None = None

    def __post_init__(self) -> None:
        if not self.article_hash:
            self.article_hash = compute_hash(self.link or self.title, self.title)

    @property
    def text(self) -> str:
        return " ".join(p for p in (self.summary, self.content) if p).strip()


@dataclass(slots=True)
class Enrichment:
    """LLM / heuristic derived attributes for an article."""

    article_hash: str
    bulletin: list[str] = field(default_factory=list)
    trend: str = "unknown"
    trend_confidence: float = 0.0
    urgency_score: int = 0
    sentiment: str = "neutral"
    iocs: dict[str, list[str]] = field(default_factory=dict)
    enriched_by: str = "extractive"


@dataclass(slots=True)
class Alert:
    """An alert produced when an enrichment crosses a threshold/filter."""

    article_hash: str
    title: str
    link: str
    source: str
    urgency_score: int
    trend: str
    trend_confidence: float
    reason: str
    sent: bool = False
    channels: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=utcnow)


@dataclass(slots=True)
class Bulletin:
    """The daily digest built from enriched, filtered articles."""

    generated_at: datetime
    articles: list[tuple[Article, Enrichment]] = field(default_factory=list)
    alerts: list[Alert] = field(default_factory=list)
    title: str = "Daily Threat Intelligence Bulletin"

    @property
    def high_risk(self) -> list[tuple[Article, Enrichment]]:
        return [(a, e) for a, e in self.articles if e.urgency_score >= 70]
