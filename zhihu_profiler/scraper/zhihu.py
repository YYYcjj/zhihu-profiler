"""Zhihu scraper — cookie-based authenticated API + Playwright DOM fallback.

Inspired by syaning/zhihuapi-py: cookie-based auth is required for content access.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import httpx
from playwright.async_api import async_playwright, BrowserContext, Page

from .models import ZhihuAnswer, ZhihuUser, ScrapedData

logger = logging.getLogger(__name__)

# --- Constants ---
BASE_URL = "https://www.zhihu.com"
USER_DATA_DIR = Path(__file__).parent.parent.parent / ".browser_data"
COOKIE_FILE = Path(__file__).parent.parent.parent / ".zhihu_cookies"

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

STEALTH = """
Object.defineProperty(navigator, 'webdriver', { get: () => false });
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
window.chrome = { runtime: {} };
"""

# zhihuapi answer include params (tested working)
ANSWERS_INCLUDE = (
    "data[*].is_normal,admin_closed_comment,reward_info,is_collapsed,"
    "annotation_action,annotation_detail,collapse_reason,collapsed_by,"
    "suggest_edit,comment_count,can_comment,content,editable_content,"
    "attachment,voteup_count,reshipment_settings,comment_permission,"
    "mark_infos,created_time,updated_time,review_info,"
    "question.detail,question.excerpt,question.topics"
)


class ZhihuScraper:
    def __init__(
        self,
        headless: bool = True,
        max_answers: int = 500,
        delay_range: tuple[float, float] = (1.0, 2.5),
    ):
        self.headless = headless
        self.max_answers = max_answers
        self.delay_range = delay_range
        self._playwright = None
        self._context: Optional[BrowserContext] = None
        self._cookies: dict[str, str] = {}
        self._z_c0: str = ""
        self._xsrf: str = ""

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *args):
        await self.stop()

    # ---- lifecycle ----

    async def start(self):
        self._playwright = await async_playwright().start()
        USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

        self._context = await self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(USER_DATA_DIR),
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            user_agent=random.choice(USER_AGENTS),
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            args=["--disable-blink-features=AutomationControlled"],
        )
        await self._context.add_init_script(STEALTH)

        # Load or extract cookies
        await self._load_cookies()
        logger.info("Browser ready, authenticated: %s", bool(self._z_c0))

    async def stop(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    # ---- cookie management ----

    async def _load_cookies(self):
        """Load cookies from previous session or saved file."""
        # 1. Try saved cookie file first
        if COOKIE_FILE.exists():
            raw = COOKIE_FILE.read_text().strip()
            if raw:
                self._parse_cookie_string(raw)
                if self._z_c0:
                    logger.info("Loaded cookies from file")
                    return

        # 2. Try existing browser context cookies
        ctx_cookies = await self._context.cookies(BASE_URL)
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in ctx_cookies)
        self._parse_cookie_string(cookie_str)

    def _parse_cookie_string(self, cookie_str: str):
        """Parse cookie string and extract z_c0 + _xsrf."""
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                self._cookies[k.strip()] = v.strip()
        self._z_c0 = self._cookies.get("z_c0", "")
        self._xsrf = self._cookies.get("_xsrf", "")

    async def ensure_login(self) -> bool:
        """Check if authenticated; if not, open browser for manual login."""
        if self._z_c0:
            return True

        if self.headless:
            logger.warning("Not authenticated and running headless — scraping may fail")
            return False

        # Open Zhihu for manual login
        page = await self._context.new_page()
        try:
            await page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
            logger.info("Please log in to Zhihu in the opened browser window...")
            logger.info("Waiting up to 120 seconds for login...")

            for _ in range(120):
                await asyncio.sleep(1)
                cookies = await self._context.cookies(BASE_URL)
                for c in cookies:
                    if c["name"] == "z_c0":
                        self._parse_cookie_string("; ".join(f"{co['name']}={co['value']}" for co in cookies))
                        # Save for future
                        COOKIE_FILE.write_text(
                            "; ".join(f"{co['name']}={co['value']}" for co in cookies)
                        )
                        logger.info("Login successful!")
                        return True
            return False
        finally:
            await page.close()

    # ---- HTTP helpers (cookie-based, like zhihuapi) ----

    def _api_headers(self) -> dict:
        return {
            "Cookie": "; ".join(f"{k}={v}" for k, v in self._cookies.items()),
            "Authorization": f"Bearer {self._z_c0}" if self._z_c0 else "",
            "Referer": BASE_URL,
            "User-Agent": random.choice(USER_AGENTS),
            "X-Xsrftoken": self._xsrf,
        }

    async def _api_get(self, path: str, params: dict = None) -> dict:
        """Make authenticated GET to Zhihu API."""
        url = f"{BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=self._api_headers(), params=params)
            if resp.status_code == 401 or resp.status_code == 403:
                logger.warning("API auth failed (status %d), response: %s", resp.status_code, resp.text[:200])
            resp.raise_for_status()
            return resp.json()

    # ---- scraping ----

    async def _fetch_profile(self, user_id: str) -> ZhihuUser:
        data = await self._api_get(f"/api/v4/members/{user_id}")
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

    async def _fetch_answers(self, user_id: str, max_items: int) -> list[ZhihuAnswer]:
        answers = []
        offset = 0
        page = 0

        while len(answers) < max_items:
            params = {
                "offset": offset,
                "limit": 20,
                "sort_by": "created",
                "include": ANSWERS_INCLUDE,
            }
            try:
                data = await self._api_get(f"/api/v4/members/{user_id}/answers", params)
            except Exception as e:
                logger.error("API error at offset %d: %s", offset, e)
                break

            items = data.get("data", [])
            paging = data.get("paging", {})

            if not items:
                break

            for item in items:
                question = item.get("question", {})
                content = item.get("content", "")

                if not content:
                    continue

                answers.append(ZhihuAnswer(
                    id=item.get("id", 0),
                    question_id=question.get("id", 0),
                    question_title=question.get("title", ""),
                    content=self._strip_html(content),
                    excerpt=item.get("excerpt", ""),
                    voteup_count=item.get("voteup_count", 0),
                    comment_count=item.get("comment_count", 0),
                    created_time=self._ts(item.get("created_time")),
                    updated_time=self._ts(item.get("updated_time")),
                    question_topics=[t.get("name", "") for t in (question.get("topics") or [])],
                    url=f"{BASE_URL}/question/{question.get('id')}/answer/{item.get('id')}",
                ))

            offset += 20
            page += 1
            logger.info("Page %d: %d answers total", page, len(answers))

            if paging.get("is_end"):
                break
            await asyncio.sleep(random.uniform(*self.delay_range))

        return answers

    async def _scrape_via_dom(self, user_id: str, max_items: int) -> list[ZhihuAnswer]:
        """DOM fallback for when API doesn't have auth."""
        answers = []
        url = f"{BASE_URL}/people/{user_id}/answers?sort_by=created"
        page = await self._context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            scroll = 0
            prev = 0
            stall = 0

            while len(answers) < max_items and scroll < 60:
                items = await page.query_selector_all(".List-item")
                for el in items[len(answers):]:
                    try:
                        # Click "展开阅读全文" if present
                        expand = await el.query_selector("button")
                        if expand:
                            btn_text = await expand.inner_text()
                            if "展开" in btn_text or "阅读全文" in btn_text:
                                await expand.click()
                                await asyncio.sleep(0.5)

                        # Extract content
                        content_el = await el.query_selector(".RichContent-inner, .RichText")
                        if not content_el:
                            continue
                        content = (await content_el.inner_text()).strip()
                        if len(content) < 20:
                            continue

                        # Try to get question title
                        qlink = await el.query_selector(".ContentItem-title a, h2 a")
                        qtitle = (await qlink.inner_text()).strip() if qlink else ""

                        answers.append(ZhihuAnswer(
                            id=0, question_id=0, question_title=qtitle,
                            content=content,
                        ))
                    except Exception:
                        continue

                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(random.uniform(2, 3))
                scroll += 1

                if len(answers) == prev:
                    stall += 1
                    if stall >= 3:
                        break
                else:
                    stall = 0
                    prev = len(answers)
                    logger.info("Scroll %d: %d answers", scroll, len(answers))
        finally:
            await page.close()

        return answers

    async def scrape_user(self, input_str: str) -> ScrapedData:
        user_id = self._extract_id(input_str)
        logger.info("Scraping: %s", user_id)

        # Profile
        user = await self._fetch_profile(user_id)
        logger.info("User: %s | %d answers | %d followers",
                     user.name, user.answer_count, user.follower_count)

        # Answers
        answers = []
        if user.answer_count > 0:
            target = min(self.max_answers, user.answer_count)

            if self._z_c0:
                # Authenticated API
                logger.info("Using authenticated API (target: %d)...", target)
                answers = await self._fetch_answers(user_id, target)
            else:
                # Unauthenticated DOM
                logger.info("No auth — using DOM scraping (target: %d)...", target)
                answers = await self._scrape_via_dom(user_id, target)

            logger.info("Got %d answers", len(answers))

        return ScrapedData(
            user=user,
            answers=answers,
            total_answers_on_profile=user.answer_count,
            answers_scraped=len(answers),
        )

    # ---- utils ----

    @staticmethod
    def _extract_id(s: str) -> str:
        m = re.search(r"zhihu\.com/people/([^/?\s]+)", s)
        return m.group(1) if m else s.strip("/")

    @staticmethod
    def _strip_html(html: str) -> str:
        if not html:
            return ""
        text = re.sub(r"<[^>]+>", "", html)
        for e, c in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"), ("&nbsp;", " ")]:
            text = text.replace(e, c)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _ts(t: Optional[int]) -> Optional[datetime]:
        return datetime.fromtimestamp(t) if t else None
