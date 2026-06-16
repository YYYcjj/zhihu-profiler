"""Value system analysis from Zhihu answer texts.

Identifies value orientations based on Schwartz's theory of basic human values,
adapted for Chinese internet discourse.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

import numpy as np

# Value dimension definitions with Chinese linguistic markers
VALUE_DIMENSIONS: dict[str, dict] = {
    "成就导向": {
        "markers": [
            "成就", "成功", "目标", "第一", "最好", "优秀", "卓越",
            "突破", "超越", "赢", "竞争", "领先", "冠军", "巅峰",
            "证明", "认可", "荣誉", "奖励", "晋升", "上升",
        ],
        "description": "看重个人成就与社会认可，具有强烈的目标驱动力",
    },
    "自我超越": {
        "markers": [
            "成长", "进步", "学习", "提升", "进化", "迭代", "修炼",
            "突破自我", "走出舒适区", "终身学习", "自我实现",
            "潜力", "格局", "眼界", "认知升级", "思维模型",
        ],
        "description": "追求个人成长与心智提升，关注长期发展",
    },
    "社会关怀": {
        "markers": [
            "帮助", "公益", "慈善", "贡献", "价值", "意义", "改变",
            "社会", "大众", "弱势", "公平", "正义", "责任",
            "环保", "可持续", "未来", "下一代", "共同体",
        ],
        "description": "关注社会议题，有较强的利他倾向与社会责任感",
    },
    "务实主义": {
        "markers": [
            "现实", "实际", "务实", "落地", "执行", "可行", "条件",
            "资源", "成本", "收益", "ROI", "性价比", "划算",
            "时间成本", "机会成本", "权衡", "妥协", "可行性",
        ],
        "description": "注重现实条件与可行性，强调投入产出比",
    },
    "理想主义": {
        "markers": [
            "理想", "梦想", "初心", "使命", "愿景", "信仰", "信念",
            "热爱", "激情", "追随内心", "不妥协", "坚持做自己",
            "诗和远方", "星辰大海", "浪漫", "完美", "应然",
        ],
        "description": "持有强烈的理想与信念，追求精神层面的满足",
    },
    "自由主义": {
        "markers": [
            "自由", "独立", "自主", "选择", "个体", "多元", "包容",
            "尊重", "边界", "空间", "隐私", "不干涉", "开放",
            "多元化", "不一样", "个人选择", "生活方式",
        ],
        "description": "重视个人自由与选择权，尊重个体差异",
    },
    "传统价值": {
        "markers": [
            "传统", "家庭", "责任", "孝顺", "传承", "规矩", "道德",
            "本分", "忠诚", "稳定", "安居", "婚姻", "子女教育",
            "尊老", "爱幼", "家庭和睦", "亲情", "感恩",
        ],
        "description": "认同传统价值观，重视家庭与道德规范",
    },
    "体验主义": {
        "markers": [
            "体验", "经历", "过程", "享受", "当下", "快乐", "开心",
            "旅行", "美食", "探索", "冒险", "新鲜", "刺激",
            "人生苦短", "及时行乐", "活在当下", "YOLO",
        ],
        "description": "追求丰富的人生体验，注重过程与感受",
    },
}


@dataclass
class ValueProfile:
    """Value system analysis result."""

    value_scores: dict[str, float] = field(default_factory=dict)
    core_values: list[str] = field(default_factory=list)
    value_tensions: list[tuple[str, str]] = field(default_factory=list)
    summary: str = ""


class ValueAnalyzer:
    """Analyze value system from text."""

    # Value tensions / polarities
    TENSIONS: ClassVar[list[tuple[str, str, str]]] = [
        ("成就导向", "体验主义", "奋斗 vs 享受"),
        ("理想主义", "务实主义", "理想 vs 现实"),
        ("自由主义", "传统价值", "自由 vs 传统"),
        ("自我超越", "社会关怀", "个人成长 vs 社会责任"),
    ]

    def __init__(self):
        pass

    def _count_value_markers(self, text: str) -> dict[str, float]:
        """Count markers for each value dimension."""
        scores = {}
        text_len = max(len(text), 100)

        for dim_name, dim_data in VALUE_DIMENSIONS.items():
            total_count = 0
            for marker in dim_data["markers"]:
                count = len(re.findall(marker, text))
                total_count += count

            # Normalize: score per 1000 chars
            scores[dim_name] = total_count / (text_len / 1000)

        return scores

    def analyze(self, combined_text: str) -> ValueProfile:
        """Analyze value system from combined answer texts."""
        raw_scores = self._count_value_markers(combined_text)

        # Normalize to 0-100 scale
        max_score = max(raw_scores.values()) if raw_scores else 1
        normalized = {
            dim: round(min(100, score / max(1, max_score) * 60), 1)
            for dim, score in raw_scores.items()
        }

        # Sort and find core values (top 3)
        ranked = sorted(normalized.items(), key=lambda x: x[1], reverse=True)
        core_values = [name for name, score in ranked[:3] if score > 20]

        # Find value tensions
        tensions = []
        for dim1, dim2, label in self.TENSIONS:
            s1 = normalized.get(dim1, 0)
            s2 = normalized.get(dim2, 0)
            if abs(s1 - s2) > 20:
                stronger = dim1 if s1 > s2 else dim2
                weaker = dim2 if s1 > s2 else dim1
                tensions.append((stronger, weaker))

        # Generate summary
        core_desc = "、".join(core_values) if core_values else "无明显价值倾向"
        tension_desc = ""
        if tensions:
            tension_desc = f"；内在张力：{' vs '.join(tensions[0])}"

        summary = f"核心价值观：{core_desc}{tension_desc}"

        return ValueProfile(
            value_scores=normalized,
            core_values=core_values,
            value_tensions=tensions,
            summary=summary,
        )

    def get_dimension_description(self, dimension: str) -> str:
        """Get the description for a value dimension."""
        return VALUE_DIMENSIONS.get(dimension, {}).get("description", "")
