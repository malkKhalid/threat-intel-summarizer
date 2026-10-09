"""Load and represent configured RSS/Atom feed sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import PROJECT_ROOT

DEFAULT_FEEDS_PATH = PROJECT_ROOT / "config" / "feeds.yaml"


@dataclass(slots=True)
class Feed:
    name: str
    url: str
    tags: list[str] = field(default_factory=list)


def load_feeds(path: str | Path | None = None) -> list[Feed]:
    """Read the feed catalogue from YAML."""
    feed_path = Path(path) if path else DEFAULT_FEEDS_PATH
    if not feed_path.exists():
        raise FileNotFoundError(f"Feeds config not found: {feed_path}")
    data = yaml.safe_load(feed_path.read_text(encoding="utf-8")) or {}
    feeds: list[Feed] = []
    for item in data.get("feeds", []):
        if not item.get("url"):
            continue
        feeds.append(
            Feed(
                name=item.get("name") or item["url"],
                url=item["url"],
                tags=list(item.get("tags", [])),
            )
        )
    return feeds
