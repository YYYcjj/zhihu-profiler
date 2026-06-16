"""Text preprocessing utilities for Chinese text from Zhihu answers."""

from __future__ import annotations

import re
from collections import Counter
from typing import Optional

import jieba
import jieba.analyse
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# Load jieba custom dictionary with common internet terms
INTERNET_TERMS = [
    "内卷", "躺平", "凡尔赛", "破防", "社恐", "社牛", "绝绝子",
    "摆烂", "摸鱼", "打工人", "工具人", "干饭人", "氛围感",
    "拿捏", "栓Q", "芭比Q", "CPU", "PUA", "EMO", "yyds",
    "元宇宙", "AI", "ChatGPT", "大模型", "LLM", "AGI",
    "OKR", "KPI", "996", "007", "35岁", "优化", "上岸",
]
for term in INTERNET_TERMS:
    jieba.add_word(term)

# Common stopwords for Chinese text
STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "他", "她", "它", "们", "那", "些",
    "这个", "那个", "可以", "觉得", "因为", "但是", "所以", "如果", "虽然",
    "而且", "还是", "只是", "什么", "怎么", "为什么", "哪", "吗", "呢",
    "啊", "吧", "哦", "嗯", "哈", "呀", "嘛", "呗", "啦",
    "之", "其", "以", "及", "或", "与", "且", "而", "于", "则",
    "从", "对", "被", "把", "向", "让", "给", "比", "较", "更",
    "等", "该", "所", "已", "能", "将", "为", "可", "应",
    "没", "吧", "么", "嘛", "呢",
}


class TextPreprocessor:
    """Chinese text preprocessing pipeline."""

    def __init__(
        self,
        custom_stopwords: Optional[set[str]] = None,
        remove_urls: bool = True,
        remove_mentions: bool = True,
        min_word_length: int = 1,
    ):
        self.stopwords = STOPWORDS | (custom_stopwords or set())
        self.remove_urls = remove_urls
        self.remove_mentions = remove_mentions
        self.min_word_length = min_word_length
        self._tfidf_vectorizer: Optional[TfidfVectorizer] = None

    def clean_text(self, text: str) -> str:
        """Clean raw text: remove URLs, mentions, special chars, normalize whitespace."""
        if not text:
            return ""

        if self.remove_urls:
            text = re.sub(r"https?://\S+", "", text)

        if self.remove_mentions:
            text = re.sub(r"@\S+", "", text)

        # Remove HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'")

        # Remove special unicode chars but keep Chinese, English, numbers, common punctuation
        text = re.sub(r"[^\u4e00-\u9fff\u3400-\u4dbfa-zA-Z0-9\s，。！？；：""''、（）《》【】\.\,\!\?\;\:\"\'\(\)\[\]]+", " ", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def segment(self, text: str) -> list[str]:
        """Segment Chinese text into words."""
        cleaned = self.clean_text(text)
        words = jieba.cut(cleaned)
        return [w.strip() for w in words if w.strip()]

    def filter_words(self, words: list[str]) -> list[str]:
        """Filter out stopwords and short words."""
        return [
            w for w in words
            if w not in self.stopwords
            and len(w) >= self.min_word_length
            and not w.isspace()
        ]

    def process(self, text: str) -> list[str]:
        """Full pipeline: clean → segment → filter."""
        words = self.segment(text)
        return self.filter_words(words)

    def extract_keywords_tfidf(
        self,
        texts: list[str],
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Extract important keywords using TF-IDF across all texts."""
        cleaned = [self.clean_text(t) for t in texts if t]
        if not cleaned:
            return []

        self._tfidf_vectorizer = TfidfVectorizer(
            tokenizer=self.process,
            max_features=200,
            token_pattern=None,  # Use our custom tokenizer
        )
        tfidf_matrix = self._tfidf_vectorizer.fit_transform(cleaned)

        # Sum TF-IDF scores across all documents
        scores = np.array(tfidf_matrix.sum(axis=0)).flatten()
        feature_names = self._tfidf_vectorizer.get_feature_names_out()

        ranked = sorted(
            zip(feature_names, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def extract_keywords_textrank(
        self,
        text: str,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Extract keywords using TextRank algorithm (via jieba)."""
        return jieba.analyse.textrank(
            text,
            topK=top_k,
            withWeight=True,
            allowPOS=("n", "nr", "ns", "nt", "nz", "v", "vn", "a", "an"),
        )

    def extract_keywords_tfidf_single(
        self,
        text: str,
        top_k: int = 20,
    ) -> list[tuple[str, float]]:
        """Extract keywords using TF-IDF (via jieba)."""
        return jieba.analyse.extract_tags(
            text,
            topK=top_k,
            withWeight=True,
            allowPOS=("n", "nr", "ns", "nt", "nz", "v", "vn", "a", "an"),
        )

    def get_word_frequency(
        self,
        texts: list[str],
        top_k: int = 50,
    ) -> list[tuple[str, int]]:
        """Get word frequency distribution."""
        counter: Counter[str] = Counter()
        for text in texts:
            words = self.process(text)
            counter.update(words)
        return counter.most_common(top_k)

    def get_combined_text(self, texts: list[str]) -> str:
        """Combine multiple texts into one clean string."""
        cleaned = [self.clean_text(t) for t in texts if t]
        return "\n\n".join(cleaned)
