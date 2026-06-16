"""Interest domain classification and analysis for Zhihu users."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import ClassVar

logger = logging.getLogger(__name__)


# Topic keyword mappings for interest domain classification
TOPIC_DOMAINS: dict[str, list[str]] = {
    "科技与互联网": [
        "AI", "人工智能", "机器学习", "深度学习", "算法", "编程", "代码",
        "Python", "Java", "Go", "Rust", "前端", "后端", "架构", "系统设计",
        "开源", "GitHub", "云计算", "服务器", "数据库", "API", "SDK",
        "科技", "技术", "软件", "硬件", "芯片", "接口", "框架",
        "大模型", "LLM", "ChatGPT", "GPT", "Transformer",
        "自动驾驶", "机器人", "物联网", "5G", "6G",
    ],
    "产品与商业": [
        "产品", "产品经理", "PM", "需求", "用户", "体验", "UX", "UI",
        "商业模式", "商业化", "盈利", "收入", "增长", "转化", "留存",
        "创业", "融资", "VC", "天使轮", "Startup", "孵化",
        "市场", "竞品", "差异", "壁垒", "护城河", "蓝海",
        "运营", "获客", "裂变", "私域", "品牌", "营销",
    ],
    "投资与金融": [
        "股票", "基金", "A股", "港股", "美股", "比特币", "加密货币", "BTC",
        "投资", "理财", "资产", "配置", "定投", "ETF", "期权", "期货",
        "房价", "楼市", "买房", "贷款", "利率", "加息", "降息",
        "财务自由", "FIRE", "被动收入", "股息", "分红",
        "经济", "通胀", "GDP", "宏观", "周期", "估值",
    ],
    "职场与成长": [
        "职场", "工作", "跳槽", "面试", "简历", "薪资", "升职", "管理",
        "领导力", "沟通", "汇报", "绩效", "OKR", "KPI", "996",
        "35岁", "中年危机", "转行", "副业", "自由职业",
        "学习", "成长", "进步", "能力", "技能", "读书", "课程",
        "时间管理", "效率", "自律", "习惯", "复盘", "反思",
    ],
    "人文与社科": [
        "哲学", "历史", "政治", "经济", "社会", "文化", "心理", "教育",
        "文学", "艺术", "音乐", "电影", "书籍", "诗歌", "戏剧",
        "人性", "道德", "伦理", "价值观", "信仰", "自由", "平等",
        "历史人物", "文明", "传统", "现代", "批判", "反思",
    ],
    "生活与情感": [
        "生活", "美食", "旅行", "健身", "运动", "健康", "睡眠", "饮食",
        "恋爱", "婚姻", "家庭", "孩子", "父母", "朋友", "孤独",
        "情绪", "焦虑", "抑郁", "幸福", "快乐", "满足", "意义",
        "日常", "周末", "爱好", "兴趣", "记录", "分享",
    ],
    "科学知识": [
        "物理", "化学", "生物", "数学", "天文", "宇宙", "量子",
        "进化", "基因", "遗传", "认知科学", "神经科学",
        "环境", "气候", "能源", "碳中和", "可持续",
        "医学", "健康", "疫苗", "药物", "疾病",
    ],
    "社会热点": [
        "热点", "新闻", "事件", "争议", "舆论", "热搜", "曝光",
        "政策", "法规", "改革", "监管", "整治", "新规",
        "社会现象", "躺平", "内卷", "摆烂", "凡尔赛",
        "教育公平", "医疗", "养老", "生育", "人口",
    ],
    "创作与表达": [
        "写作", "创作", "表达", "故事", "小说", "文章", "内容",
        "自媒体", "公众号", "短视频", "UP主", "创作者",
        "设计", "审美", "视觉", "创意", "灵感", "作品",
    ],
}

# Topic hierarchy
DOMAIN_HIERARCHY = {
    "硬核理性": ["科技与互联网", "科学知识", "投资与金融"],
    "实践应用": ["产品与商业", "职场与成长"],
    "人文思考": ["人文与社科", "社会热点"],
    "生活情感": ["生活与情感", "创作与表达"],
}


@dataclass
class InterestProfile:
    """Interest analysis result."""

    top_domains: list[tuple[str, float]] = field(default_factory=list)
    topic_distribution: dict[str, float] = field(default_factory=dict)
    category_balance: dict[str, float] = field(default_factory=dict)
    total_topics: int = 0
    primary_domain: str = ""
    summary: str = ""


class InterestAnalyzer:
    """Analyze a user's interest domains based on Zhihu answers and topics."""

    def __init__(self):
        self.domains = TOPIC_DOMAINS
        self.hierarchy = DOMAIN_HIERARCHY

    def analyze_from_topics(
        self, all_question_topics: list[list[str]]
    ) -> InterestProfile:
        """Analyze interests from question topic tags."""
        flat_topics = []
        for topics in all_question_topics:
            flat_topics.extend(topics)

        topic_counts = Counter(flat_topics)
        total = sum(topic_counts.values()) or 1

        return InterestProfile(
            top_domains=[(t, c / total) for t, c in topic_counts.most_common(10)],
            topic_distribution=dict(topic_counts.most_common(20)),
            total_topics=len(topic_counts),
            primary_domain=topic_counts.most_common(1)[0][0] if topic_counts else "",
            summary=f"关注{len(topic_counts)}个话题领域",
        )

    def analyze_from_text(
        self, combined_text: str, top_k: int = 5
    ) -> InterestProfile:
        """Analyze interests from answer content using keyword matching."""
        domain_scores: dict[str, float] = {}
        text_lower = combined_text.lower()

        for domain, keywords in self.domains.items():
            score = 0
            for kw in keywords:
                # Count occurrences of each keyword
                count = text_lower.count(kw.lower())
                if count > 0:
                    # Weight: first occurrence is most significant
                    score += 1 + min(count, 10) * 0.5
            domain_scores[domain] = score

        # Normalize scores
        total_score = sum(domain_scores.values()) or 1
        normalized = {
            d: round(s / total_score * 100, 1)
            for d, s in domain_scores.items()
        }

        # Rank domains
        ranked = sorted(normalized.items(), key=lambda x: x[1], reverse=True)

        # Calculate category balance
        cat_scores = {}
        for cat, domains in self.hierarchy.items():
            cat_scores[cat] = sum(domain_scores.get(d, 0) for d in domains)
        cat_total = sum(cat_scores.values()) or 1
        cat_normalized = {
            c: round(s / cat_total * 100, 1) for c, s in cat_scores.items()
        }

        # Generate summary
        top = ranked[:3]
        top_names = [d[0] for d in top]
        primary = top[0][0] if top else "综合"

        if len(top) >= 2 and top[0][1] > top[1][1] * 1.5:
            focus = f"高度聚焦于「{primary}」领域"
        elif len(top) >= 3:
            focus = f"主要关注「{'」「'.join(top_names)}」"
        else:
            focus = "兴趣较为分散"

        return InterestProfile(
            top_domains=ranked[:top_k],
            topic_distribution=dict(ranked),
            category_balance=cat_normalized,
            total_topics=len([d for d, s in domain_scores.items() if s > 0]),
            primary_domain=primary,
            summary=focus,
        )

    def analyze_combined(
        self,
        combined_text: str,
        all_question_topics: list[list[str]],
    ) -> InterestProfile:
        """Combine topic-based and text-based analysis."""
        text_profile = self.analyze_from_text(combined_text)
        topic_profile = self.analyze_from_topics(all_question_topics)

        # Merge: prioritize topic tags but supplement with text analysis
        merged = dict(text_profile.topic_distribution)

        # Boost domains that appear in topic tags
        for topic, _ in topic_profile.top_domains:
            if topic in merged:
                merged[topic] *= 1.5

        ranked = sorted(merged.items(), key=lambda x: x[1], reverse=True)

        return InterestProfile(
            top_domains=ranked[:10],
            topic_distribution=dict(ranked),
            category_balance=text_profile.category_balance,
            total_topics=text_profile.total_topics + topic_profile.total_topics,
            primary_domain=ranked[0][0] if ranked else "",
            summary=text_profile.summary,
        )
