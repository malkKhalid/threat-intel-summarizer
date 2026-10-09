"""RSS/Atom fetching and parsing.

Network access is isolated in :func:`fetch_feed_text` so the parsing logic in
:func:`parse_feed` stays pure and easy to unit test with fixture strings.
"""

from __future__ import annotations

import logging
import re
from calendar import timegm
from datetime import datetime, timedelta, timezone

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ..models import Article
from .feeds import Feed

log = logging.getLogger(__name__)

USER_AGENT = "ThreatIntelSummarizer/0.1 (+https://github.com)"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_HTML_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
    "&nbsp;": " ",
}


def clean_html(raw: str | None) -> str:
    """Strip tags/entities/whitespace from a feed field."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    for entity, char in _HTML_ENTITIES.items():
        text = text.replace(entity, char)
    return _WS_RE.sub(" ", text).strip()


def _to_datetime(entry: object) -> datetime:
    parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if parsed:
        try:
            return datetime.fromtimestamp(timegm(parsed), tz=timezone.utc)
        except (OverflowError, ValueError):
            pass
    return datetime.now(timezone.utc)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=8), reraise=True)
def _get(client: httpx.Client, url: str) -> str:
    resp = client.get(url)
    resp.raise_for_status()
    return resp.text


def fetch_feed_text(url: str, timeout: float = 20.0) -> str:
    """Fetch raw feed body, retrying transient failures."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, */*"}
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        return _get(client, url)


def parse_feed(text: str, feed: Feed, max_items: int = 10) -> list[Article]:
    """Parse feed text into :class:`Article` objects (pure, no I/O)."""
    parsed = feedparser.parse(text)
    articles: list[Article] = []
    for entry in parsed.entries[:max_items]:
        title = clean_html(getattr(entry, "title", "")).strip()
        link = getattr(entry, "link", "") or ""
        if not title or not link:
            continue
        body = ""
        if getattr(entry, "content", None):
            body = clean_html(entry.content[0].get("value", ""))
        summary = clean_html(getattr(entry, "summary", "")) or clean_html(
            getattr(entry, "description", "")
        )
        articles.append(
            Article(
                title=title,
                link=link,
                source=feed.name,
                published=_to_datetime(entry),
                summary=summary,
                content=body,
            )
        )
    return articles


def scrape_feeds(
    feeds: list[Feed],
    max_items: int = 10,
    freshness_hours: int = 24,
    timeout: float = 20.0,
) -> list[Article]:
    """Fetch and parse all feeds, de-duplicating by content hash."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=freshness_hours) if freshness_hours else None
    seen: set[str] = set()
    collected: list[Article] = []
    for feed in feeds:
        try:
            text = fetch_feed_text(feed.url, timeout=timeout)
            items = parse_feed(text, feed, max_items=max_items)
        except Exception as exc:  # noqa: BLE001 - one bad feed must not kill the run
            log.warning("Failed to scrape %s (%s): %s", feed.name, feed.url, exc)
            continue
        for article in items:
            if cutoff and article.published < cutoff:
                continue
            if article.article_hash in seen:
                continue
            seen.add(article.article_hash)
            collected.append(article)
    log.info("Scraped %d unique articles from %d feeds", len(collected), len(feeds))
    return collected
