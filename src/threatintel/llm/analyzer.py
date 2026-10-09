"""Turns raw articles into :class:`Enrichment` records using a provider."""

from __future__ import annotations

from ..config import get_settings
from ..iocs import extract_iocs
from ..models import Article, Enrichment
from .provider import LLMProvider, get_provider


class Analyzer:
    def __init__(self, provider: LLMProvider | None = None, trend_labels: list[str] | None = None) -> None:
        self.provider = provider or get_provider()
        self.trend_labels = trend_labels or get_settings().trend_labels

    def analyze(self, article: Article, max_points: int = 4) -> Enrichment:
        text = article.text or article.title
        payload = f"{article.title}. {text}"

        bullets = self.provider.summarize(payload, max_points=max_points)
        if not bullets:
            bullets = [article.title]

        trend, confidence = self.provider.classify_trend(payload, self.trend_labels)
        urgency, sentiment = self.provider.score_urgency(payload, trend, confidence)
        iocs = extract_iocs(payload)

        return Enrichment(
            article_hash=article.article_hash,
            bulletin=bullets,
            trend=trend,
            trend_confidence=confidence,
            urgency_score=urgency,
            sentiment=sentiment,
            iocs=iocs,
            enriched_by=self.provider.name,
        )
