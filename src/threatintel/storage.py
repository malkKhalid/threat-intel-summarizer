"""SQLite storage layer: caching feeds, enrichments and alert history."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Alert, Article, Enrichment

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    article_hash  TEXT UNIQUE NOT NULL,
    title         TEXT NOT NULL,
    link          TEXT NOT NULL,
    source        TEXT NOT NULL,
    published     TEXT,
    summary       TEXT,
    content       TEXT,
    fetched_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrichments (
    article_hash     TEXT PRIMARY KEY REFERENCES articles(article_hash),
    bulletin         TEXT NOT NULL,
    trend            TEXT NOT NULL,
    trend_confidence REAL NOT NULL,
    urgency_score    INTEGER NOT NULL,
    sentiment        TEXT NOT NULL,
    iocs             TEXT NOT NULL,
    enriched_by      TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    article_hash     TEXT NOT NULL,
    title            TEXT NOT NULL,
    link             TEXT NOT NULL,
    source           TEXT NOT NULL,
    urgency_score    INTEGER NOT NULL,
    trend            TEXT NOT NULL,
    trend_confidence REAL NOT NULL,
    reason           TEXT NOT NULL,
    sent             INTEGER NOT NULL DEFAULT 0,
    channels         TEXT NOT NULL,
    created_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published);
CREATE INDEX IF NOT EXISTS idx_alerts_urgency ON alerts(urgency_score);
"""


def _iso(dt: datetime | None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def _parse(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


class Storage:
    """Thin, dependency-free SQLite wrapper."""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ articles
    def article_exists(self, article_hash: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM articles WHERE article_hash = ?", (article_hash,)
            ).fetchone()
        return row is not None

    def save_article(self, article: Article) -> bool:
        """Insert article; returns True if newly inserted, False if duplicate."""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO articles
                    (article_hash, title, link, source, published, summary, content, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.article_hash,
                    article.title,
                    article.link,
                    article.source,
                    _iso(article.published),
                    article.summary,
                    article.content,
                    _iso(None),
                ),
            )
            return cur.rowcount > 0

    def recent_articles(self, limit: int = 100) -> list[Article]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM articles ORDER BY published DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            Article(
                id=r["id"],
                title=r["title"],
                link=r["link"],
                source=r["source"],
                published=_parse(r["published"]),
                summary=r["summary"] or "",
                content=r["content"] or "",
                article_hash=r["article_hash"],
            )
            for r in rows
        ]

    # -------------------------------------------------------------- enrichments
    def save_enrichment(self, e: Enrichment) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO enrichments
                    (article_hash, bulletin, trend, trend_confidence, urgency_score,
                     sentiment, iocs, enriched_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    e.article_hash,
                    json.dumps(e.bulletin),
                    e.trend,
                    e.trend_confidence,
                    e.urgency_score,
                    e.sentiment,
                    json.dumps(e.iocs),
                    e.enriched_by,
                    _iso(None),
                ),
            )

    def get_enrichment(self, article_hash: str) -> Enrichment | None:
        with self._connect() as conn:
            r = conn.execute(
                "SELECT * FROM enrichments WHERE article_hash = ?", (article_hash,)
            ).fetchone()
        if not r:
            return None
        return Enrichment(
            article_hash=r["article_hash"],
            bulletin=json.loads(r["bulletin"]),
            trend=r["trend"],
            trend_confidence=r["trend_confidence"],
            urgency_score=r["urgency_score"],
            sentiment=r["sentiment"],
            iocs=json.loads(r["iocs"]),
            enriched_by=r["enriched_by"],
        )

    # -------------------------------------------------------------------- alerts
    def save_alert(self, alert: Alert) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO alerts
                    (article_hash, title, link, source, urgency_score, trend,
                     trend_confidence, reason, sent, channels, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    alert.article_hash,
                    alert.title,
                    alert.link,
                    alert.source,
                    alert.urgency_score,
                    alert.trend,
                    alert.trend_confidence,
                    alert.reason,
                    int(alert.sent),
                    json.dumps(alert.channels),
                    _iso(alert.created_at),
                ),
            )
            return int(cur.lastrowid or 0)

    def recent_alerts(self, limit: int = 50) -> list[Alert]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            Alert(
                article_hash=r["article_hash"],
                title=r["title"],
                link=r["link"],
                source=r["source"],
                urgency_score=r["urgency_score"],
                trend=r["trend"],
                trend_confidence=r["trend_confidence"],
                reason=r["reason"],
                sent=bool(r["sent"]),
                channels=json.loads(r["channels"]),
                created_at=_parse(r["created_at"]),
            )
            for r in rows
        ]

    def count_articles(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0])

    def distinct_sources(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT source FROM articles ORDER BY source").fetchall()
        return [r[0] for r in rows]

    def iter_enriched(self, limit: int = 100) -> Iterable[tuple[Article, Enrichment]]:
        for article in self.recent_articles(limit=limit):
            enrichment = self.get_enrichment(article.article_hash)
            if enrichment:
                yield article, enrichment
