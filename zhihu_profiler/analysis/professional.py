"""Professional image analysis — career stage, skills, work values, industry insight."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from ..scraper.models import ZhihuAnswer


@dataclass
class CareerStage:
    """Inferred career stage."""

    level: str = ""       # 初级/中级/高级/管理/创业/自由职业/转行期
    years_exp: str = ""   # "3-5年" / "10年+" / ""
    summary: str = ""


@dataclass
class SkillProfile:
    """Professional skills assessment."""

    hard_skills: list[str] = field(default_factory=list)     # 硬技能
    soft_skills: list[str] = field(default_factory=list)     # 软技能
    expertise_domains: list[str] = field(default_factory=list)  # 擅长领域
    summary: str = ""


@dataclass
class WorkValues:
    """Work-related values."""

    motivations: list[str] = field(default_factory=list)     # 工作动力来源
    preferences: list[str] = field(default_factory=list)     # 偏好（大厂/创业/WLB等）
    attitudes: list[str] = field(default_factory=list)       # 态度（躺平/奋斗/务实等）
    summary: str = ""


@dataclass
class IndustryInsight:
    """Industry understanding."""

    industries: list[str] = field(default_factory=list)     # 涉及行业
    hot_topics: list[str] = field(default_factory=list)     # 关注热点
    depth_score: float = 0.0
    summary: str = ""


@dataclass
class ProfessionalImage:
    """Complete professional image."""

    career_stage: CareerStage = field(default_factory=CareerStage)
    skills: SkillProfile = field(default_factory=SkillProfile)
    work_values: WorkValues = field(default_factory=WorkValues)
    industry_insight: IndustryInsight = field(default_factory=IndustryInsight)
    professional_quotes: list[dict] = field(default_factory=list)
    summary: str = ""


# ── 技能词库 ──
HARD_SKILLS = {
    "编程开发": ["编程", "代码", "开发", "Python", "Java", "Go", "Rust", "C++", "JavaScript",
               "前端", "后端", "全栈", "算法", "数据结构", "系统设计", "CI/CD", "DevOps",
               "测试", "Debug", "重构", "架构", "微服务", "API", "数据库", "SQL", "Redis",
               "K8s", "Docker", "Linux", "Git", "云计算", "Serverless"],
    "数据分析": ["数据", "分析", "统计", "SQL", "Excel", "Tableau", "Power BI",
               "机器学习", "深度学习", "NLP", "CV", "数据挖掘", "A/B测试",
               "数据仓库", "ETL", "数据可视化", "指标", "DAU", "留存"],
    "产品设计": ["产品", "需求", "PRD", "原型", "用户体验", "UX", "UI", "交互",
               "竞品分析", "用户研究", "用户访谈", "A/B测试", "增长", "留存",
               "商业化", "变现", "PMF", "MVP"],
    "运营市场": ["运营", "营销", "推广", "用户增长", "内容", "社区", "活动",
               "SEO", "SEM", "投放", "私域", "社群", "转化", "获客", "裂变",
               "品牌", "公关", "新媒体", "短视频", "直播"],
    "管理领导": ["管理", "团队", "OKR", "KPI", "绩效", "招聘", "面试",
               "领导", "带人", "培养", "授权", "复盘", "战略", "规划",
               "跨部门", "协作", "向上管理", "项目", "敏捷", "Scrum"],
    "金融投资": ["投资", "股票", "基金", "理财", "风控", "量化", "金融",
               "保险", "信贷", "估值", "财务", "会计", "审计", "税务"],
    "设计创作": ["设计", "视觉", "插画", "动效", "摄影", "剪辑", "3D",
               "Blender", "Figma", "Sketch", "Adobe", "手绘",
               "写作", "文案", "编辑", "翻译"],
    "教育学术": ["研究", "论文", "实验", "教学", "课程", "教材",
               "发表", "学术", "科研", "导师", "学生"],
}

SOFT_SKILLS = {
    "沟通表达": ["沟通", "表达", "演讲", "汇报", "说服", "谈判", "倾听", "反馈"],
    "学习能力": ["学习", "自学", "快速上手", "钻研", "好奇", "成长"],
    "问题解决": ["解决问题", "分析", "定位", "排查", "优化", "改进", "创新"],
    "抗压韧性": ["抗压", "坚持", "加班", "deadline", "熬夜", "压力", "韧性", "心态"],
    "团队协作": ["合作", "协作", "配合", "协调", "共赢", "帮助", "支持"],
    "独立思考": ["思考", "深度", "批判", "反思", "复盘", "独立", "主见"],
}

WORK_VALUE_MARKERS = {
    "追求影响力": ["影响力", "改变世界", "价值", "意义", "使命", "愿景", "贡献"],
    "追求技术深度": ["技术", "深入", "底层", "原理", "极致", "工匠", "精通"],
    "追求成长速度": ["成长", "提升", "进步", "学习", "发展", "晋升", "挑战"],
    "追求工作生活平衡": ["WLB", "工作生活平衡", "加班少", "双休", "不卷", "生活", "家庭"],
    "追求财富自由": ["财务自由", "赚钱", "收入", "薪资", "offer", "股票", "期权", "套现"],
    "追求稳定": ["稳定", "国企", "公务员", "事业编", "体制内", "养老", "不裁员"],
    "追求自由独立": ["自由", "独立", "副业", "远程", "数字游民", "自由职业", "创业", "不想上班"],
    "务实理性": ["现实", "理性", "取舍", "权衡", "性价比", "投入产出", "just a job"],
}

CAREER_PHASES = [
    (["刚毕业", "应届", "新人", "实习", "第一份", "校招", "初入职场", "小白", "入门", "从零", "零基础"], "初级阶段：职场新人/应届"),
    (["三五年", "两三年", "跳槽", "换了几份", "开始独立", "承担更多", "成长最快", "技术提升"], "成长阶段：独立贡献者"),
    (["带团队", "管理", "负责人", "leader", "经理", "总监", "主管", "架构师", "专家"], "高级阶段：技术专家/管理者"),
    (["创业", "合伙人", "创始人", "联合创始", "自己做", "辞职创业", "副业", "全职创业"], "创业阶段"),
    (["转行", "换方向", "换个赛道", "从零开始", "重新学", "跨界", "转型"], "转型阶段"),
    (["躺平", "不想努力", "佛系", "看淡", "随缘", "无所谓", "凑合"], "倦怠/反思阶段"),
]


class ProfessionalAnalyzer:
    """Analyze professional image from answers."""

    def analyze(self, answers: list[ZhihuAnswer]) -> ProfessionalImage:
        if not answers:
            return ProfessionalImage()

        all_text = "\n".join(a.content + a.question_title for a in answers)

        career_stage = self._analyze_career_stage(answers, all_text)
        skills = self._analyze_skills(answers, all_text)
        work_values = self._analyze_work_values(all_text)
        industry_insight = self._analyze_industry(all_text)
        quotes = self._extract_professional_quotes(answers)

        return ProfessionalImage(
            career_stage=career_stage,
            skills=skills,
            work_values=work_values,
            industry_insight=industry_insight,
            professional_quotes=quotes,
            summary=self._build_summary(career_stage, skills, work_values, industry_insight, quotes),
        )

    def _analyze_career_stage(self, answers: list[ZhihuAnswer], text: str) -> CareerStage:
        scores = Counter()
        evidence = defaultdict(list)

        for markers, stage in CAREER_PHASES:
            for m in markers:
                count = len(re.findall(re.escape(m), text))
                if count > 0:
                    scores[stage] += count

        best = scores.most_common(1)
        level = best[0][0] if best else "无法判断"

        # Estimate years of experience
        years = ""
        year_matches = re.findall(r"(\d{1,2})\s*年[的之]?([工作经历]|经验|经验|职场)", text)
        if year_matches:
            nums = [int(m[0]) for m in year_matches if is_number(m[0])]
            if nums:
                years = f"{min(nums)}-{max(nums)}年"
        else:
            # Check for implied experience
            if "十年" in text or "10年" in text:
                years = "10年+"
            elif "五年" in text or "5年" in text:
                years = "5年+"
            elif "三年" in text or "3年" in text:
                years = "3-5年"

        return CareerStage(
            level=level,
            years_exp=years,
            summary=f"推测为{level}" + (f"，约{years}经验" if years else ""),
        )

    def _analyze_skills(self, answers: list[ZhihuAnswer], text: str) -> SkillProfile:
        hard = defaultdict(int)
        soft = defaultdict(int)
        domains = set()

        # Hard skills
        for domain, skills in HARD_SKILLS.items():
            score = 0
            for s in skills:
                score += len(re.findall(re.escape(s), text))
            if score >= 3:
                hard[domain] = score
                domains.add(domain)

        # Soft skills
        for category, markers in SOFT_SKILLS.items():
            score = 0
            for m in markers:
                score += len(re.findall(re.escape(m), text))
            if score >= 2:
                soft[category] = score

        # Expertise domains from question topics
        topic_counter = Counter()
        for a in answers:
            for topic in a.question_topics:
                topic_counter[topic] += 1

        top_domains = [t for t, _ in topic_counter.most_common(5)]

        return SkillProfile(
            hard_skills=[d for d, s in hard.most_common(4)],
            soft_skills=[c for c, s in soft.most_common(4)],
            expertise_domains=top_domains,
            summary=self._skill_summary(hard, soft, top_domains),
        )

    def _skill_summary(self, hard: Counter, soft: Counter, domains: list[str]) -> str:
        parts = []
        top_hard = hard.most_common(3)
        if top_hard:
            parts.append(f"核心硬技能：{'、'.join(h for h, _ in top_hard)}")
        top_soft = soft.most_common(3)
        if top_soft:
            parts.append(f"突出软技能：{'、'.join(c for c, _ in top_soft)}")
        if domains:
            parts.append(f"关注领域：{'、'.join(domains[:5])}")
        return "\n".join(parts)

    def _analyze_work_values(self, text: str) -> WorkValues:
        motivations = []
        preferences = []
        attitudes = []

        for label, markers in WORK_VALUE_MARKERS.items():
            score = sum(len(re.findall(re.escape(m), text)) for m in markers)
            if score >= 2:
                if any(w in label for w in ["影响力", "技术", "成长", "财富"]):
                    motivations.append(label)
                elif any(w in label for w in ["平衡", "稳定", "自由"]):
                    preferences.append(label)
                else:
                    attitudes.append(label)

        # Extract specific attitude phrases
        attitude_patterns = {
            "奋斗型": ["努力", "奋斗", "拼搏", "卷", "竞争"],
            "务实型": ["现实", "务实", "理性", "冷静", "实际"],
            "躺平型": ["躺平", "佛系", "无所谓", "随便", "混"],
            "平衡型": ["平衡", "生活", "爱好", "家庭", "周末"],
        }
        for label, markers in attitude_patterns.items():
            if any(len(re.findall(re.escape(m), text)) >= 2 for m in markers):
                attitudes.append(label)

        return WorkValues(
            motivations=motivations[:3],
            preferences=preferences[:3],
            attitudes=attitudes[:3],
            summary=self._values_summary(motivations, preferences, attitudes),
        )

    def _values_summary(self, motivations: list, preferences: list, attitudes: list) -> str:
        parts = []
        if motivations:
            parts.append(f"工作动力：{'、'.join(motivations[:3])}")
        if preferences:
            parts.append(f"环境偏好：{'、'.join(preferences[:3])}")
        if attitudes:
            parts.append(f"职业态度：{'、'.join(attitudes[:3])}")
        return "\n".join(parts)

    def _analyze_industry(self, text: str) -> IndustryInsight:
        industries = []
        industry_map = {
            "互联网/科技": ["互联网", "科技", "技术", "工程师", "程序员", "产品", "IT", "软件"],
            "金融": ["金融", "投资", "银行", "基金", "保险", "证券", "量化"],
            "教育": ["教育", "学校", "教学", "培训", "课程", "学生"],
            "医疗健康": ["医疗", "医院", "健康", "医生", "药", "患者"],
            "消费/零售": ["消费", "零售", "电商", "品牌", "营销"],
            "制造业": ["制造", "工厂", "供应链", "硬件", "设备", "汽车", "芯片"],
            "房地产": ["房地产", "买房", "房价", "地产", "楼市"],
            "媒体/内容": ["媒体", "内容", "创作", "写作", "短视频", "自媒体"],
        }

        for industry, keywords in industry_map.items():
            score = sum(len(re.findall(re.escape(k), text)) for k in keywords)
            if score >= 3:
                industries.append((industry, score))

        industries.sort(key=lambda x: x[1], reverse=True)
        top_industries = [i for i, _ in industries[:3]]

        # Estimate depth score based on industry-specific vocabulary density
        depth = min(sum(s for _, s in industries) / max(len(text.split()), 1) * 1000, 1.0)

        return IndustryInsight(
            industries=top_industries,
            hot_topics=[],
            depth_score=round(depth, 2),
            summary=f"主要涉及行业：{'、'.join(top_industries) if top_industries else '无明显行业倾向'}"
                    + (f" · 行业深度：{'★★★' if depth > 0.3 else '★★' if depth > 0.1 else '★' if depth > 0.05 else '—'}"),
        )

    def _extract_professional_quotes(self, answers: list[ZhihuAnswer]) -> list[dict]:
        """Extract answers that reveal professional thinking."""
        career_keywords = [
            "工作", "职业", "行业", "技能", "面试", "offer", "跳槽", "薪资",
            "同事", "领导", "团队", "管理", "晋升", "加班", "裁员",
            "老板", "公司", "职场", "打工", "创业", "自由职业",
        ]

        candidates = []
        for a in answers:
            text = a.content
            score = sum(1 for k in career_keywords if k in text)
            if score >= 2 and len(text) > 100:
                # Pick most insightful paragraph
                best = ""
                best_score = 0
                for para in re.split(r"\n{2,}", text):
                    para_score = sum(1 for k in career_keywords if k in para)
                    if para_score > best_score and len(para) < 400:
                        best_score = para_score
                        best = para.strip()
                if best:
                    candidates.append((score, best[:250], a.question_title))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [
            {"text": text, "title": title, "trait": "职业视野"}
            for _, text, title in candidates[:3]
        ]

    def _build_summary(
        self,
        career: CareerStage,
        skills: SkillProfile,
        values: WorkValues,
        industry: IndustryInsight,
        quotes: list[dict],
    ) -> str:
        parts = [
            f"## 职业形象",
            f"**职业阶段**：{career.summary}",
            f"**专业能力**",
        ]
        parts.append(skills.summary)
        parts.append(f"**工作价值观**")
        parts.append(values.summary)
        parts.append(f"**行业视野**")
        parts.append(industry.summary)

        if quotes:
            parts.append(f"**职业相关思考（代表性回答）**")
            for q in quotes:
                parts.append(f"> \"{q['text'][:100]}...\"")
                parts.append(f"> —《{q['title'][:25]}》")

        return "\n".join(parts)


def is_number(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False
