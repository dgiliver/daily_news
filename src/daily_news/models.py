"""Data models for news articles and digests."""

from datetime import datetime
from enum import Enum
from typing import Any
import hashlib

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Region(str, Enum):
    """Geographic regions for news sources."""

    AMERICAS_US = "americas_us"
    AMERICAS_LATAM = "americas_latam"
    EUROPE = "europe"
    ASIA_PACIFIC = "asia_pacific"
    MIDDLE_EAST = "middle_east"
    AFRICA = "africa"
    LOCAL_NY = "local_ny"
    GLOBAL = "global"


class Category(str, Enum):
    """News categories."""

    GENERAL = "general"
    POLITICS = "politics"
    ECONOMY = "economy"
    TECHNOLOGY = "technology"
    LOCAL = "local"


class SourceConfig(BaseModel):
    """Configuration for a news source."""

    name: str
    region: Region
    category: Category
    url: str
    language: str = "en"
    priority: str = "medium"  # high, medium, low
    enabled: bool = True


class RawArticle(BaseModel):
    """Article as collected from source."""

    source_name: str
    source_region: Region
    source_category: Category
    title: str
    url: HttpUrl
    description: str | None = None
    content: str | None = None
    published_at: datetime | None = None
    language: str = "en"
    image_url: HttpUrl | None = None

    @field_validator("title", "description", mode="before")
    @classmethod
    def clean_text(cls, v: Any) -> Any:
        """Clean up text fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    def generate_id(self) -> str:
        """Generate a unique ID based on URL."""
        return hashlib.sha256(str(self.url).encode()).hexdigest()[:16]


class ProcessedArticle(BaseModel):
    """Article after translation and processing."""

    id: str
    source_name: str
    source_region: Region
    source_category: Category
    original_title: str
    title: str  # Translated if needed
    url: HttpUrl
    description: str
    original_language: str
    published_at: datetime
    collected_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def from_raw(
        cls,
        raw: RawArticle,
        translated_title: str | None = None,
        translated_description: str | None = None,
    ) -> "ProcessedArticle":
        """Create a ProcessedArticle from a RawArticle."""
        return cls(
            id=raw.generate_id(),
            source_name=raw.source_name,
            source_region=raw.source_region,
            source_category=raw.source_category,
            original_title=raw.title,
            title=translated_title or raw.title,
            url=raw.url,
            description=translated_description or raw.description or "",
            original_language=raw.language,
            published_at=raw.published_at or datetime.utcnow(),
        )


class RankedArticle(ProcessedArticle):
    """Article with AI-assigned significance score."""

    significance_score: float = Field(ge=0, le=100)
    ranking_rationale: str = ""
    dedupe_cluster_id: str | None = None


class CollectionStats(BaseModel):
    """Statistics from a collection run."""

    sources_attempted: int = 0
    sources_succeeded: int = 0
    articles_collected: int = 0
    articles_after_dedup: int = 0
    errors: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0


class NewsDigest(BaseModel):
    """Complete digest for delivery."""

    date: datetime
    top_stories: list[RankedArticle]
    sms_headlines: list[RankedArticle]  # Top stories for SMS
    collection_stats: CollectionStats

    @property
    def story_count(self) -> int:
        """Total number of stories in digest."""
        return len(self.top_stories)
