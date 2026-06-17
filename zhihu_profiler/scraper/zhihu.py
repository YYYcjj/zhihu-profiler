"""Zhihu scraper using Playwright for browser automation.

Handles:
- User profile data extraction via API
- Answer extraction with API + DOM fallback
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

DEFAULT_USER_DATA = Path(__file__).parent.parent.parent / ".browser_data"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

SELECTORS = {
    "answer_item": ".List-item",
    "answer_content": ".RichContent-inner",
    "answer_content_fallback": ".RichText",
    "question_title": ".QuestionHeader-title",
    "question_link": ".ContentItem-title a",
    "vote_count": ".VoteButton--up",
    "expand_btn": ".Button.ContentItem-rightButton",
}

STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
window.chrome = { runtime: {} };
"""


class ZhihuScraper:
    """Main scraper for Zhihu user data."""

    def __init__(
        self,
        headless: bool = True,
        user_data_dir: Optional[Path] = None,
        max_answers: int = 500,
        delay_range: tuple[float, float] = (1.5, 3.5),
    ):
        self.headless = headless
        self.user_data_dir = user_data_dir or DEFAULT_USER_DATA
        self.max_answers = max_answers
        self.delay_range = delay_range
        self._playwright = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    async def start(self) -> None:
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.user_data_dir),
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            user_agent=random.choice(USER_AGENTS),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            bypass_csp=True,
        )
        await self._context.add_init_script(STEALTH_SCRIPT)
        logger.info("Browser launched")

    async def stop(self) -> None:
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("Browser closed")

    async def _random_delay(self, extra: float = 0) -> None:
        await asyncio.sleep(random.uniform(*self.delay_range) + extra)

    async def _create_page(self) -> Page:
        if not self._context:
            raise RuntimeError("Browser not started")
        page = await self._context.new_page()
        await page.set_extra_http_headers({
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        return page

    async def _extract_user_from_api(self, user_id: str) -> ZhihuUser:
        api_url = f"https://www.zhihu.com/api/v4/members/{user_id}"
        page = await self._create_page()
        try:
            resp = await page.goto(api_url, wait_until="networkidle", timeout=15000)
            if not resp or not resp.ok:
                raise ValueError(f"Profile API failed: {resp.status if resp else 'no response'}")
            data = await resp.json()
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

    async def _scrape_answers_from_api(self, user_id: str, max_items: int) -> list[ZhihuAnswer]:
        """Scrape answers via Zhihu API."""
        answers = []
        offset = 0
        limit = 20
        page_count = 0
        empty_pages = 0

        page = await self._create_page()
        try:
            while len(answers) < max_items and empty_pages < 3:
                api_url = (
                    f"https://www.zhihu.com/api/v4/members/{user_id}/answers"
                    f"?include=data[*].is_normal,admin_closed_comment,"
                    f"reward_info,is_collapsed,annotation_action,annotation_detail,"
                    f"collapse_reason,collapsed_by,suggest_edit,comment_count,"
                    f"can_comment,content,editable_content,attachment,voteup_count,"
                    f"reshipment_settings,comment_permission,"
                    f"created_time,updated_time,review_info,"
                    f"question.detail,question.excerpt,question.topics,"
                    f"&offset={offset}&limit={limit}&sort_by=created"
                )

                resp = await page.goto(api_url, wait_until="networkidle", timeout=20000)
                if not resp or not resp.ok:
                    logger.warning(f"API error at offset {offset}: {resp.status if resp else 'no response'}")
                    break

                data = await resp.json()
                items = data.get("data", [])
                paging = data.get("paging", {})
                is_end = paging.get("is_end", False)

                if not items:
                    empty_pages += 1
                    if is_end:
                        break
                    offset += limit
                    continue

                empty_pages = 0
                for item in items:
                    question = item.get("question", {})
                    content = item.get("content", "") or item.get("excerpt", "")

                    if not content and not question:
                        continue

                    clean_content = self._strip_html(content)
                    answers.append(ZhihuAnswer(
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
                            t.get("name", "") for t in (question.get("topics") or [])
                        ],
                        url=f"https://www.zhihu.com/question/{question.get('id')}/answer/{item.get('id')}",
                    ))

                offset += limit
                page_count += 1
                logger.info(f"API page {page_count}: {len(answers)} answers")

                if is_end:
                    break

                await self._random_delay()
        finally:
            await page.close()

        return answers

    async def _scrape_answers_from_list_page(self, user_id: str, max_items: int) -> list[ZhihuAnswer]:
        """Scrape answers by rendering the user's answer list page."""
        answers = []
        url = f"https://www.zhihu.com/people/{user_id}/answers?sort_by=created"
        page = await self._create_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await self._random_delay(2)

            scroll_count = 0
            prev_count = 0
            stall = 0

            while len(answers) < max_items:
                items = await page.query_selector_all(SELECTORS["answer_item"])
                new_items = items[len(answers):]

                for el in new_items:
                    try:
                        # Try to expand truncated answer
                        expand = await el.query_selector(SELECTORS["expand_btn"])
                        if expand:
                            await expand.click()
                            await asyncio.sleep(0.3)

                        # Extract content
                        content = ""
                        for sel in [SELECTORS["answer_content"], SELECTORS["answer_content_fallback"]]:
                            content_el = await el.query_selector(sel)
                            if content_el:
                                content = await content_el.inner_text()
                                if content.strip():
                                    break

                        if not content or len(content) < 10:
                            continue

                        # Extract question title
                        qtitle = ""
                        qlink = await el.query_selector(SELECTORS["question_link"])
                        if qlink:
                            qtitle = await qlink.inner_text()

                        answers.append(ZhihuAnswer(
                            id=0, question_id=0, question_title=qtitle.strip(),
                            content=content.strip(),
                        ))
                    except Exception as e:
                        continue

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2, 3))
                scroll_count += 1

                if len(answers) == prev_count:
                    stall += 1
                    if stall >= 3:
                        logger.info(f"No new items after {stall} scrolls, stopping")
                        break
                else:
                    stall = 0
                    prev_count = len(answers)
                    logger.info(f"Scroll {scroll_count}: {len(answers)} answers")

                if scroll_count > 50:
                    break
        finally:
            await page.close()

        return answers

    async def scrape_user(self, user_id_or_url: str) -> ScrapedData:
        user_id = self._extract_user_id(user_id_or_url)
        logger.info(f"Scraping user: {user_id}")

        # Step 1: Profile
        logger.info("Fetching profile...")
        user = await self._extract_user_from_api(user_id)
        logger.info(f"User: {user.name} | {user.answer_count} answers | {user.follower_count} followers")

        answers = []
        if user.answer_count > 0:
            target = min(self.max_answers, user.answer_count)
            logger.info(f"Scraping answers (target: {target})...")

            # Strategy 1: API
            try:
                answers = await self._scrape_answers_from_api(user_id, target)
            except Exception as e:
                logger.warning(f"API scraping failed: {e}")

            # Strategy 2: Page scraping if API had few results
            if len(answers) < min(3, target):
                logger.info("API got few results, trying page scraping...")
                try:
                    page_answers = await self._scrape_answers_from_list_page(user_id, target)
                    if len(page_answers) > len(answers):
                        answers = page_answers
                except Exception as e:
                    logger.warning(f"Page scraping failed: {e}")

            logger.info(f"Total scraped: {len(answers)} answers")

        return ScrapedData(
            user=user,
            answers=answers,
            total_answers_on_profile=user.answer_count,
            answers_scraped=len(answers),
        )

    @staticmethod
    def _extract_user_id(input_str: str) -> str:
        match = re.search(r"zhihu\.com/people/([^/?\s]+)", input_str)
        if match:
            return match.group(1)
        return input_str.strip("/")

    @staticmethod
    def _strip_html(html: str) -> str:
        if not html:
            return ""
        text = re.sub(r"<[^>]+>", "", html)
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _parse_timestamp(ts: Optional[int]) -> Optional[datetime]:
        if ts is None or ts == 0:
            return None
        return datetime.fromtimestamp(ts)


async def quick_scrape(user_id_or_url: str, **kwargs) -> ScrapedData:
    scraper = ZhihuScraper(**kwargs)
    await scraper.start()
    try:
        return await scraper.scrape_user(user_id_or_url)
    finally:
        await scraper.stop()
