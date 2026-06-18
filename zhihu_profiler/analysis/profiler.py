"""Main profiler: orchestrates all analysis modules to produce a complete user profile."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..scraper.models import ScrapedData, ZhihuUser, ZhihuAnswer
from ..nlp.preprocessing import TextPreprocessor
from ..nlp.sentiment import SentimentAnalyzer, AggregateSentiment
from .personality import PersonalityAnalyzer, PersonalityProfile
from .interests import InterestAnalyzer, InterestProfile
from .values import ValueAnalyzer, ValueProfile
from .style import StyleAnalyzer, StyleProfile
from .timeline import TimelineBuilder, PersonalTimeline
from .evolution import EvolutionAnalyzer, ThoughtEvolution
from .concrete import ConcreteExtractor, ConcreteProfile
from .professional import ProfessionalAnalyzer, ProfessionalImage

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """Complete user profile with all analysis dimensions."""

    # Identity
    user: Optional[dict] = None
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Data stats
    total_answers: int = 0
    total_chars: int = 0
    total_upvotes: int = 0
    date_range: Optional[tuple[str, str]] = None

    # Analysis dimensions
    personality: Optional[dict] = None
    interests: Optional[dict] = None
    values: Optional[dict] = None
    style: Optional[dict] = None
    sentiment: Optional[dict] = None

    # Deep analysis
    timeline: Optional[dict] = None
    evolution: Optional[dict] = None
    concrete: Optional[dict] = None
    professional: Optional[dict] = None

    # Meta
    keywords: list[tuple[str, float]] = field(default_factory=list)
    summary: str = ""


class Profiler:
    """Main profiler that runs all analysis pipelines."""

    def __init__(
        self,
        enable_sentiment: bool = True,
        enable_personality: bool = True,
        enable_interests: bool = True,
        enable_values: bool = True,
        enable_style: bool = True,
    ):
        self.preprocessor = TextPreprocessor()
        self.sentiment_analyzer = SentimentAnalyzer() if enable_sentiment else None
        self.personality_analyzer = PersonalityAnalyzer() if enable_personality else None
        self.interest_analyzer = InterestAnalyzer() if enable_interests else None
        self.value_analyzer = ValueAnalyzer() if enable_values else None
        self.style_analyzer = StyleAnalyzer() if enable_style else None
        self.timeline_builder = TimelineBuilder()
        self.evolution_analyzer = EvolutionAnalyzer()
        self.concrete_extractor = ConcreteExtractor()
        self.professional_analyzer = ProfessionalAnalyzer()

        self.modules_enabled = {
            "sentiment": enable_sentiment,
            "personality": enable_personality,
            "interests": enable_interests,
            "values": enable_values,
            "style": enable_style,
        }

    def profile(self, data: ScrapedData) -> UserProfile:
        """Run full profiling pipeline on scraped data."""
        logger.info(f"Starting profiling for {data.user.name}")
        logger.info(f"Processing {len(data.answers)} answers ({data.total_text_chars} chars)")

        profile = UserProfile()

        # Extract user identity
        profile.user = data.user.model_dump()
        profile.total_answers = data.answers_scraped
        profile.total_chars = data.total_text_chars
        profile.total_upvotes = data.total_upvotes

        # Extract date range
        if data.answers:
            dates = [a.created_time for a in data.answers if a.created_time]
            if dates:
                dates.sort()
                profile.date_range = (
                    dates[0].strftime("%Y-%m-%d"),
                    dates[-1].strftime("%Y-%m-%d"),
                )

        # Extract answer texts
        answer_texts = [a.content for a in data.answers if a.content]
        combined_text = self.preprocessor.get_combined_text(answer_texts)

        if not combined_text:
            logger.warning("No text content to analyze")
            return profile

        # Extract all question topics
        all_topics = [a.question_topics for a in data.answers if a.question_topics]

        # 1. Keywords
        logger.info("Extracting keywords...")
        profile.keywords = self.preprocessor.extract_keywords_tfidf(answer_texts, top_k=30)

        # 2. Sentiment analysis
        if self.sentiment_analyzer:
            logger.info("Analyzing sentiment...")
            sentiment = self.sentiment_analyzer.analyze_batch(answer_texts)
            profile.sentiment = {
                "overall_score": sentiment.overall_score,
                "positive_ratio": sentiment.positive_ratio,
                "negative_ratio": sentiment.negative_ratio,
                "neutral_ratio": sentiment.neutral_ratio,
                "score_std": sentiment.score_std,
                "trend": sentiment.sentiment_trend,
                "description": sentiment.description,
                "emotional_stability": sentiment.emotional_stability,
            }

        # 3. Personality analysis
        if self.personality_analyzer:
            logger.info("Analyzing personality...")
            personality = self.personality_analyzer.analyze(combined_text)
            profile.personality = {
                "big_five": personality.big_five.to_dict(),
                "cognitive_style": personality.cognitive_style,
                "social_orientation": personality.social_orientation,
                "risk_tolerance": personality.risk_tolerance,
                "summary": personality.summary,
            }

        # 4. Interest analysis
        if self.interest_analyzer:
            logger.info("Analyzing interests...")
            interests = self.interest_analyzer.analyze_combined(combined_text, all_topics)
            profile.interests = {
                "primary_domain": interests.primary_domain,
                "top_domains": interests.top_domains,
                "category_balance": interests.category_balance,
                "summary": interests.summary,
            }

        # 5. Value analysis
        if self.value_analyzer:
            logger.info("Analyzing values...")
            values = self.value_analyzer.analyze(combined_text)
            profile.values = {
                "value_scores": values.value_scores,
                "core_values": values.core_values,
                "value_tensions": values.value_tensions,
                "summary": values.summary,
            }

        # 6. Writing style analysis
        if self.style_analyzer:
            logger.info("Analyzing writing style...")
            style = self.style_analyzer.analyze(answer_texts)
            profile.style = {
                "avg_sentence_length": style.avg_sentence_length,
                "avg_answer_length": style.avg_answer_length,
                "avg_paragraph_length": style.avg_paragraph_length,
                "punctuation_style": style.punctuation_style,
                "structural_style": style.structural_style,
                "tone_style": style.tone_style,
                "rhetorical_devices": style.rhetorical_devices,
                "vocabulary_richness": style.vocabulary_richness,
                "first_person_ratio": style.first_person_ratio,
                "summary": style.summary,
            }

        # 7. Personal timeline
        logger.info("Building personal timeline...")
        timeline = self.timeline_builder.build(data.answers)
        profile.timeline = {
            "events": [
                {
                    "date": e.date_str or (e.date.strftime("%Y-%m") if e.date else ""),
                    "category": e.category,
                    "description": e.description,
                    "answer_title": e.answer_title,
                }
                for e in timeline.events[:20]
            ],
            "phases": timeline.phases,
            "key_turns": timeline.key_turns[:10],
            "summary": timeline.summary,
        }

        # 8. Thought evolution
        logger.info("Analyzing thought evolution...")
        evolution = self.evolution_analyzer.analyze(data.answers)
        profile.evolution = {
            "points": [
                {
                    "period": p.period,
                    "topics": p.dominant_topics,
                    "sentiment": p.sentiment_score,
                    "avg_length": p.avg_answer_length,
                    "answer_count": p.answer_count,
                    "transition_phrases": p.key_phrases,
                }
                for p in evolution.evolution_points
            ],
            "sentiment_trend": evolution.sentiment_trend,
            "length_trend": evolution.length_trend,
            "summary": evolution.summary,
        }

        # 9. Concrete details + representative quotes
        logger.info("Extracting concrete details...")
        concrete = self.concrete_extractor.extract(data.answers)
        profile.concrete = {
            "bio_facts": [
                {"label": f.label, "value": f.value, "source": f.source_answer}
                for f in concrete.bio_facts
            ],
            "quotes": [
                {"text": q.text, "title": q.answer_title, "trait": q.trait}
                for q in concrete.quotes
            ],
            "narrative_summary": concrete.narrative_summary,
        }

        # 10. Professional image
        logger.info("Analyzing professional image...")
        professional = self.professional_analyzer.analyze(data.answers)
        profile.professional = {
            "career_stage": {
                "level": professional.career_stage.level,
                "years": professional.career_stage.years_exp,
                "summary": professional.career_stage.summary,
            },
            "skills": {
                "hard": professional.skills.hard_skills,
                "soft": professional.skills.soft_skills,
                "domains": professional.skills.expertise_domains,
                "summary": professional.skills.summary,
            },
            "work_values": {
                "motivations": professional.work_values.motivations,
                "preferences": professional.work_values.preferences,
                "attitudes": professional.work_values.attitudes,
                "summary": professional.work_values.summary,
            },
            "industry_insight": {
                "industries": professional.industry_insight.industries,
                "depth": professional.industry_insight.depth_score,
                "summary": professional.industry_insight.summary,
            },
            "quotes": professional.professional_quotes,
            "summary": professional.summary,
        }

        # Generate overall summary
        profile.summary = self._generate_overall_summary(profile)

        logger.info("Profiling complete!")
        return profile

    def _generate_overall_summary(self, profile: UserProfile) -> str:
        """Generate an executive summary of the profile."""
        user_name = profile.user.get("name", "未知用户") if profile.user else "未知用户"
        parts = [f"# {user_name} · 知乎人物画像"]

        # Basic stats
        parts.append(f"\n## 基础数据")
        parts.append(f"- 回答数：{profile.total_answers}")
        parts.append(f"- 总字数：{profile.total_chars:,}")
        parts.append(f"- 总赞同：{profile.total_upvotes:,}")
        if profile.date_range:
            parts.append(f"- 时间跨度：{profile.date_range[0]} ~ {profile.date_range[1]}")

        # Personality
        if profile.personality:
            parts.append(f"\n## 人格特征")
            parts.append(profile.personality.get("summary", ""))

        # Interests
        if profile.interests:
            parts.append(f"\n## 兴趣领域")
            parts.append(profile.interests.get("summary", ""))

        # Values
        if profile.values:
            parts.append(f"\n## 价值体系")
            parts.append(profile.values.get("summary", ""))

        # Sentiment
        if profile.sentiment:
            parts.append(f"\n## 情感基调")
            parts.append(profile.sentiment.get("description", ""))

        # Style
        if profile.style:
            parts.append(f"\n## 表达风格")
            parts.append(profile.style.get("summary", ""))

        # Timeline
        if profile.timeline:
            parts.append(f"\n## 个人时间线")
            parts.append(profile.timeline.get("summary", ""))

        # Evolution
        if profile.evolution:
            parts.append(f"\n## 思想演变")
            parts.append(profile.evolution.get("summary", ""))

        # Concrete details
        if profile.concrete:
            ns = profile.concrete.get("narrative_summary", "")
            if ns.strip():
                parts.append(f"\n## 具体画像")
                parts.append(ns)

        # Professional image
        if profile.professional:
            parts.append(f"\n## 职业形象")
            parts.append(profile.professional.get("summary", ""))

        return "\n".join(parts)

    def save_profile(self, profile: UserProfile, path: Path) -> None:
        """Save profile to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(profile), f, ensure_ascii=False, indent=2)
        logger.info(f"Profile saved to {path}")

    @staticmethod
    def load_profile(path: Path) -> UserProfile:
        """Load profile from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return UserProfile(**data)
