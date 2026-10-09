"""Indicator-of-Compromise (IOC) extraction using deterministic regexes.

Kept provider-independent and side-effect free for easy unit testing.
"""

from __future__ import annotations

import re

PATTERNS: dict[str, re.Pattern[str]] = {
    "cve": re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE),
    "ipv4": re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"),
    "domain": re.compile(
        r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
        r"(?:com|net|org|io|ru|cn|top|xyz|info|biz|onion|co|gov|edu|me|tk)\b",
        re.IGNORECASE,
    ),
    "md5": re.compile(r"\b[a-fA-F0-9]{32}\b"),
    "sha1": re.compile(r"\b[a-fA-F0-9]{40}\b"),
    "sha256": re.compile(r"\b[a-fA-F0-9]{64}\b"),
    "url": re.compile(r"\bhttps?://[^\s<>\"')]+", re.IGNORECASE),
    "email": re.compile(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b", re.IGNORECASE),
}

_PRIVATE_IP = re.compile(
    r"^(?:10\.|127\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.|0\.|255\.)"
)

_SKIP_DOMAINS = {
    "example.com",
    "wikipedia.org",
    "github.com",
    "google.com",
}

_HASH_CAPTURE_ORDER = ("sha256", "sha1", "md5")


def _valid_ip(ip: str) -> bool:
    return not _PRIVATE_IP.match(ip)


def extract_iocs(text: str, include_private_ips: bool = False) -> dict[str, list[str]]:
    """Return a mapping of IOC type -> sorted unique values."""
    if not text:
        return {}
    found: dict[str, set[str]] = {key: set() for key in PATTERNS}

    hash_spans: list[tuple[int, int]] = []
    for kind in _HASH_CAPTURE_ORDER:
        for m in PATTERNS[kind].finditer(text):
            # avoid reporting a SHA-256 also as shorter hashes
            if any(start <= m.start() and m.end() <= end for start, end in hash_spans):
                continue
            found[kind].add(m.group(0).lower())
            hash_spans.append(m.span())

    for m in PATTERNS["ipv4"].finditer(text):
        ip = m.group(0)
        if include_private_ips or _valid_ip(ip):
            found["ipv4"].add(ip)

    for m in PATTERNS["domain"].finditer(text):
        domain = m.group(0).lower()
        if domain not in _SKIP_DOMAINS:
            found["domain"].add(domain)

    for key in ("cve", "url", "email"):
        for m in PATTERNS[key].finditer(text):
            value = m.group(0)
            found[key].add(value.upper() if key == "cve" else value)

    return {k: sorted(v) for k, v in found.items() if v}


def ioc_summary(iocs: dict[str, list[str]], max_per_type: int = 5) -> str:
    """Human readable one-line summary, e.g. ``cve: 2, domain: 1``."""
    parts = [f"{kind}: {len(vals)}" for kind, vals in sorted(iocs.items()) if vals]
    return ", ".join(parts) if parts else "none"
