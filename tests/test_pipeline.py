from threatintel.config import Settings
from threatintel.llm.provider import ExtractiveProvider
from threatintel.models import Article
from threatintel.pipeline import Pipeline


def _settings(tmp_path) -> Settings:
    s = Settings()
    s.database_path = tmp_path / "threatintel.db"
    s.report_output_dir = tmp_path / "reports"
    s.llm_provider = "extractive"
    s.ensure_dirs()
    return s


ARTICLES = [
    Article(
        title="Critical zero-day exploited in the wild",
        link="https://example.org/1",
        source="Test Feed",
        summary="CVE-2024-1111 is actively exploited. Attackers deploy ransomware.",
    ),
    Article(
        title="Company publishes annual update",
        link="https://example.org/2",
        source="Test Feed",
        summary="A short and uneventful corporate announcement.",
    ),
]


def test_pipeline_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr("threatintel.pipeline.scrape_feeds", lambda *a, **k: list(ARTICLES))
    pipeline = Pipeline(settings=_settings(tmp_path), provider=ExtractiveProvider())

    bulletin, summary = pipeline.run(dry_run=True)

    assert summary.articles_scraped == 2
    assert summary.new_articles == 2
    assert len(bulletin.articles) == 2
    assert summary.alerts >= 1
    assert summary.report_paths["latest_html"].exists()
    assert summary.report_paths["latest_json"].exists()


def test_pipeline_deduplicates_on_second_run(tmp_path, monkeypatch):
    monkeypatch.setattr("threatintel.pipeline.scrape_feeds", lambda *a, **k: list(ARTICLES))
    pipeline = Pipeline(settings=_settings(tmp_path), provider=ExtractiveProvider())

    first, s1 = pipeline.run(dry_run=True)
    second, s2 = pipeline.run(dry_run=True)

    assert s1.new_articles == 2
    assert s2.new_articles == 0
    assert len(second.alerts) == 0
