"""User-defined, industry-specific alert filters loaded from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import PROJECT_ROOT, get_settings
from .models import Article, Enrichment

DEFAULT_FILTERS_PATH = PROJECT_ROOT / "config" / "filters.yaml"


@dataclass(slots=True)
class FilterRule:
    name: str
    description: str = ""
    min_urgency: int = 70
    keywords: list[str] = field(default_factory=list)
    trend_labels: list[str] = field(default_factory=list)
    feed_tags: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    require_iocs: bool = False


@dataclass(slots=True)
class MatchResult:
    rule: str
    reason: str


def load_filter_rules(path: str | Path | None = None) -> tuple[int, list[FilterRule]]:
    """Return (default_min_urgency, rules)."""
    filter_path = Path(path) if path else DEFAULT_FILTERS_PATH
    if not filter_path.exists():
        return get_settings().urgency_alert_threshold, []
    data = yaml.safe_load(filter_path.read_text(encoding="utf-8")) or {}
    default_min = int(data.get("defaults", {}).get("min_urgency", 70))
    require_iocs_default = bool(data.get("defaults", {}).get("require_iocs", False))
    rules: list[FilterRule] = []
    for item in data.get("filters", []):
        rules.append(
            FilterRule(
                name=item.get("name", "unnamed"),
                description=item.get("description", ""),
                min_urgency=int(item.get("min_urgency", default_min)),
                keywords=[k.lower() for k in item.get("keywords", [])],
                trend_labels=[t.lower() for t in item.get("trend_labels", [])],
                feed_tags=[t.lower() for t in item.get("feed_tags", [])],
                industries=[i.lower() for i in item.get("industries", [])],
                require_iocs=bool(item.get("require_iocs", require_iocs_default)),
            )
        )
    return default_min, rules


def build_source_tags(feeds: list[object]) -> dict[str, list[str]]:
    """Map feed name -> lower-cased tags (accepts scraper Feed or duck-typed)."""
    tags: dict[str, list[str]] = {}
    for feed in feeds:
        name = getattr(feed, "name", None)
        if not name:
            continue
        tags[name] = [str(t).lower() for t in getattr(feed, "tags", []) or []]
    return tags


class FilterEngine:
    def __init__(
        self,
        rules: list[FilterRule],
        source_tags: dict[str, list[str]] | None = None,
        default_min_urgency: int = 70,
    ) -> None:
        self.rules = rules
        self.source_tags = source_tags or {}
        self.default_min_urgency = default_min_urgency

    def _text(self, article: Article) -> str:
        return f"{article.title} {article.text}".lower()

    def _rule_matches(self, rule: FilterRule, article: Article, enrichment: Enrichment) -> str | None:
        if enrichment.urgency_score < rule.min_urgency:
            return None

        text = self._text(article)

        if rule.keywords and not any(kw in text for kw in rule.keywords):
            return None

        if rule.trend_labels and enrichment.trend.lower() not in rule.trend_labels:
            return None

        if rule.feed_tags:
            tags = self.source_tags.get(article.source, [])
            if not any(t in tags for t in rule.feed_tags):
                return None

        if rule.require_iocs and not enrichment.iocs:
            return None

        details = []
        if enrichment.trend and enrichment.trend != "unknown":
            details.append(f"trend={enrichment.trend}")
        details.append(f"urgency={enrichment.urgency_score}")
        if enrichment.iocs:
            details.append(f"iocs={sum(len(v) for v in enrichment.iocs.values())}")
        return f"matched '{rule.name}' ({', '.join(details)})"

    def evaluate(self, article: Article, enrichment: Enrichment) -> MatchResult | None:
        """Return the first matching rule, or None."""
        for rule in self.rules:
            reason = self._rule_matches(rule, article, enrichment)
            if reason:
                return MatchResult(rule=rule.name, reason=reason)
        return None

    def evaluate_default(self, article: Article, enrichment: Enrichment) -> MatchResult | None:
        """Fallback: alert purely on the global urgency threshold."""
        if enrichment.urgency_score >= self.default_min_urgency:
            return MatchResult(
                rule="default-threshold",
                reason=f"urgency={enrichment.urgency_score} >= {self.default_min_urgency}",
            )
        return None

    def should_alert(self, article: Article, enrichment: Enrichment) -> MatchResult | None:
        return self.evaluate(article, enrichment) or self.evaluate_default(article, enrichment)
