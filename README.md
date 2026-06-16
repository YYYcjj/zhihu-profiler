# Zhihu Profiler

Deep personality profiling through Zhihu answer analysis.

通过知乎用户的历史回答，自动生成**人格画像、兴趣领域、价值体系、表达风格、情感基调**等多维度深度分析报告。

## Features

- **智能数据采集** - 基于 Playwright 的浏览器自动化，通过知乎 API 高效抓取用户回答
- **中文深度 NLP** - jieba 分词 + TF-IDF/TextRank 关键词提取 + SnowNLP 情感分析
- **大五人格推断** - 基于语言标记物推断开放性、尽责性、外向性、宜人性、神经质
- **兴趣领域分类** - 10 大领域 100+ 关键词自动归类
- **价值体系分析** - Schwartz 理论框架，识别核心价值观与内在张力
- **表达风格量化** - 句长、词汇丰富度、修辞手法、结构偏好等多维度量化
- **交互式报告** - 自包含 HTML 报告，含 ECharts 图表，可直接分享
- **Web 界面** - 本地 Web 应用，输入链接即可分析，支持历史记录保存与查看

## Web UI

```bash
# 启动 Web 界面
zhihu-profiler web

# 自定义端口
zhihu-profiler web --port 8080
```

打开浏览器访问 `http://127.0.0.1:8765`，粘贴知乎用户链接即可开始分析。

- 实时进度条，展示抓取和分析状态
- 分析结果自动保存，支持历史记录浏览
- 一键删除不再需要的分析记录

## Architecture

```
zhihu-profiler/
├── zhihu_profiler/
│   ├── scraper/          # 数据采集层
│   │   ├── models.py     # 数据模型 (Pydantic)
│   │   └── zhihu.py      # Playwright 爬虫
│   ├── nlp/              # NLP 处理层
│   │   ├── preprocessing.py  # 分词/清洗/关键词
│   │   └── sentiment.py      # 情感分析
│   ├── analysis/         # 分析层
│   │   ├── personality.py    # 人格特征
│   │   ├── interests.py      # 兴趣领域
│   │   ├── values.py         # 价值体系
│   │   ├── style.py          # 表达风格
│   │   └── profiler.py       # 主分析器
│   ├── viz/              # 可视化层
│   │   └── dashboard.py      # HTML 报告生成
│   ├── web/              # Web 界面
│   │   ├── server.py         # FastAPI 后端
│   │   └── static/
│   │       └── index.html    # 前端页面
│   └── cli.py            # 命令行入口
├── examples/
│   └── basic_usage.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Installation

```bash
# Clone
git clone https://github.com/YYYcjj/zhihu-profiler.git
cd zhihu-profiler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install
pip install -e .

# Install Playwright browsers
playwright install chromium
```

## Quick Start

### One-line analysis

```bash
# Analyze by user ID
zhihu-profiler analyze zhang-jia-wei

# Analyze by full URL
zhihu-profiler analyze https://www.zhihu.com/people/zhihu-admin

# Limit answers and show browser
zhihu-profiler analyze zhang-jia-wei -n 200 --no-headless

# Use verbose output
zhihu-profiler analyze zhang-jia-wei -v
```

### Programmatic usage

```python
import asyncio
from zhihu_profiler.scraper.zhihu import ZhihuScraper
from zhihu_profiler.analysis.profiler import Profiler
from zhihu_profiler.viz.dashboard import ReportGenerator

async def main():
    # Step 1: Scrape
    async with ZhihuScraper(headless=True, max_answers=200) as scraper:
        data = await scraper.scrape_user("user-id")

    # Step 2: Profile
    profiler = Profiler()
    profile = profiler.profile(data)

    # Step 3: Generate report
    generator = ReportGenerator()
    html_path = generator.generate(profile)
    print(f"Report: {html_path}")

asyncio.run(main())
```

## Analysis Dimensions

### Personality (大五人格 OCEAN)

| 维度 | 说明 |
|------|------|
| 开放性 | 求知欲、想象力、审美敏感度 |
| 尽责性 | 自律、条理性、目标导向 |
| 外向性 | 社交活跃度、表达欲望 |
| 宜人性 | 合作倾向、同理心 |
| 神经质 | 情绪稳定性、焦虑倾向 |

### Interests (兴趣领域)

- 科技与互联网
- 产品与商业
- 投资与金融
- 职场与成长
- 人文与社科
- 生活与情感
- 科学知识
- 社会热点
- 创作与表达

### Values (价值体系)

基于 Schwartz 价值观理论，分析：
- 成就导向 vs 体验主义
- 理想主义 vs 务实主义
- 自由主义 vs 传统价值
- 自我超越 vs 社会关怀

### Writing Style (表达风格)

- 平均句长 / 回答长度
- 词汇丰富度 (Type-Token Ratio)
- 修辞手法使用频率
- 结构偏好 (叙事 / 列举 / 自由流)
- 语气风格 (幽默 / 严谨 / 随性 / 权威)

## Output

### CLI 输出

```
╭────────────────────────────────────────────────────╮
│ Zhihu Profiler · Deep Personality Analysis         │
╰────────────────────────────────────────────────────╯

Scraping: zhang-jia-wei
Scraped 200 answers from 张佳玮

Running analysis pipeline...
Profile saved to output/zhang-jia-wei_profile.json

╭────────────────── Analysis Summary ──────────────────╮
│ # 张佳玮 · 知乎人物画像                              │
│                                                      │
│ ## 基础数据                                          │
│ - 回答数：200                                        │
│ - 总字数：156,432                                    │
│ - 总赞同：2,340,000                                  │
│ ...                                                  │
╰──────────────────────────────────────────────────────╯
```

### HTML 报告

生成包含以下图表的交互式 HTML 报告：

- 人格特征柱状图
- 兴趣领域环形图
- 价值体系雷达图
- 情感统计卡片
- 表达风格指标体系

## Requirements

- Python 3.9+
- Chromium (auto-installed by Playwright)

## Login & Anti-Crawling

首次使用可能需要进行知乎登录，使用 `--no-headless` 参数显示浏览器窗口：

```bash
zhihu-profiler analyze <user> --no-headless
```

登录信息会保存在 `~/.zhihu_profiler/browser_data/` 中，后续无需重复登录。

爬虫内置了反检测措施：
- 随机 User-Agent
- 浏览器指纹伪装
- 随机请求延迟
- Stealth 脚本注入

## Roadmap

- [x] Web UI 界面
- [ ] 接入 BERT/RoBERTa 模型做更精准的情感分析
- [ ] 知识图谱构建 (回答的实体-关系网络)
- [ ] 多用户对比分析
- [ ] Web UI 界面
- [ ] 朋友圈/微博数据源扩展
- [ ] 时间序列分析 (观点演变)

## Disclaimer

本工具仅用于学习和研究目的。请遵守知乎用户协议和相关法律法规，尊重他人隐私。不要用于商业用途或侵犯他人权益。

## License

MIT
