"""Thought evolution analysis — track how opinions, values, and interests shift over time."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np

from ..scraper.models import ZhihuAnswer
from ..nlp.preprocessing import TextPreprocessor
from ..nlp.sentiment import SentimentAnalyzer


@dataclass
class EvolutionPoint:
    """A point in the user's thought evolution."""

    date: Optional[datetime] = None
    period: str = ""
    dominant_topics: list[str] = field(default_factory=list)
    sentiment_score: float = 0.5
    avg_answer_length: int = 0
    answer_count: int = 0
    key_phrases: list[str] = field(default_factory=list)


@dataclass
class ThoughtEvolution:
    """Complete thought evolution profile."""

    evolution_points: list[EvolutionPoint] = field(default_factory=list)
    topic_trends: dict[str, list[float]] = field(default_factory=dict)
    sentiment_trend: list[float] = field(default_factory=list)
    length_trend: list[int] = field(default_factory=list)
    summary: str = ""


class EvolutionAnalyzer:
    """Analyze how a user's thinking changes over time."""

    # Topic transitions — phrases indicating changed thinking
    TRANSITION_MARKERS = [
        r"(以前|过去|曾经|原来)[^，。]{0,30}(现在|如今|后来)",
        r"(不再|不再那么|再也不)",
        r"(突然|忽然|慢慢|渐渐)[^，。]{0,20}(意识到|发现|明白|懂了)",
        r"(改变|转变|修正|调整)[了]?(想法|观点|看法|态度)",
    ]

    def __init__(self):
        self.preprocessor = TextPreprocessor()
        self.sentiment = SentimentAnalyzer()

    def analyze(self, answers: list[ZhihuAnswer]) -> ThoughtEvolution:
        if not answers:
            return ThoughtEvolution()

        sorted_answers = sorted(
            [a for a in answers if a.created_time],
            key=lambda a: a.created_time,
        )

        if not sorted_answers:
            return ThoughtEvolution()

        # Group by period (quarterly for many answers, yearly for few)
        if len(sorted_answers) >= 12:
            points = self._group_by_quarter(sorted_answers)
        else:
            points = self._group_by_semester(sorted_answers)

        # Track topic trends
        topic_trends = self._track_topic_trends(points)

        # Build sentiment trend
        sentiment_trend = [p.sentiment_score for p in points]
        length_trend = [p.avg_answer_length for p in points]

        # Generate summary
        summary = self._generate_summary(points, topic_trends, sentiment_trend, sorted_answers)

        return ThoughtEvolution(
            evolution_points=points,
            topic_trends=topic_trends,
            sentiment_trend=sentiment_trend,
            length_trend=length_trend,
            summary=summary,
        )

    def _group_by_quarter(self, answers: list[ZhihuAnswer]) -> list[EvolutionPoint]:
        """Group answers by quarter."""
        groups = defaultdict(list)
        for a in answers:
            dt = a.created_time
            key = f"{dt.year}Q{(dt.month-1)//3+1}"
            groups[key].append(a)

        return [self._make_point(key, group) for key, group in sorted(groups.items())]

    def _group_by_semester(self, answers: list[ZhihuAnswer]) -> list[EvolutionPoint]:
        """Group answers by half-year."""
        groups = defaultdict(list)
        for a in answers:
            dt = a.created_time
            key = f"{dt.year}{'上' if dt.month <= 6 else '下'}半年"
            groups[key].append(a)

        return [self._make_point(key, group) for key, group in sorted(groups.items())]

    def _make_point(self, period: str, answers: list[ZhihuAnswer]) -> EvolutionPoint:
        """Create an EvolutionPoint from a group of answers."""
        sentiments = [self.sentiment.analyze_single(a.content).score for a in answers]
        avg_sent = float(np.mean(sentiments)) if sentiments else 0.5
        avg_len = int(np.mean([len(a.content) for a in answers])) if answers else 0

        # Find dominant topics via keyword frequency
        word_freq = self.preprocessor.get_word_frequency(
            [a.content for a in answers], top_k=10
        )

        # Find key phrases (transition markers)
        key_phrases = []
        for a in answers:
            for pattern in self.TRANSITION_MARKERS:
                matches = re.findall(pattern, a.content)
                for m in matches:
                    if isinstance(m, tuple):
                        m = "".join(m)
                    if len(m) > 4 and m not in key_phrases:
                        key_phrases.append(m[:50])

        return EvolutionPoint(
            period=period,
            dominant_topics=[w for w, _ in word_freq[:5]],
            sentiment_score=round(avg_sent, 3),
            avg_answer_length=avg_len,
            answer_count=len(answers),
            key_phrases=key_phrases[:5],
        )

    def _track_topic_trends(self, points: list[EvolutionPoint]) -> dict[str, list[float]]:
        """Track how topic engagement changes over time."""
        topic_scores = defaultdict(list)
        all_topics = set()
        for p in points:
            all_topics.update(p.dominant_topics)

        for topic in all_topics:
            for p in points:
                score = 1.0 if topic in p.dominant_topics else 0.0
                topic_scores[topic].append(score)

        return dict(topic_scores)

    def _generate_summary(
        self,
        points: list[EvolutionPoint],
        topic_trends: dict,
        sentiment_trend: list[float],
        answers: list[ZhihuAnswer],
    ) -> str:
        """Generate human-readable evolution summary."""
        parts = []

        if len(points) < 2:
            parts.append("时间跨度较短，暂未观察到明显的思维演变轨迹。")
            return "\n".join(parts)

        # Sentiment trajectory
        first_sent = sentiment_trend[0]
        last_sent = sentiment_trend[-1]
        sent_change = last_sent - first_sent

        if abs(sent_change) < 0.1:
            parts.append("情感基调保持稳定，情绪管理能力较强。")
        elif sent_change > 0.1:
            parts.append(f"情感趋势：从 {first_sent:.2f} → {last_sent:.2f}，整体走向更加积极乐观。")
        else:
            parts.append(f"情感趋势：从 {first_sent:.2f} → {last_sent:.2f}，近期表达更加严肃深沉。")

        # Topic evolution
        new_topics = set()
        old_topics = set()
        mid = len(points) // 2
        for p in points[:mid]:
            old_topics.update(p.dominant_topics)
        for p in points[mid:]:
            new_topics.update(p.dominant_topics)

        added = new_topics - old_topics
        dropped = old_topics - new_topics

        if added:
            parts.append(f"新增关注方向：{'、'.join(list(added)[:5])}")
        if dropped:
            parts.append(f"不再频繁讨论：{'、'.join(list(dropped)[:5])}")

        # Length trend
        length_trend = [p.avg_answer_length for p in points]
        if len(length_trend) >= 3:
            early_avg = np.mean(length_trend[:2]) if len(length_trend) >= 2 else length_trend[0]
            late_avg = np.mean(length_trend[-2:]) if len(length_trend) >= 2 else length_trend[-1]
            if late_avg > early_avg * 1.5:
                parts.append("回答篇幅增长明显，显示出持续深度的思考习惯。")
            elif late_avg < early_avg * 0.6:
                parts.append("近期回答更加精炼，可能转向结构化表达。")

        # Transition phrases
        all_transitions = []
        for p in points:
            all_transitions.extend(p.key_phrases)

        if all_transitions:
            parts.append(f"思维转变迹象（{len(all_transitions)}处）：")
            for t in all_transitions[:5]:
                parts.append(f"  · {t}")

        return "\n".join(parts)
