"""Zhihu scraper using Playwright for browser automation.

Handles:
- User profile data extraction
- Answer list pagination and extraction
- Anti-crawling measures (stealth browser, delays)
- Cookie-based authentication persistence
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PwTimeout

from .models import ZhihuAnswer, ZhihuUser, ScrapedData

logger = logging.getLogger(__name__)

# Default user data directory for browser persistence
DEFAULT_USER_DATA = Path.home() / ".zhihu_profiler" / "browser_data"

# Common Zhihu selectors
SELECTORS = {
    "profile_name": ".ProfileHeader-name",
    "profile_headline": ".ProfileHeader-headline",
    "profile_bio": ".ProfileHeader-detail .RichText",
    "answer_item": ".List-item",
    "answer_content": ".RichContent-inner",
    "question_title": ".QuestionHeader-title",
    "question_link": ".ContentItem-title a",
    "vote_count": ".VoteButton--up",
    "comment_count": ".ContentItem-actions button",
    "load_more": ".PaginationButton-next",
    "topic_tag": ".TopicLink .Popover div",
}

# Anti-detection user agents
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]


class ZhihuScraper:
    """Main scraper for Zhihu user data."""

    def __init__(
        self,
        headless: bool = True,
        user_data_dir: Optional[Path] = None,
        max_answers: int = 500,
        delay_range: tuple[float, float] = (1.0, 3.0),
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir or DEFAULT_USER_DATA
        self.max_answers = max_answers
        self.delay_range = delay_range
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self) -> None:
        """Launch the browser and create a persistent context."""
        self.user_data_dir.mkdir(parents=True, exist_ok=True)

        self._playwright = await async_playwright().start()

        # Use persistent context to retain cookies between sessions
        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            user_agent=random.choice(USER_AGENTS),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            # Stealth settings
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            bypass_csp=True,
        )

        # Inject stealth script to hide automation
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
            window.chrome = { runtime: {} };
        """)

        logger.info("Browser launched successfully")

    async def stop(self) -> None:
        """Close browser and cleanup."""
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def _random_delay(self) -> None:
        """Add random delay between actions to avoid detection."""
        await asyncio.sleep(random.uniform(*self.delay_range))

    async def _create_page(self) -> Page:
        """Create a new page with common settings."""
        if not self._context:
            raise RuntimeError("Browser not started. Call start() first.")
        page = await self._context.new_page()
        await page.set_extra_http_headers({
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        return page

    async def _extract_user_from_api(self, user_id: str) -> ZhihuUser:
        """Extract user profile via Zhihu API endpoint (more reliable than DOM parsing)."""
        api_url = f"https://www.zhihu.com/api/v4/members/{user_id}"
        page = await self._create_page()
        try:
            response = await page.goto(
                api_url,
                wait_until="networkidle",
                timeout=15000,
            )
            if response and response.ok:
                data = await response.json()
            else:
                raise ValueError(f"API request failed: {response.status if response else 'no response'}")
        finally:
            await page.close()

        return ZhihuUser(
            id=data.get("id", user_id),
            name=data.get("name", ""),
            headline=data.get("headline", ""),
            bio=data.get("bio", ""),
            avatar_url=data.get("avatar_url_template", "").replace("{size}", "xl"),
            gender=data.get("gender", -1),
            follower_count=data.get("follower_count", 0),
            answer_count=data.get("answer_count", 0),
            article_count=data.get("articles_count", 0),
            voteup_count=data.get("voteup_count", 0),
            thanked_count=data.get("thanked_count", 0),
            locations=[loc.get("name", "") for loc in data.get("locations", [])],
            businesses=[biz.get("name", "") for biz in data.get("business", {}).get("list", [])],
            educations=[edu.get("school", {}).get("name", "") for edu in data.get("educations", [])],
            raw_json=data,
        )

    async def _scrape_answers_from_api(
        self, user_id: str, user_answer_count: int
    ) -> list[ZhihuAnswer]:
        """Scrape answers via Zhihu API with pagination."""
        answers = []
        offset = 0
        limit = 20
        page_count = 0
        target_count = min(self.max_answers, user_answer_count)

        page = await self._create_page()

        try:
            while len(answers) < target_count:
                api_url = (
                    f"https://www.zhihu.com/api/v4/members/{user_id}/answers"
                    f"?include=data[*].is_normal,comment_count,voteup_count,"
                    f"created_time,updated_time,excerpt,content,question,"
                    f"question.topics&offset={offset}&limit={limit}"
                )

                response = await page.goto(api_url, wait_until="networkidle", timeout=15000)
                if not response or not response.ok:
                    logger.warning(f"API request failed at offset {offset}: {response.status if response else 'no response'}")
                    break

                data = await response.json()
                items = data.get("data", [])

                if not items:
                    break

                for item in items:
                    question = item.get("question", {})
                    content = item.get("content", "")
                    # Strip HTML tags for clean text
                    clean_content = self._strip_html(content)

                    answer = ZhihuAnswer(
                        id=item.get("id", 0),
                        question_id=question.get("id", 0),
                        question_title=question.get("title", ""),
                        content=clean_content,
                        excerpt=item.get("excerpt", ""),
                        voteup_count=item.get("voteup_count", 0),
                        comment_count=item.get("comment_count", 0),
                        created_time=self._parse_timestamp(item.get("created_time")),
                        updated_time=self._parse_timestamp(item.get("updated_time")),
                        question_topics=[
                            t.get("name", "")
                            for t in (question.get("topics") or [])
                        ],
                        url=f"https://www.zhihu.com/question/{question.get('id')}/answer/{item.get('id')}",
                    )
                    answers.append(answer)

                offset += limit
                page_count += 1
                logger.info(
                    f"Scraped page {page_count}: {len(answers)}/{target_count} answers"
                )

                if page_count % 5 == 0:
                    logger.info(f"Progress: {len(answers)} answers, taking a brief pause...")
                    await asyncio.sleep(random.uniform(2.0, 4.0))
                else:
                    await self._random_delay()

        finally:
            await page.close()

        return answers

    async def _scrape_answers_from_page(
        self, user_id: str, user_answer_count: int
    ) -> list[ZhihuAnswer]:
        """Fallback: scrape answers by scrolling the profile page."""
        answers = []
        profile_url = f"https://www.zhihu.com/people/{user_id}/answers"
        page = await self._create_page()

        try:
            await page.goto(profile_url, wait_until="networkidle", timeout=30000)
            await self._random_delay()

            scroll_count = 0
            prev_count = 0
            stall_count = 0
            target_count = min(self.max_answers, user_answer_count)

            while len(answers) < target_count:
                # Extract visible answers
                answer_elements = await page.query_selector_all(SELECTORS["answer_item"])
                for el in answer_elements[len(answers):]:
                    try:
                        content_el = await el.query_selector(SELECTORS["answer_content"])
                        question_el = await el.query_selector(SELECTORS["question_link"])
                        vote_el = await el.query_selector(SELECTORS["vote_count"])

                        content = await content_el.inner_text() if content_el else ""
                        question_title = await question_el.inner_text() if question_el else ""

                        answers.append(ZhihuAnswer(
                            id=0,
                            question_id=0,
                            question_title=question_title,
                            content=content.strip(),
                        ))
                    except Exception:
                        continue

                # Scroll down
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2.0, 4.0))
                scroll_count += 1

                if len(answers) == prev_count:
                    stall_count += 1
                    if stall_count >= 3:
                        break
                else:
                    stall_count = 0
                    prev_count = len(answers)

                if scroll_count % 5 == 0:
                    logger.info(f"Scrolled {scroll_count} times: {len(answers)} answers found")

        finally:
            await page.close()

        return answers

    async def scrape_user(self, user_id_or_url: str) -> ScrapedData:
        """Main entry point: scrape a Zhihu user's complete data."""
        # Extract user ID from URL if needed
        user_id = self._extract_user_id(user_id_or_url)
        logger.info(f"Starting scrape for user: {user_id}")

        # Step 1: Get user profile
        logger.info("Fetching user profile...")
        user = await self._extract_user_from_api(user_id)
        logger.info(
            f"User: {user.name} | Followers: {user.follower_count} | "
            f"Answers: {user.answer_count} | Upvotes: {user.voteup_count}"
        )

        # Step 2: Scrape answers
        if user.answer_count > 0:
            target = min(self.max_answers, user.answer_count)
            logger.info(f"Scraping answers (target: {target}/{user.answer_count})...")

            try:
                answers = await self._scrape_answers_from_api(user_id, user.answer_count)
            except Exception as e:
                logger.warning(f"API scraping failed: {e}. Falling back to page scraping.")
                answers = await self._scrape_answers_from_page(user_id, user.answer_count)

            logger.info(f"Scraped {len(answers)} answers")
        else:
            answers = []
            logger.info("No answers to scrape.")

        return ScrapedData(
            user=user,
            answers=answers,
            total_answers_on_profile=user.answer_count,
            answers_scraped=len(answers),
        )

    @staticmethod
    def _extract_user_id(input_str: str) -> str:
        """Extract user ID from URL or return as-is."""
        # Handle URLs like:
        # https://www.zhihu.com/people/xxx
        # https://www.zhihu.com/people/xxx/answers
        match = re.search(r"zhihu\.com/people/([^/?\s]+)", input_str)
        if match:
            return match.group(1)
        return input_str.strip("/")

    @staticmethod
    def _strip_html(html: str) -> str:
        """Strip HTML tags and entities from content."""
        if not html:
            return ""
        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", html)
        # Decode common HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
        """Parse Unix timestamp to datetime."""
        if ts is None or ts == 0:
            return None
        return datetime.fromtimestamp(ts)


async def quick_scrape(user_id_or_url: str, **kwargs) -> ScrapedData:
    """Quick one-shot scrape for testing."""
    scraper = ZhihuScraper(**kwargs)
    await scraper.start()
    try:
        return await scraper.scrape_user(user_id_or_url)
    finally:
        await scraper.stop()
