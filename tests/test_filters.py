from threatintel.filters import FilterEngine, FilterRule
from threatintel.models import Article, Enrichment


def _article(title: str, source: str = "The Hacker News") -> Article:
    return Article(title=title, link="https://example.org/x", source=source, summary=title)


def _enrichment(trend: str = "ransomware", urgency: int = 80, iocs=None) -> Enrichment:
    return Enrichment(
        article_hash="h",
        trend=trend,
        trend_confidence=0.9,
        urgency_score=urgency,
        iocs=iocs or {},
    )


def test_industry_rule_matches_by_keyword_and_trend():
    rule = FilterRule(
        name="healthcare-sector",
        min_urgency=65,
        keywords=["hospital", "healthcare"],
        trend_labels=["ransomware", "data breach"],
    )
    engine = FilterEngine([rule], default_min_urgency=70)
    article = _article("Hospital chain crippled by ransomware attack")
    result = engine.should_alert(article, _enrichment())
    assert result is not None
    assert result.rule == "healthcare-sector"


def test_rule_rejects_below_urgency():
    rule = FilterRule(name="energy", min_urgency=90, keywords=["grid"])
    engine = FilterEngine([rule], default_min_urgency=95)
    article = _article("Power grid probing activity")
    assert engine.should_alert(article, _enrichment(urgency=50)) is None


def test_feed_tag_constraint():
    rule = FilterRule(name="tagged", feed_tags=["government"], min_urgency=10)
    engine = FilterEngine([rule], source_tags={"CISA": ["government"]}, default_min_urgency=99)
    assert engine.should_alert(_article("Advisory", source="CISA"), _enrichment(urgency=50))
    assert engine.should_alert(_article("Advisory", source="Blog"), _enrichment(urgency=50)) is None


def test_default_threshold_fallback():
    engine = FilterEngine([], default_min_urgency=70)
    result = engine.should_alert(_article("Something critical"), _enrichment(urgency=75))
    assert result is not None
    assert result.rule == "default-threshold"
