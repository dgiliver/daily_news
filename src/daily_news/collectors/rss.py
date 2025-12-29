"""RSS feed collector with async support."""

import asyncio
import contextlib
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from daily_news.collectors.base import BaseCollector
from daily_news.config import settings
from daily_news.models import RawArticle, SourceConfig

logger = logging.getLogger(__name__)


class RSSCollector(BaseCollector):
    """Collector for RSS/Atom feeds."""

    def __init__(
        self,
        max_articles_per_source: int | None = None,
        timeout: int | None = None,
        max_concurrent: int | None = None,
    ):
        self.max_articles = max_articles_per_source or settings.max_articles_per_source
        self.timeout = timeout or settings.collection_timeout
        self.max_concurrent = max_concurrent or settings.max_concurrent_requests
        self._semaphore: asyncio.Semaphore | None = None

    async def collect(self, source: SourceConfig) -> list[RawArticle]:
        """Collect articles from a single RSS source.

        Args:
            source: Source configuration

        Returns:
            List of raw articles from the feed
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "DailyNewsAggregator/1.0"},
            ) as client:
                response = await client.get(source.url)
                response.raise_for_status()

                feed = feedparser.parse(response.text)

                if feed.bozo and not feed.entries:
                    logger.warning(f"Feed parse error for {source.name}: {feed.bozo_exception}")
                    return []

                articles = []
                for entry in feed.entries[: self.max_articles]:
                    article = self._parse_entry(entry, source)
                    if article:
                        articles.append(article)

                logger.info(f"Collected {len(articles)} articles from {source.name}")
                return articles

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error for {source.name}: {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Request error for {source.name}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error for {source.name}: {e}")
            return []

    async def health_check(self, source: SourceConfig) -> bool:
        """Check if RSS feed is accessible."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.head(source.url, follow_redirects=True)
                return bool(response.status_code < 400)
        except Exception:
            return False

    async def collect_all(self, sources: list[SourceConfig]) -> list[RawArticle]:
        """Collect articles from all sources concurrently.

        Args:
            sources: List of source configurations

        Returns:
            All articles from all sources
        """
        self._semaphore = asyncio.Semaphore(self.max_concurrent)

        async def collect_with_semaphore(source: SourceConfig) -> list[RawArticle]:
            async with self._semaphore:  # type: ignore
                return await self.collect(source)

        tasks = [collect_with_semaphore(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_articles = []
        for result in results:
            if isinstance(result, list):
                all_articles.extend(result)
            elif isinstance(result, Exception):
                logger.error(f"Collection task failed: {result}")

        return all_articles

    def _parse_entry(self, entry: Any, source: SourceConfig) -> RawArticle | None:
        """Parse a feed entry into a RawArticle.

        Args:
            entry: Feed entry from feedparser
            source: Source configuration

        Returns:
            RawArticle or None if parsing fails
        """
        try:
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()

            if not title or not link:
                return None

            # Extract description
            description = ""
            if "summary" in entry:
                description = entry.summary
            elif "description" in entry:
                description = entry.description

            # Clean HTML from description
            description = self._clean_html(description)

            # Parse published date
            published_at = None
            if "published_parsed" in entry and entry.published_parsed:
                with contextlib.suppress(TypeError, ValueError):
                    published_at = datetime(*entry.published_parsed[:6])
            elif "updated_parsed" in entry and entry.updated_parsed:
                with contextlib.suppress(TypeError, ValueError):
                    published_at = datetime(*entry.updated_parsed[:6])
            elif "published" in entry:
                with contextlib.suppress(TypeError, ValueError):
                    published_at = parsedate_to_datetime(entry.published)

            # Extract image URL if available
            image_url = None
            if "media_content" in entry and entry.media_content:
                image_url = entry.media_content[0].get("url")
            elif "media_thumbnail" in entry and entry.media_thumbnail:
                image_url = entry.media_thumbnail[0].get("url")

            return RawArticle(
                source_name=source.name,
                source_region=source.region,
                source_category=source.category,
                title=title,
                url=link,
                description=description[:500] if description else None,
                published_at=published_at,
                language=source.language,
                image_url=image_url,
            )

        except Exception as e:
            logger.debug(f"Failed to parse entry from {source.name}: {e}")
            return None

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re

        if not text:
            return ""
        # Remove HTML tags
        clean = re.sub(r"<[^>]+>", "", text)
        # Clean up whitespace
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean
