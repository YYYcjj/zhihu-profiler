"""Personality trait inference from Zhihu answer texts.

Based on Big Five (OCEAN) model with linguistic markers adapted for Chinese social media.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class BigFiveTraits:
    """Big Five personality trait scores (0-100)."""

    openness: float = 50.0
    conscientiousness: float = 50.0
    extraversion: float = 50.0
    agreeableness: float = 50.0
    neuroticism: float = 50.0

    def to_dict(self) -> dict[str, float]:
        return {
            "openness": round(self.openness, 1),
            "conscientiousness": round(self.conscientiousness, 1),
            "extraversion": round(self.extraversion, 1),
            "agreeableness": round(self.agreeableness, 1),
            "neuroticism": round(self.neuroticism, 1),
        }

    def dominant_trait(self) -> str:
        """Return the most pronounced trait."""
        traits = self.to_dict()
        return max(traits, key=traits.get)


@dataclass
class PersonalityProfile:
    """Complete personality profile."""

    big_five: BigFiveTraits = field(default_factory=BigFiveTraits)
    cognitive_style: str = ""
    social_orientation: str = ""
    risk_tolerance: str = ""
    summary: str = ""


class PersonalityAnalyzer:
    """Infer personality traits from text patterns in Zhihu answers."""

    # Linguistic markers for each Big Five dimension (Chinese)
    OPENNESS_MARKERS: ClassVar[list[str]] = [
        "新", "创新", "尝试", "探索", "想象", "艺术", "创造", "好奇",
        "不同", "变化", "多元", "可能", "或许", "有趣", "独特", "突破",
        "哲学", "抽象", "思考", "理论上", "假设", "创意", "灵感",
    ]

    CONSCIENTIOUSNESS_MARKERS: ClassVar[list[str]] = [
        "完成", "计划", "组织", "准时", "负责", "认真", "努力", "坚持",
        "目标", "效率", "规划", "执行", "自律", "规则", "标准", "细节",
        "任务", "清单", "安排", "准备", "系统", "流程", "纪律",
    ]

    EXTRAVERSION_MARKERS: ClassVar[list[str]] = [
        "朋友", "一起", "聚会", "社交", "热闹", "分享", "聊天", "合作",
        "团队", "交流", "认识", "大家", "互动", "参与", "活动", "兴奋",
        "讨论", "伙伴", "圈子", "认识", "遇到", "一起玩",
    ]

    AGREEABLENESS_MARKERS: ClassVar[list[str]] = [
        "帮助", "理解", "关心", "同情", "合作", "信任", "善良", "包容",
        "感谢", "尊重", "和谐", "温暖", "支持", "鼓励", "照顾", "体贴",
        "善意", "友好", "接纳", "倾听", "感同身受", "换位思考",
    ]

    NEUROTICISM_MARKERS: ClassVar[list[str]] = [
        "焦虑", "担心", "压力", "紧张", "不安", "烦躁", "害怕", "沮丧",
        "难过", "生气", "愤怒", "压抑", "崩溃", "绝望", "痛苦", "受不了",
        "烦", "累", "疲惫", "纠结", "后悔", "自责", "敏感",
    ]

    # Cognitive style markers
    ANALYTICAL_MARKERS: ClassVar[list[str]] = [
        "分析", "逻辑", "数据", "证明", "推理", "证据", "因果", "结论",
        "定量", "统计", "概率", "归纳", "演绎", "假设检验", "论证",
    ]

    INTUITIVE_MARKERS: ClassVar[list[str]] = [
        "感觉", "直觉", "预感", "好像", "似乎", "大概", "整体", "联系",
        "关联", "模式", "类比", "比喻", "灵感", "顿悟",
    ]

    # Risk tolerance markers
    RISK_SEEKING: ClassVar[list[str]] = [
        "冒险", "挑战", "赌博", "高风险", "all in", "拼一把", "博一下",
        "敢", "勇敢", "突破", "试错", "大不了",
    ]

    RISK_AVERSE: ClassVar[list[str]] = [
        "稳妥", "保险", "安全", "稳健", "风险控制", "保守", "谨慎",
        "慢慢来", "观望", "留一手", "底线", "防备", "万一",
    ]

    def __init__(self):
        pass

    def _count_markers(self, text: str, markers: list[str]) -> float:
        """Count marker occurrences in text, normalized by text length."""
        if not text:
            return 0.0
        count = sum(len(re.findall(m, text)) for m in markers)
        # Normalize by hundreds of chars
        return count / max(len(text) / 100, 1)

    def _analyze_big_five(self, combined_text: str) -> BigFiveTraits:
        """Score Big Five traits based on linguistic markers."""
        marker_sets = {
            "openness": (self.OPENNESS_MARKERS, 60),
            "conscientiousness": (self.CONSCIENTIOUSNESS_MARKERS, 55),
            "extraversion": (self.EXTRAVERSION_MARKERS, 50),
            "agreeableness": (self.AGREEABLENESS_MARKERS, 55),
            "neuroticism": (self.NEUROTICISM_MARKERS, 45),
        }

        scores = {}
        for trait, (markers, baseline) in marker_sets.items():
            raw_count = self._count_markers(combined_text, markers)
            # Map 0-1 to 0-100 with baseline adjustment
            score = min(100, max(0, baseline + (raw_count - 0.5) * 30))
            scores[trait] = score

        return BigFiveTraits(**scores)

    def _analyze_cognitive_style(self, combined_text: str) -> str:
        """Determine cognitive style: analytical vs intuitive."""
        analytical_score = self._count_markers(combined_text, self.ANALYTICAL_MARKERS)
        intuitive_score = self._count_markers(combined_text, self.INTUITIVE_MARKERS)

        if analytical_score > intuitive_score * 1.5:
            return "分析型 - 偏好逻辑推理与数据驱动，善于拆解问题"
        elif intuitive_score > analytical_score * 1.5:
            return "直觉型 - 依赖整体感知与直觉判断，善于发现联系"
        else:
            return "平衡型 - 兼顾理性分析与直觉感知"

    def _analyze_social_orientation(self, extraversion: float, agreeableness: float) -> str:
        """Determine social orientation from Big Five scores."""
        if extraversion > 65 and agreeableness > 65:
            return "社交导向 - 外向且善于合作，享受群体互动"
        elif extraversion > 65:
            return "主动社交 - 积极表达但可能有较强主见"
        elif extraversion < 35 and agreeableness > 65:
            return "温和内敛 - 内向但友善，偏好深层关系"
        elif extraversion < 35:
            return "独处倾向 - 偏好独立思考与少数紧密关系"
        else:
            return "平衡社交 - 能适应不同社交场景"

    def _analyze_risk_tolerance(self, combined_text: str) -> str:
        """Assess risk tolerance."""
        seek_score = self._count_markers(combined_text, self.RISK_SEEKING)
        averse_score = self._count_markers(combined_text, self.RISK_AVERSE)

        if seek_score > averse_score * 1.5:
            return "高风险偏好 - 愿意尝试新事物，不畏惧不确定性"
        elif averse_score > seek_score * 1.5:
            return "风险规避 - 偏好稳妥路径，注重安全边际"
        else:
            return "中性 - 能理性评估风险收益"

    def analyze(self, combined_text: str) -> PersonalityProfile:
        """Run full personality analysis."""
        big_five = self._analyze_big_five(combined_text)
        cognitive = self._analyze_cognitive_style(combined_text)
        social = self._analyze_social_orientation(big_five.extraversion, big_five.agreeableness)
        risk = self._analyze_risk_tolerance(combined_text)

        # Generate summary
        o, c, e, a, n = big_five.openness, big_five.conscientiousness, big_five.extraversion, big_five.agreeableness, big_five.neuroticism
        high_traits = []
        if o > 65: high_traits.append("开放创新")
        if c > 65: high_traits.append("严谨自律")
        if e > 65: high_traits.append("外向活跃")
        if a > 65: high_traits.append("温和友善")
        if n > 65: high_traits.append("情绪敏感")

        summary_parts = [f"人格画像：{'、'.join(high_traits) if high_traits else '均衡发展'}", f"认知方式：{cognitive}", f"社交倾向：{social}", f"风险偏好：{risk}"]
        summary = "\n".join(summary_parts)

        return PersonalityProfile(
            big_five=big_five,
            cognitive_style=cognitive,
            social_orientation=social,
            risk_tolerance=risk,
            summary=summary,
        )
