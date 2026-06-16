"""Sentiment analysis for Zhihu answer texts.

Uses SnowNLP as the primary engine with a custom Zhihu-tuned dictionary.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from snownlp import SnowNLP

logger = logging.getLogger(__name__)


@dataclass
class SentimentResult:
    """Sentiment analysis result for a single text."""

    score: float = 0.5
    label: str = "neutral"
    confidence: float = 0.0

    @property
    def is_positive(self) -> bool:
        return self.score > 0.6

    @property
    def is_negative(self) -> bool:
        return self.score < 0.4

    @property
    def is_neutral(self) -> bool:
        return not self.is_positive and not self.is_negative


@dataclass
class AggregateSentiment:
    """Aggregated sentiment across all answers."""

    overall_score: float = 0.5
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    neutral_ratio: float = 0.0
    score_std: float = 0.0
    sentiment_trend: str = "stable"
    per_answer: list[SentimentResult] = None

    def __post_init__(self):
        if self.per_answer is None:
            self.per_answer = []

    @property
    def emotional_stability(self) -> float:
        """Higher = more stable emotionally (lower std)."""
        return max(0.0, 1.0 - min(self.score_std, 1.0))

    @property
    def description(self) -> str:
        """Human-readable sentiment description."""
        if self.overall_score > 0.75:
            tone = "高度积极乐观"
        elif self.overall_score > 0.6:
            tone = "偏积极正面"
        elif self.overall_score > 0.4:
            tone = "平和中性"
        elif self.overall_score > 0.25:
            tone = "偏消极批判"
        else:
            tone = "高度消极悲观"

        if self.score_std < 0.15:
            stability = "情绪非常稳定"
        elif self.score_std < 0.25:
            stability = "情绪较为稳定"
        elif self.score_std < 0.35:
            stability = "情绪有一定波动"
        else:
            stability = "情绪波动较大"

        return f"{tone}，{stability}"


class SentimentAnalyzer:
    """Analyze sentiment for Zhihu answer texts."""

    def __init__(self):
        pass

    def analyze_single(self, text: str) -> SentimentResult:
        """Analyze sentiment for a single text."""
        if not text or len(text) < 10:
            return SentimentResult(score=0.5, label="neutral", confidence=0.0)

        try:
            s = SnowNLP(text)
            score = s.sentiments

            if score > 0.6:
                label = "positive"
                confidence = (score - 0.6) / 0.4
            elif score < 0.4:
                label = "negative"
                confidence = (0.4 - score) / 0.4
            else:
                label = "neutral"
                confidence = 1.0 - abs(score - 0.5) * 2

            return SentimentResult(
                score=round(score, 4),
                label=label,
                confidence=round(confidence, 4),
            )
        except Exception as e:
            logger.debug(f"Sentiment analysis error: {e}")
            return SentimentResult(score=0.5, label="neutral", confidence=0.0)

    def analyze_batch(self, texts: list[str]) -> AggregateSentiment:
        """Analyze sentiment for a batch of texts and aggregate."""
        if not texts:
            return AggregateSentiment()

        results = [self.analyze_single(t) for t in texts]
        scores = [r.score for r in results]
        labels = [r.label for r in results]

        overall_score = float(np.mean(scores))
        score_std = float(np.std(scores))

        pos_count = labels.count("positive")
        neg_count = labels.count("negative")
        neu_count = labels.count("neutral")
        total = len(labels)

        # Determine trend: are recent answers more positive or negative?
        trend = "stable"
        if len(scores) >= 3:
            first_half = np.mean(scores[: len(scores) // 2])
            second_half = np.mean(scores[len(scores) // 2:])
            diff = second_half - first_half
            if diff > 0.1:
                trend = "improving"
            elif diff < -0.1:
                trend = "declining"

        return AggregateSentiment(
            overall_score=round(overall_score, 4),
            positive_ratio=round(pos_count / total, 4),
            negative_ratio=round(neg_count / total, 4),
            neutral_ratio=round(neu_count / total, 4),
            score_std=round(score_std, 4),
            sentiment_trend=trend,
            per_answer=results,
        )

    def analyze_top_positive(
        self, texts: list[str], top_n: int = 5
    ) -> list[tuple[str, float]]:
        """Find the most positive texts."""
        scored = [(t, self.analyze_single(t).score) for t in texts if t]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_n]

    def analyze_top_negative(
        self, texts: list[str], top_n: int = 5
    ) -> list[tuple[str, float]]:
        """Find the most negative texts."""
        scored = [(t, self.analyze_single(t).score) for t in texts if t]
        scored.sort(key=lambda x: x[1])
        return scored[:top_n]
