"""Basic usage example for Zhihu Profiler."""

import asyncio
import json
import logging
from pathlib import Path

from zhihu_profiler.scraper.zhihu import ZhihuScraper
from zhihu_profiler.scraper.models import ZhihuAnswer, ZhihuUser, ScrapedData
from zhihu_profiler.analysis.profiler import Profiler
from zhihu_profiler.viz.dashboard import ReportGenerator

logging.basicConfig(level=logging.INFO)


async def example_full_pipeline():
    """Complete pipeline: scrape -> analyze -> report."""
    print("=" * 60)
    print("Zhihu Profiler - Full Pipeline Example")
    print("=" * 60)

    # Replace with actual Zhihu user ID
    USER_ID = "zhihu-admin"

    # Step 1: Scrape data
    print("\n[1] Scraping data...")
    async with ZhihuScraper(
        headless=True,
        max_answers=100,
    ) as scraper:
        data = await scraper.scrape_user(USER_ID)

    print(f"    User: {data.user.name}")
    print(f"    Answers scraped: {data.answers_scraped}/{data.total_answers_on_profile}")
    print(f"    Total chars: {data.total_text_chars:,}")
    print(f"    Total upvotes: {data.total_upvotes:,}")

    # Step 2: Run analysis
    print("\n[2] Running analysis...")
    profiler = Profiler()
    profile = profiler.profile(data)

    print(f"\n    Personality Big Five:")
    if profile.personality:
        for k, v in profile.personality.get("big_five", {}).items():
            bar = "#" * int(v // 5) + " " * (20 - int(v // 5))
            print(f"    {k:20s} [{bar}] {v:.1f}")

    print(f"\n    Top Interests:")
    if profile.interests:
        for domain, score in profile.interests.get("top_domains", [])[:5]:
            print(f"    - {domain}: {score:.1f}")

    print(f"\n    Core Values: {profile.values.get('core_values', []) if profile.values else 'N/A'}")

    print(f"\n    Sentiment: {profile.sentiment.get('description', 'N/A') if profile.sentiment else 'N/A'}")

    if profile.style:
        print(f"\n    Writing Style:")
        print(f"    - Avg answer length: {profile.style.get('avg_answer_length', 0):.0f} chars")
        print(f"    - Vocabulary richness: {profile.style.get('vocabulary_richness', 0):.3f}")
        print(f"    - Tone: {profile.style.get('tone_style', 'N/A')}")

    # Step 3: Generate HTML report
    print("\n[3] Generating report...")
    generator = ReportGenerator()
    report_path = generator.generate(profile)
    print(f"    Report saved to: {report_path}")

    # Step 4: Save JSON profile
    json_path = Path("output") / f"{USER_ID}_profile.json"
    profiler.save_profile(profile, json_path)
    print(f"    JSON profile saved to: {json_path}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60)

    return profile


async def example_with_saved_data():
    """Load pre-scraped data and re-analyze."""
    print("Loading saved data...")

    # Load from JSON
    data_path = Path("output/zhihu-admin_raw.json")
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        return

    with open(data_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    data = ScrapedData(**raw)

    # Re-run analysis
    profiler = Profiler(
        enable_sentiment=True,
        enable_personality=True,
        enable_interests=True,
        enable_values=True,
        enable_style=True,
    )
    profile = profiler.profile(data)

    # Generate report
    generator = ReportGenerator()
    report_path = generator.generate(profile)

    print(f"Report: {report_path}")
    print(f"Summary:\n{profile.summary}")


async def example_basic_stats():
    """Basic statistics without full analysis."""
    async with ZhihuScraper(headless=True, max_answers=50) as scraper:
        data = await scraper.scrape_user("zhihu-admin")

    # Just compute basic stats
    answers = data.answers
    if not answers:
        print("No answers found")
        return

    # Average answer length
    avg_len = sum(a.text_length for a in answers) / len(answers)
    print(f"Average answer length: {avg_len:.0f} chars")

    # Most upvoted answer
    top = max(answers, key=lambda a: a.voteup_count)
    print(f"Most upvoted: {top.voteup_count} votes on '{top.question_title[:50]}...'")

    # Activity over time
    dates = [a.created_time for a in answers if a.created_time]
    if dates:
        from datetime import datetime
        dates.sort()
        print(f"Date range: {dates[0].strftime('%Y-%m-%d')} to {dates[-1].strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    asyncio.run(example_full_pipeline())
