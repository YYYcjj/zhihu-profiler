"""Data models for Zhihu user profiles and answers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ZhihuUser(BaseModel):
    """Zhihu user profile information."""

    id: str = Field(description="Unique user ID, e.g. 'zhihu-admin'")
    name: str = Field(description="Display name")
    headline: str = Field(default="", description="One-line bio / headline")
    bio: str = Field(default="", description="Full bio description")
    avatar_url: Optional[str] = Field(default=None, description="Avatar image URL")
    gender: int = Field(default=-1, description="0: female, 1: male, -1: unknown")
    follower_count: int = Field(default=0, description="Number of followers")
    answer_count: int = Field(default=0, description="Total number of answers")
    article_count: int = Field(default=0, description="Total number of articles")
    voteup_count: int = Field(default=0, description="Total upvotes received")
    thanked_count: int = Field(default=0, description="Total thanks received")
    locations: list[str] = Field(default_factory=list, description="Locations on profile")
    businesses: list[str] = Field(default_factory=list, description="Work experiences")
    educations: list[str] = Field(default_factory=list, description="Education info")
    raw_json: dict = Field(default_factory=dict, description="Raw API response")

    @property
    def profile_url(self) -> str:
        return f"https://www.zhihu.com/people/{self.id}"


class ZhihuAnswer(BaseModel):
    """A single Zhihu answer."""

    id: int = Field(description="Answer ID")
    question_id: int = Field(description="Question ID")
    question_title: str = Field(description="Title of the question")
    content: str = Field(description="Full answer content in plain text")
    excerpt: str = Field(default="", description="Short excerpt / summary")
    voteup_count: int = Field(default=0, description="Upvotes on this answer")
    comment_count: int = Field(default=0, description="Number of comments")
    created_time: Optional[datetime] = Field(default=None, description="When the answer was created")
    updated_time: Optional[datetime] = Field(default=None, description="When the answer was last updated")
    question_topics: list[str] = Field(default_factory=list, description="Topic tags on the question")
    url: str = Field(default="", description="Answer permalink URL")

    @property
    def text_length(self) -> int:
        return len(self.content)


class ScrapedData(BaseModel):
    """Complete scraped dataset for one user."""

    user: ZhihuUser
    answers: list[ZhihuAnswer] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)
    total_answers_on_profile: int = 0
    answers_scraped: int = 0

    @property
    def total_text_chars(self) -> int:
        return sum(a.text_length for a in self.answers)

    @property
    def total_upvotes(self) -> int:
        return sum(a.voteup_count for a in self.answers)
