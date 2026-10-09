"""End-to-end pipeline: scrape -> enrich -> filter -> alert -> report -> store."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .alerts import AlertDispatcher
from .config import Settings, get_settings
from .filters import FilterEngine, build_source_tags, load_filter_rules
from .llm.analyzer import Analyzer
from .llm.provider import LLMProvider
from .models import Alert, Bulletin
from .report import write_report_files
from .scraper import load_feeds, scrape_feeds
from .storage import Storage

log = logging.getLogger(__name__)


@dataclass(slots=True)
class RunSummary:
    feeds: int = 0
    articles_scraped: int = 0
    new_articles: int = 0
    alerts: int = 0
    delivered_alerts: int = 0
    duration_s: float = 0.0
    report_paths: dict[str, Path] = field(default_factory=dict)

    def as_text(self) -> str:
        return (
            f"feeds={self.feeds} scraped={self.articles_scraped} new={self.new_articles} "
            f"alerts={self.alerts} delivered={self.delivered_alerts} "
            f"duration={self.duration_s:.1f}s"
        )


class Pipeline:
    def __init__(
        self,
        settings: Settings | None = None,
        provider: LLMProvider | None = None,
        dispatcher: AlertDispatcher | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self.storage = Storage(self.settings.database_path)
        self.analyzer = Analyzer(provider=provider)
        self.feeds = load_feeds()
        self.filter_engine = FilterEngine(
            *load_filter_rules(),
            source_tags=build_source_tags(self.feeds),
        )
        self.dispatcher = dispatcher or AlertDispatcher()

    def run(self, dry_run: bool = False, write_report: bool = True) -> tuple[Bulletin, RunSummary]:
        start = time.perf_counter()
        summary = RunSummary(feeds=len(self.feeds))

        articles = scrape_feeds(
            self.feeds,
            max_items=self.settings.max_articles_per_feed,
            freshness_hours=self.settings.freshness_hours,
        )
        summary.articles_scraped = len(articles)

        bulletin = Bulletin(generated_at=datetime.now(timezone.utc))

        for article in articles:
            is_new = self.storage.save_article(article)
            if is_new:
                summary.new_articles += 1

            enrichment = self.storage.get_enrichment(article.article_hash)
            if enrichment is None:
                enrichment = self.analyzer.analyze(article)
                self.storage.save_enrichment(enrichment)

            bulletin.articles.append((article, enrichment))

            if not is_new:
                continue

            match = self.filter_engine.should_alert(article, enrichment)
            if not match:
                continue

            alert = Alert(
                article_hash=article.article_hash,
                title=article.title,
                link=article.link,
                source=article.source,
                urgency_score=enrichment.urgency_score,
                trend=enrichment.trend,
                trend_confidence=enrichment.trend_confidence,
                reason=match.reason,
            )
            if dry_run:
                log.info("[dry-run] would alert: %s", alert.title)
            else:
                delivered = self.dispatcher.dispatch(alert)
                summary.delivered_alerts += len(delivered)
            self.storage.save_alert(alert)
            bulletin.alerts.append(alert)
            summary.alerts += 1

        if write_report:
            summary.report_paths = write_report_files(bulletin, self.settings.report_output_dir)

        summary.duration_s = time.perf_counter() - start
        log.info("Pipeline complete: %s", summary.as_text())
        return bulletin, summary
