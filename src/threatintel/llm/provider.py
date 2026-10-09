"""LLM provider abstraction.

Ships with a dependency-free :class:`ExtractiveProvider` used by default (and by
CI). The Hugging Face provider is loaded lazily only when requested so importing
this module never pulls in ``torch``/``transformers``.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections import Counter

# Severity baseline per trend label (0-100).
TREND_SEVERITY: dict[str, int] = {
    "zero-day exploit": 88,
    "ransomware": 82,
    "apt campaign": 82,
    "supply chain attack": 80,
    "data breach": 76,
    "malware": 66,
    "denial of service": 64,
    "vulnerability": 60,
    "phishing": 58,
    "unknown": 40,
}

# Keyword -> weight used by the extractive urgency heuristic.
URGENCY_KEYWORDS: dict[str, int] = {
    "zero-day": 25,
    "0-day": 25,
    "actively exploited": 22,
    "in the wild": 18,
    "ransomware": 18,
    "critical": 14,
    "remote code execution": 18,
    "rce": 14,
    "data breach": 14,
    "emergency": 12,
    "patch immediately": 14,
    "exploit": 10,
    "cve-": 8,
    "malware": 8,
    "backdoor": 12,
    "botnet": 10,
    "phishing": 6,
}

NEGATIVE_WORDS = {
    "attack",
    "exploit",
    "breach",
    "malware",
    "ransomware",
    "vulnerability",
    "threat",
    "compromise",
    "hack",
    "critical",
    "danger",
    "warning",
    "leak",
}
POSITIVE_WORDS = {"secure", "patched", "fixed", "mitigated", "protected", "resolved"}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


class LLMProvider(ABC):
    """Interface every provider must implement."""

    name: str = "base"

    @abstractmethod
    def summarize(self, text: str, max_points: int = 4) -> list[str]:
        """Return concise bullet points for the given text."""

    @abstractmethod
    def classify_trend(self, text: str, labels: list[str]) -> tuple[str, float]:
        """Return the best matching trend label and a confidence in [0, 1]."""

    @abstractmethod
    def score_urgency(self, text: str, trend: str, trend_confidence: float) -> tuple[int, str]:
        """Return an urgency score (0-100) and a sentiment label."""


class ExtractiveProvider(LLMProvider):
    """Deterministic, offline provider based on lexical heuristics.

    Fast, dependency-free and used for tests / environments without GPU.
    """

    name = "extractive"

    def __init__(self, stopwords: set[str] | None = None) -> None:
        self._stop = stopwords or {
            "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
            "is", "are", "was", "were", "be", "been", "by", "as", "at", "from", "that",
            "this", "it", "its", "has", "have", "had", "will", "would", "can", "could",
            "which", "who", "when", "where", "how", "their", "they", "them", "you",
            "your", "we", "our", "not", "no", "if", "than", "then", "into", "over",
        }

    # --------------------------------------------------------------- summarize
    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [s.strip() for s in _SENT_SPLIT.split(text.strip()) if len(s.strip()) > 30]

    def _word_freq(self, sentences: list[str]) -> Counter[str]:
        freq: Counter[str] = Counter()
        for sent in sentences:
            for word in re.findall(r"[a-z0-9\-]+", sent.lower()):
                if word not in self._stop and len(word) > 2:
                    freq[word] += 1
        return freq

    def summarize(self, text: str, max_points: int = 4) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []
        sentences = self._sentences(text) or [text]
        freq = self._word_freq(sentences)
        max_freq = max(freq.values(), default=1)

        scored: list[tuple[float, int, str]] = []
        for idx, sent in enumerate(sentences):
            words = re.findall(r"[a-z0-9\-]+", sent.lower())
            if not words:
                continue
            score = sum(freq.get(w, 0) / max_freq for w in words) / len(words)
            # reward position and "interesting" tokens
            score += 0.15 if idx == 0 else 0.0
            low = sent.lower()
            for token in ("cve-", "zero-day", "exploit", "ransomware", "breach", "rce"):
                if token in low or (token == "rce" and re.search(r"\brce\b", low)):
                    score += 0.25
            scored.append((score, idx, sent))

        scored.sort(key=lambda t: (-t[0], t[1]))
        selected = sorted(scored[:max_points], key=lambda t: t[1])
        bullets: list[str] = []
        for _, _, sent in selected:
            cleaned = sent if sent.endswith((".", "!", "?")) else f"{sent}."
            bullets.append(cleaned)
        return bullets

    # ------------------------------------------------------------- trend classify
    def classify_trend(self, text: str, labels: list[str]) -> tuple[str, float]:
        low = (text or "").lower()
        if not low.strip():
            return "unknown", 0.0
        scores: dict[str, int] = {}
        for label in labels:
            score = 0
            for token in label.lower().split():
                if token in ("and", "of"):
                    continue
                if token.rstrip("s") in low or token in low:
                    score += 1
            # label-specific strong signals
            if label.lower() == "zero-day exploit" and re.search(r"zero-?day|0-day", low):
                score += 3
            if label.lower() == "ransomware" and "ransom" in low:
                score += 2
            if label.lower() == "data breach" and ("breach" in low or "leak" in low):
                score += 2
            if label.lower() == "apt campaign" and re.search(r"\bapt\d+\b|espionage|nation-state", low):
                score += 2
            if label.lower() == "phishing" and ("phish" in low or "credential" in low):
                score += 2
            scores[label] = score

        best = max(scores, key=lambda k: scores[k])
        best_score = scores[best]
        if best_score == 0:
            return "unknown", 0.0
        total = sum(scores.values()) or 1
        # blend relative dominance with an absolute-signal factor
        confidence = round(min(0.99, 0.5 * (best_score / total) + 0.5 * min(1.0, best_score / 4)), 2)
        return best, confidence

    # ---------------------------------------------------------------- urgency
    def score_urgency(self, text: str, trend: str, trend_confidence: float) -> tuple[int, str]:
        low = (text or "").lower()
        base = TREND_SEVERITY.get(trend.lower(), TREND_SEVERITY["unknown"])
        score = base * (0.6 + 0.4 * max(0.0, min(1.0, trend_confidence)))

        for kw, weight in URGENCY_KEYWORDS.items():
            if kw in low:
                score += weight

        sentiment = self._sentiment(low)
        score = int(max(0, min(100, round(score))))
        return score, sentiment

    def _sentiment(self, low: str) -> str:
        neg = sum(1 for w in NEGATIVE_WORDS if w in low)
        pos = sum(1 for w in POSITIVE_WORDS if w in low)
        if neg > pos:
            return "negative"
        if pos > neg:
            return "positive"
        return "neutral"


def get_provider(name: str | None = None) -> LLMProvider:
    """Factory returning the configured provider instance."""
    from ..config import get_settings

    provider = (name or get_settings().llm_provider or "extractive").strip().lower()
    if provider in ("extractive", "heuristic", "offline"):
        return ExtractiveProvider()
    if provider in ("huggingface", "hf", "local"):
        from .hf_provider import HuggingFaceProvider

        return HuggingFaceProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}")
