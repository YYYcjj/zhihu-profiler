"""Personal timeline construction from answer texts.

Extracts temporal cues, key life events, transitions, and builds a chronological narrative.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..scraper.models import ZhihuAnswer


# Time-related patterns
TIME_PATTERNS = {
    "year": re.compile(r"(\d{4})\s*年"),
    "age": re.compile(r"(\d{1,2})\s*岁[那的]?时候"),
    "phase": re.compile(r"(大学|高中|初中|研究生|博士|毕业|入职|离职|辞职|跳槽|创业|结婚|生[子孩]|离婚|分手)"),
    "duration": re.compile(r"(\d+)\s*(年|个月|月|周|天)[来前以]"),
    "milestone": re.compile(r"(第[一二三四五六七八九十\d]次|[五六七十八九十\d]年前|刚[刚才]|最近|去年|今年|明年|前[几些]年|[一二三五六七八九十\d]年前)"),
}

# Event indicators
EVENT_INDICATORS = {
    "职业转变": ["跳槽", "换工作", "离职", "辞职", "转行", "入职", "升职", "晋升", "裁员", "优化", "裸辞", "offer", "面试", "创业"],
    "教育经历": ["毕业", "大学", "高考", "考研", "读研", "博士", "留学", "辍学", "退学", "考试", "论文", "答辩", "学位"],
    "关系变化": ["结婚", "离婚", "分手", "恋爱", "对象", "相亲", "孩子", "生子", "家庭", "父母", "在一起"],
    "迁移变化": ["搬家", "北漂", "沪漂", "深漂", "出国", "回国", "去.*城市", "离开", "搬来"],
    "健康转折": ["生病", "住院", "手术", "抑郁", "焦虑", "康复", "减肥", "健身", "熬夜", "失眠"],
    "财务变化": ["买房", "首付", "房贷", "负债", "存款", "财务自由", "FIRE", "投资", "亏", "赚"],
    "认知突破": ["顿悟", "突然明白", "意识到", "醒悟", "改变.*想法", "以前.*现在", "不再", "终于", "后来才"],
    "重大决策": ["决定", "放弃", "选择", "要不要", "该不该", "人生规划", "未来.*方向"],
}


@dataclass
class TimelineEvent:
    """A single event on the personal timeline."""

    date: Optional[datetime] = None
    date_str: str = ""
    category: str = ""
    description: str = ""
    answer_url: str = ""
    answer_title: str = ""
    confidence: float = 1.0


@dataclass
class PersonalTimeline:
    """Complete personal timeline."""

    events: list[TimelineEvent] = field(default_factory=list)
    phases: list[dict] = field(default_factory=list)
    key_turns: list[str] = field(default_factory=list)
    summary: str = ""


class TimelineBuilder:
    """Build a personal timeline from Zhihu answers."""

    def __init__(self):
        pass

    def build(self, answers: list[ZhihuAnswer]) -> PersonalTimeline:
        if not answers:
            return PersonalTimeline()

        # Sort answers by time
        sorted_answers = sorted(
            [a for a in answers if a.created_time],
            key=lambda a: a.created_time,
        )

        events = []
        for answer in sorted_answers:
            extracted = self._extract_events(answer)
            events.extend(extracted)

        # Group by category
        grouped = defaultdict(list)
        for e in events:
            grouped[e.category].append(e)

        # Identify phases
        phases = self._identify_phases(sorted_answers)

        # Identify key turning points
        key_turns = self._identify_turning_points(events)

        # Generate summary
        summary = self._generate_summary(events, phases, key_turns, sorted_answers)

        return PersonalTimeline(
            events=events,
            phases=phases,
            key_turns=key_turns,
            summary=summary,
        )

    def _extract_events(self, answer: ZhihuAnswer) -> list[TimelineEvent]:
        """Extract events from a single answer."""
        text = answer.content
        events = []

        # Check each event category
        for category, markers in EVENT_INDICATORS.items():
            for marker in markers:
                if re.search(marker, text):
                    # Try to extract time context
                    date_str = self._extract_time(text)
                    date = self._parse_date(date_str, answer.created_time)

                    # Extract surrounding context (sentence with the marker)
                    context = self._extract_context(text, marker)

                    events.append(TimelineEvent(
                        date=date or answer.created_time,
                        date_str=date_str,
                        category=category,
                        description=context[:200],
                        answer_url=answer.url,
                        answer_title=answer.question_title,
                        confidence=0.7,
                    ))
                    break  # One event per category per answer

        return events

    def _extract_time(self, text: str) -> str:
        """Extract time references from text."""
        for name, pattern in TIME_PATTERNS.items():
            match = pattern.search(text)
            if match:
                return match.group(0)
        return ""

    def _parse_date(self, date_str: str, fallback: Optional[datetime]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return fallback

        # Try year pattern
        year_match = re.search(r"(\d{4})", date_str)
        if year_match:
            year = int(year_match.group(1))
            if 2000 <= year <= 2030:
                return datetime(year, 1, 1)

        return fallback

    def _extract_context(self, text: str, marker: str) -> str:
        """Extract the sentence containing the marker."""
        sentences = re.split(r"[。！？;；\n]", text)
        for s in sentences:
            if marker in s:
                return s.strip()[:200]
        return ""

    def _identify_phases(self, answers: list[ZhihuAnswer]) -> list[dict]:
        """Identify life phases from answer patterns."""
        if not answers:
            return []

        phases = []
        # Group answers by year
        by_year = defaultdict(list)
        for a in answers:
            if a.created_time:
                year = a.created_time.year
                by_year[year].append(a)

        for year in sorted(by_year.keys()):
            year_answers = by_year[year]
            # Determine dominant themes for this year
            themes = self._get_dominant_themes(year_answers)

            phases.append({
                "year": year,
                "answer_count": len(year_answers),
                "total_upvotes": sum(a.voteup_count for a in year_answers),
                "themes": themes,
                "avg_answer_length": sum(len(a.content) for a in year_answers) // max(len(year_answers), 1),
            })

        return phases

    def _get_dominant_themes(self, answers: list[ZhihuAnswer]) -> list[str]:
        """Get dominant discussion themes."""
        theme_counts = defaultdict(int)
        for a in answers:
            text = a.content + a.question_title
            for category, markers in EVENT_INDICATORS.items():
                for marker in markers:
                    if re.search(marker, text):
                        theme_counts[category] += 1
                        break

        ranked = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        return [t for t, c in ranked[:3] if c >= 1]

    def _identify_turning_points(self, events: list[TimelineEvent]) -> list[str]:
        """Identify key turning points."""
        # Special events that indicate major life changes
        turning_categories = ["职业转变", "迁移变化", "关系变化", "认知突破", "重大决策"]
        turns = []
        for e in events:
            if e.category in turning_categories and e.confidence >= 0.7:
                label = f"[{e.category}] {e.description[:80]}"
                if e.date_str:
                    label = f"{e.date_str} {label}"
                turns.append(label)

        return turns[:10]

    def _generate_summary(
        self,
        events: list[TimelineEvent],
        phases: list[dict],
        turns: list[str],
        answers: list[ZhihuAnswer],
    ) -> str:
        """Generate human-readable timeline summary."""
        parts = []

        # Activity span
        if phases:
            first_year = phases[0]["year"]
            last_year = phases[-1]["year"]
            span = last_year - first_year
            parts.append(f"知乎活跃时间跨度：{first_year} - {last_year}（{span}年）")

        # Phases overview
        if len(phases) >= 2:
            active_phase = max(phases, key=lambda p: p["answer_count"])
            long_phase = max(phases, key=lambda p: p["avg_answer_length"])
            parts.append(f"最活跃时期：{active_phase['year']}年（{active_phase['answer_count']}条回答）")
            if long_phase["avg_answer_length"] > 200:
                parts.append(f"深度思考期：{long_phase['year']}年（平均{int(long_phase['avg_answer_length'])}字/回答）")

        # Turning points
        if turns:
            parts.append(f"关键转折点（{len(turns)}个）：")
            for t in turns[:5]:
                parts.append(f"  · {t}")

        # Event distribution
        if events:
            categories = defaultdict(int)
            for e in events:
                categories[e.category] += 1
            top_cats = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:3]
            cat_str = "、".join(f"{c}({n}次)" for c, n in top_cats)
            parts.append(f"主要人生事件：{cat_str}")

        # Growth indication
        if len(answers) >= 5:
            first_half = answers[:len(answers)//2]
            second_half = answers[len(answers)//2:]
            first_avg = sum(len(a.content) for a in first_half) // max(len(first_half), 1)
            second_avg = sum(len(a.content) for a in second_half) // max(len(second_half), 1)
            if second_avg > first_avg * 1.3:
                parts.append("📈 回答篇幅持续增长，显示深度思考习惯在加强")
            elif second_avg < first_avg * 0.7:
                parts.append("📉 近期回答更简洁，可能转向精炼表达")

        return "\n".join(parts)
