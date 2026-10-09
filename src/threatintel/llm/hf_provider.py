"""Hugging Face local provider (summarization + zero-shot trend + sentiment).

Imports of ``transformers``/``torch`` happen inside ``__init__`` so that the rest
of the system runs without the heavy optional dependencies installed.
"""

from __future__ import annotations

import logging
import re

from .provider import TREND_SEVERITY, URGENCY_KEYWORDS, LLMProvider

log = logging.getLogger(__name__)

MAX_INPUT_CHARS = 3000
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


class HuggingFaceProvider(LLMProvider):
    name = "huggingface"

    def __init__(self, summarizer_model: str | None = None, classifier_model: str | None = None) -> None:
        from ..config import get_settings

        settings = get_settings()
        self._summarizer_model = summarizer_model or settings.hf_summarizer_model
        self._classifier_model = classifier_model or settings.hf_classifier_model
        self._cache_dir = str(settings.hf_cache_dir)
        self._summarizer = None
        self._classifier = None
        self._sentiment = None

    # ------------------------------------------------------------- lazy loaders
    def _get_summarizer(self):
        if self._summarizer is None:
            from transformers import pipeline

            log.info("Loading summarizer model: %s", self._summarizer_model)
            self._summarizer = pipeline(
                "summarization",
                model=self._summarizer_model,
                cache_dir=self._cache_dir,
                device=-1,
            )
        return self._summarizer

    def _get_classifier(self):
        if self._classifier is None:
            from transformers import pipeline

            log.info("Loading zero-shot classifier: %s", self._classifier_model)
            self._classifier = pipeline(
                "zero-shot-classification",
                model=self._classifier_model,
                cache_dir=self._cache_dir,
                device=-1,
            )
        return self._classifier

    def _get_sentiment(self):
        if self._sentiment is None:
            from transformers import pipeline

            self._sentiment = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                cache_dir=self._cache_dir,
                device=-1,
            )
        return self._sentiment

    # --------------------------------------------------------------- summarize
    def summarize(self, text: str, max_points: int = 4) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []
        try:
            result = self._get_summarizer()(
                text[:MAX_INPUT_CHARS],
                max_length=140,
                min_length=40,
                do_sample=False,
                truncation=True,
            )
            summary = result[0]["summary_text"].strip()
        except Exception as exc:  # noqa: BLE001
            log.warning("HF summarization failed, falling back to extractive: %s", exc)
            from .provider import ExtractiveProvider

            return ExtractiveProvider().summarize(text, max_points)

        sentences = [s.strip() for s in _SENT_SPLIT.split(summary) if s.strip()]
        if not sentences:
            sentences = [summary]
        return sentences[:max_points]

    # ----------------------------------------------------------- trend classify
    def classify_trend(self, text: str, labels: list[str]) -> tuple[str, float]:
        text = (text or "").strip()
        if not text or not labels:
            return "unknown", 0.0
        try:
            result = self._get_classifier()(text[:MAX_INPUT_CHARS], candidate_labels=labels)
            return result["labels"][0], float(round(result["scores"][0], 2))
        except Exception as exc:  # noqa: BLE001
            log.warning("HF classification failed, falling back to extractive: %s", exc)
            from .provider import ExtractiveProvider

            return ExtractiveProvider().classify_trend(text, labels)

    # ---------------------------------------------------------------- urgency
    def score_urgency(self, text: str, trend: str, trend_confidence: float) -> tuple[int, str]:
        low = (text or "").lower()
        base = TREND_SEVERITY.get(trend.lower(), TREND_SEVERITY["unknown"])
        score = base * (0.6 + 0.4 * max(0.0, min(1.0, trend_confidence)))
        for kw, weight in URGENCY_KEYWORDS.items():
            if kw in low:
                score += weight

        sentiment = "neutral"
        try:
            out = self._get_sentiment()((text or "")[:512])[0]
            label = out["label"].lower()
            if label == "negative":
                sentiment = "negative"
                score += 8 * float(out["score"])
            elif label == "positive":
                sentiment = "positive"
        except Exception as exc:  # noqa: BLE001
            log.debug("HF sentiment failed: %s", exc)

        return int(max(0, min(100, round(score)))), sentiment
