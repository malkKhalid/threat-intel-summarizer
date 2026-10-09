from datetime import datetime, timezone

from threatintel.models import Alert, Article, Bulletin, Enrichment
from threatintel.report import build_html, build_markdown, write_report_files


def _bulletin() -> Bulletin:
    article = Article(
        title="Zero-day exploited",
        link="https://example.org/z",
        source="FeedX",
        published=datetime(2025, 10, 8, tzinfo=timezone.utc),
    )
    enrichment = Enrichment(
        article_hash=article.article_hash,
        bulletin=["Bullet one", "Bullet two"],
        trend="zero-day exploit",
        trend_confidence=0.91,
        urgency_score=95,
        sentiment="negative",
        iocs={"cve": ["CVE-2024-1234"]},
    )
    alert = Alert(
        article_hash=article.article_hash,
        title=article.title,
        link=article.link,
        source=article.source,
        urgency_score=95,
        trend="zero-day exploit",
        trend_confidence=0.91,
        reason="matched 'zero-day-watch'",
    )
    return Bulletin(
        generated_at=datetime(2025, 10, 8, 12, 0, tzinfo=timezone.utc),
        articles=[(article, enrichment)],
        alerts=[alert],
    )


def test_markdown_contains_key_sections():
    md = build_markdown(_bulletin())
    assert "Daily Threat Intelligence Bulletin" in md
    assert "Zero-day exploited" in md
    assert "CVE-2024-1234" in md


def test_html_is_wellformed_enough():
    html = build_html(_bulletin())
    assert html.startswith("<!doctype html>")
    assert "Zero-day exploited" in html
    assert "CVE-2024-1234" in html


def test_write_report_files(tmp_path):
    paths = write_report_files(_bulletin(), tmp_path)
    for key in ("markdown", "html", "json", "latest_html", "latest_json"):
        assert paths[key].exists()
    assert "Zero-day exploited" in paths["latest_html"].read_text(encoding="utf-8")
