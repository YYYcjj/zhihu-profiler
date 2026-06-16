"""Writing style analysis for Zhihu answer texts."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import numpy as np


@dataclass
class StyleProfile:
    """Writing style analysis result."""

    avg_sentence_length: float = 0.0
    avg_paragraph_length: float = 0.0
    avg_answer_length: float = 0.0
    punctuation_style: str = ""
    structural_style: str = ""
    tone_style: str = ""
    rhetorical_devices: dict[str, int] = field(default_factory=dict)
    vocabulary_richness: float = 0.0
    first_person_ratio: float = 0.0
    summary: str = ""


class StyleAnalyzer:
    """Analyze writing style characteristics."""

    # Rhetorical devices markers
    RHETORICAL_DEVICES = {
        "反问": [r"[^。！？\n]+\？(?!\n)"],
        "排比": [r"(?:([^，。！？\n]{2,10})[，。]?\1[，。]?\1)"],
        "引用": [r"「[^」]+」", r"『[^』]+』", r""[^"]+"", r"'[^']+'"],
        "设问": [r"[^。！？\n]+\？\s*(?:首先|第一|那么|[我我]认为|[我我]觉得|答案|因为|其实|实际上)[^。！？]+"],
        "感叹": [r"！(?:\s*！)+", r"(?:多么|真是|简直)[^！。]+！"],
        "对比": [r"(?:不是|并非)[^，。]+[，。]*(?:而是|应该是)[^。]+"],
        "类比": [r"(?:就像|好比|如同|仿佛|犹如|像)[^，。]+[，。]*[^。]+"],
        "数据论证": [r"\d+%", r"\d+亿", r"\d+万", r"\d+倍", r"\d+人"],
    }

    def __init__(self):
        pass

    def analyze(self, answers_texts: list[str]) -> StyleProfile:
        """Analyze writing style from a list of answer texts."""
        if not answers_texts:
            return StyleProfile()

        # Combine all texts
        combined = "\n\n".join(answers_texts)

        # Sentence-level analysis
        sentences = self._split_sentences(combined)
        sentence_lengths = [len(s) for s in sentences if s.strip()]
        avg_sent_len = np.mean(sentence_lengths) if sentence_lengths else 0

        # Paragraph-level analysis
        paragraphs = [p for p in combined.split("\n") if p.strip()]
        para_lengths = [len(p) for p in paragraphs]
        avg_para_len = np.mean(para_lengths) if para_lengths else 0

        # Answer-level analysis
        answer_lengths = [len(a) for a in answers_texts if a]
        avg_answer_len = np.mean(answer_lengths) if answer_lengths else 0

        # Punctuation style
        punct_style = self._analyze_punctuation(combined)

        # Structural style
        structural = self._analyze_structure(answers_texts)

        # Tone style
        tone = self._analyze_tone(combined)

        # Rhetorical devices
        devices = self._count_rhetorical_devices(combined)

        # Vocabulary richness (type-token ratio)
        richness = self._calculate_richness(combined)

        # First-person pronoun ratio
        first_person = self._calculate_first_person(combined)

        # Generate summary
        summary = self._generate_summary(
            avg_answer_len, avg_sent_len, richness, tone, devices
        )

        return StyleProfile(
            avg_sentence_length=round(avg_sent_len, 1),
            avg_paragraph_length=round(avg_para_len, 1),
            avg_answer_length=round(avg_answer_len, 1),
            punctuation_style=punct_style,
            structural_style=structural,
            tone_style=tone,
            rhetorical_devices=devices,
            vocabulary_richness=round(richness, 4),
            first_person_ratio=round(first_person, 4),
            summary=summary,
        )

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Chinese sentence delimiters
        return re.split(r"[。！？；\n]+", text)

    def _analyze_punctuation(self, text: str) -> str:
        """Analyze punctuation usage patterns."""
        total = len(text)
        if total == 0:
            return "无数据"

        excl = text.count("！")
        question = text.count("？")
        ellipsis = text.count("……") + text.count("...")
        comma = text.count("，")

        excl_ratio = excl / total * 1000
        question_ratio = question / total * 1000

        if excl_ratio > 3:
            return "感叹号使用频繁 — 表达强烈，情绪充沛"
        elif question_ratio > 3:
            return "问号使用频繁 — 思辨性强，善于引导思考"
        else:
            return "标点使用均衡 — 表达平稳，注重逻辑"

    def _analyze_structure(self, answers: list[str]) -> str:
        """Analyze answer structural patterns."""
        if not answers:
            return "无数据"

        # Check for structured patterns
        numbered = sum(1 for a in answers if re.search(r"^\d+[\.\、)]", a, re.MULTILINE))
        listed = sum(1 for a in answers if re.search(r"^[一二三四五六七八九十][\.\、)]", a, re.MULTILINE))
        has_intro_conclusion = sum(1 for a in answers if len(a.split("\n")) >= 4)
        bold_headers = sum(1 for a in answers if "**" in a or "__" in a)

        ratio_numbered = numbered / len(answers)
        ratio_structured = (numbered + listed + bold_headers) / len(answers)

        if ratio_structured > 0.3:
            return "结构化表达 — 善于使用编号、分段、标题组织内容"
        elif ratio_numbered > 0.15:
            return "偏好列举 — 常用数字编号展开论述"
        elif has_intro_conclusion / len(answers) > 0.5:
            return "叙事型结构 — 有起承转合，注重可读性"
        else:
            return "自由流式 — 随性表达，不拘泥于固定格式"

    def _analyze_tone(self, text: str) -> str:
        """Analyze the overall tone of writing."""
        if not text:
            return "无数据"

        # Count tone indicators
        humor_markers = len(re.findall(r"(?:哈哈|笑|搞笑|幽默|调侃|吐槽|玩|乐)", text))
        serious_markers = len(re.findall(r"(?:严肃|严谨|重要|关键|核心|本质|深度|思考)", text))
        casual_markers = len(re.findall(r"(?:吧|嘛|呗|呢|啊|呀|哦|啦|随便|无所谓)", text))
        authoritative_markers = len(re.findall(r"(?:我认为|我的观点|事实证明|毫无疑问|显然|必然)", text))

        total = text.count("。") + text.count("！") + text.count("？") + 1

        humor_rate = humor_markers / total
        serious_rate = serious_markers / total
        casual_rate = casual_markers / total
        authoritative_rate = authoritative_markers / total

        rates = {
            "轻松幽默": humor_rate,
            "严谨专业": serious_rate,
            "随性口语": casual_rate,
            "权威论述": authoritative_rate,
        }

        primary = max(rates, key=rates.get)
        descriptions = {
            "轻松幽默": "轻松幽默 — 善于用生动语言调节氛围",
            "严谨专业": "严谨专业 — 表达注重逻辑与准确性",
            "随性口语": "随性口语 — 像朋友聊天般自然亲切",
            "权威论述": "权威论述 — 语气笃定，有较强的表达自信",
        }

        return descriptions.get(primary, "风格均衡")

    def _count_rhetorical_devices(self, text: str) -> dict[str, int]:
        """Count rhetorical devices used."""
        counts = {}
        for device, patterns in self.RHETORICAL_DEVICES.items():
            count = 0
            for pattern in patterns:
                count += len(re.findall(pattern, text))
            if count > 0:
                counts[device] = count
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def _calculate_richness(self, text: str) -> float:
        """Calculate vocabulary richness (unique chars / total meaningful chars)."""
        chars = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        if not chars:
            return 0.0
        unique = set(chars)
        return len(unique) / len(chars)

    def _calculate_first_person(self, text: str) -> float:
        """Calculate first-person pronoun usage ratio."""
        total_chars = len(text)
        if total_chars == 0:
            return 0.0
        first_person_count = len(re.findall(r"[我我]", text))
        return first_person_count / total_chars

    def _generate_summary(
        self,
        avg_answer_len: float,
        avg_sent_len: float,
        richness: float,
        tone: str,
        devices: dict,
    ) -> str:
        """Generate a human-readable style summary."""
        parts = []

        if avg_answer_len > 500:
            parts.append("长篇深度回答")
        elif avg_answer_len > 200:
            parts.append("中等篇幅")
        else:
            parts.append("短小精悍")

        if avg_sent_len > 40:
            parts.append("长句为主")
        elif avg_sent_len > 20:
            parts.append("长短句结合")
        else:
            parts.append("短句为主")

        if richness > 0.5:
            parts.append("词汇丰富")
        elif richness > 0.3:
            parts.append("词汇量适中")
        else:
            parts.append("用词简洁")

        if devices:
            top_device = list(devices.keys())[0]
            parts.append(f"善用{top_device}")

        return " · ".join(parts)
