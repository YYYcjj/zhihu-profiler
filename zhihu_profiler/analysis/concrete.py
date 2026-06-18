"""Extract concrete biographical details and representative quotes from answers.

Makes the profile feel like a real person instead of abstract labels.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from ..scraper.models import ZhihuAnswer


@dataclass
class BioDetail:
    label: str = ""
    value: str = ""
    source_answer: str = ""  # question title
    confidence: float = 0.8


@dataclass
class RepresentativeQuote:
    text: str = ""
    answer_title: str = ""
    trait: str = ""  # which personality trait it illustrates
    why: str = ""    # why it's representative


@dataclass
class ConcreteProfile:
    bio_facts: list[BioDetail] = field(default_factory=list)
    quotes: list[RepresentativeQuote] = field(default_factory=list)
    narrative_summary: str = ""


class ConcreteExtractor:
    """Extract concrete details and quotes from answers."""

    # Patterns for biographical details
    BIO_PATTERNS = {
        "职业": [
            r"(我是|我[做在当干搞从事]).{0,30}(工程师|程序员|设计师|产品经理|运营|教师|医生|律师|公务员|学生|自由职业|创业者|老板|总监|经理|分析师|研究员|写手|作者|编辑|摄影师|翻译|\w+师|\w+员)",
            r"(入职|加入|进了|去了).{0,20}(公司|团队|部门|创业)",
            r"(在|于)([\w\u4e00-\u9fff]+(?:公司|科技|集团|网络|软件|银行|医院|学校|大学|媒体|广告|咨询|电商|互联网|\w+厂))",
        ],
        "学历": [
            r"(本科|硕士|博士|研究生|MBA|EMBA|博士后)",
            r"(\d{4})(年|级|届)",
            r"(毕业于|读了|上了|考上了)(.{0,20}(大学|学院|学校))",
        ],
        "城市": [
            r"(住在|在|生活在|漂在)(.{2,8}(?:北京|上海|深圳|广州|杭州|成都|武汉|南京|西安|重庆|苏州|天津|长沙|郑州|东莞|青岛|厦门|合肥|大连|福州|昆明))",
            r"(去了|到了|来到了|搬到了)(.{2,8}(?:北京|上海|深圳|广州|杭州|成都|武汉|南京|西安))",
        ],
        "收入": [
            r"(年收入|月薪|年薪|月入|年入)[^\d]{0,6}(\d+[万多千万]?)",
            r"(工资|薪资|薪酬|收入)[^\d]{0,6}(\d+[千kK万多千万wW]?)",
        ],
        "年龄": [
            r"(我.{0,5}|今年|目前)(\d{2})[岁周岁]",
            r"(\d{2})[岁周岁]的[那这]?时[候年]",
        ],
        "身份": [
            r"(我是一个|我是一个|作为[一].{0,10}|我是个)(.{2,20}(?:人|者|党|粉|迷|控|奴|族|青年|中年|女性|男性|\w{2,}))",
        ],
    }

    # "代表性回答" — 选出最有"人味"的回答
    NARRATIVE_MARKERS = [
        "我记得", "有一次", "当时", "那时候", "小时候",
        "我的经历", "我是怎么", "后来", "从那以后",
        "说一件", "突然想", "决定",
        "不敢", "害怕", "焦虑", "难过", "开心", "感动",
        "感谢", "感恩", "后悔", "遗憾",
    ]

    def extract(self, answers: list[ZhihuAnswer]) -> ConcreteProfile:
        if not answers:
            return ConcreteProfile()

        all_text = "\n".join(a.content for a in answers)
        bio_facts = self._extract_bio_facts(answers, all_text)
        quotes = self._pick_representative_quotes(answers)
        narrative_summary = self._build_narrative_summary(answers, bio_facts, quotes)

        return ConcreteProfile(
            bio_facts=bio_facts,
            quotes=quotes,
            narrative_summary=narrative_summary,
        )

    def _extract_bio_facts(self, answers: list[ZhihuAnswer], all_text: str) -> list[BioDetail]:
        facts = []
        seen = set()

        for category, patterns in self.BIO_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, all_text)
                for m in matches:
                    if isinstance(m, tuple):
                        m = "".join(m)
                    if not isinstance(m, str) or len(m) < 2:
                        continue
                    key = f"{category}:{m}"
                    if key in seen:
                        continue
                    seen.add(key)

                    # Find which answer this came from
                    source = ""
                    for a in answers:
                        if m in a.content:
                            source = a.question_title
                            break

                    # Only include if found in at least 2 answers (consistency) OR highly specific
                    count = all_text.count(m)
                    if count >= 2 or len(m) > 4:
                        facts.append(BioDetail(
                            label=category,
                            value=m.strip(),
                            source_answer=source,
                            confidence=min(count / 5 + 0.3, 1.0),
                        ))

        return facts[:12]

    def _pick_representative_quotes(self, answers: list[ZhihuAnswer]) -> list[RepresentativeQuote]:
        """Pick the most 'personal' quotes from answers."""
        candidates = []

        for a in answers:
            text = a.content
            # Score: narrative + length + emotional content
            score = 0
            for marker in self.NARRATIVE_MARKERS:
                if marker in text:
                    score += 1

            if score >= 2:  # Answer with personal story markers
                # Pick the most narrative-rich paragraph
                paras = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.strip()) > 30]
                best_para = ""
                best_para_score = 0
                for p in paras:
                    para_score = sum(1 for m in self.NARRATIVE_MARKERS if m in p)
                    if para_score > best_para_score and len(p) < 500:
                        best_para_score = para_score
                        best_para = p

                if best_para:
                    candidates.append((score, best_para[:250], a.question_title))

        # Sort by narrative score, pick top 4
        candidates.sort(key=lambda x: x[0], reverse=True)
        quotes = []
        for score, text, title in candidates[:4]:
            quotes.append(RepresentativeQuote(
                text=text,
                answer_title=title,
                trait=self._guess_trait(text),
                why=f"个人叙事丰富度: {score}",
            ))

        return quotes

    def _guess_trait(self, text: str) -> str:
        """Guess which trait this quote illustrates."""
        traits = {
            "开放": ["尝试", "学习", "新", "探索", "好奇", "旅行", "读书", "艺术"],
            "尽责": ["坚持", "每天", "计划", "完成", "目标", "自律", "习惯"],
            "外向": ["朋友", "聚会", "社交", "热闹", "团队", "一起", "分享"],
            "宜人": ["帮助", "理解", "倾听", "包容", "善良", "支持", "关心"],
            "神经质": ["焦虑", "担心", "害怕", "压力", "失眠", "崩溃", "难过"],
        }
        scores = Counter()
        for trait, markers in traits.items():
            for m in markers:
                if m in text:
                    scores[trait] += 1
        return scores.most_common(1)[0][0] if scores else "个人经历"

    def _build_narrative_summary(
        self,
        answers: list[ZhihuAnswer],
        bio_facts: list[BioDetail],
        quotes: list[RepresentativeQuote],
    ) -> str:
        """Build a human-readable narrative summary."""
        parts = []

        # Bio facts
        if bio_facts:
            grouped = {}
            for f in bio_facts:
                grouped.setdefault(f.label, []).append(f.value)
            for label, values in grouped.items():
                uniq = list(set(values))[:3]
                parts.append(f"- {label}：{'/'.join(uniq)}")

        # Quotes
        if quotes:
            parts.append("")
            parts.append("**代表性回答节选**：")
            for q in quotes:
                parts.append(f"")
                parts.append(f"> \"{q.text[:120]}...\"")
                parts.append(f"> — 来自《{q.answer_title}》· 展现{q.trait}特质")

        return "\n".join(parts)
