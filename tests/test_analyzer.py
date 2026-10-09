from threatintel.llm.analyzer import Analyzer
from threatintel.llm.provider import ExtractiveProvider
from threatintel.models import Article

LABELS = [
    "zero-day exploit",
    "ransomware",
    "data breach",
    "phishing",
    "malware",
    "vulnerability",
    "APT campaign",
]


def _article() -> Article:
    return Article(
        title="Critical zero-day in firewall actively exploited in the wild",
        link="https://example.org/a1",
        source="Test Feed",
        summary=(
            "Researchers reported a critical zero-day vulnerability being exploited in the wild. "
            "Attackers deploy ransomware after achieving remote code execution. "
            "Indicator CVE-2024-9999 and domain bad.actor-domain.com were observed."
        ),
    )


def test_extractive_summary_is_non_empty():
    provider = ExtractiveProvider()
    bullets = provider.summarize(_article().text, max_points=3)
    assert bullets
    assert len(bullets) <= 3


def test_trend_and_urgency_high_for_zero_day():
    analyzer = Analyzer(provider=ExtractiveProvider(), trend_labels=LABELS)
    enrichment = analyzer.analyze(_article())
    assert enrichment.trend in {"zero-day exploit", "ransomware", "vulnerability"}
    assert enrichment.urgency_score >= 70
    assert enrichment.iocs.get("cve") == ["CVE-2024-9999"]


def test_benign_article_low_urgency():
    article = Article(
        title="Company releases annual transparency report",
        link="https://example.org/a2",
        source="Test Feed",
        summary="The report describes governance and general company updates for the year.",
    )
    analyzer = Analyzer(provider=ExtractiveProvider(), trend_labels=LABELS)
    enrichment = analyzer.analyze(article)
    assert enrichment.urgency_score < 60
