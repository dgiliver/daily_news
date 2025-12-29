"""Article deduplication using similarity matching."""

import logging
from difflib import SequenceMatcher
from typing import TypeVar

from daily_news.config import settings
from daily_news.models import ProcessedArticle

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=ProcessedArticle)


class ArticleDeduplicator:
    """Deduplicate articles based on title similarity."""

    def __init__(self, similarity_threshold: float | None = None):
        self.threshold = similarity_threshold or settings.dedup_similarity_threshold

    def is_similar(self, text1: str, text2: str) -> bool:
        """Check if two texts are similar.

        Args:
            text1: First text
            text2: Second text

        Returns:
            True if similarity exceeds threshold
        """
        ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        return ratio > self.threshold

    def deduplicate(self, articles: list[T]) -> list[T]:
        """Remove duplicate articles, keeping the first occurrence.

        Articles are considered duplicates if their titles are similar.
        When duplicates are found, keep the one from the higher priority source.

        Args:
            articles: List of processed articles

        Returns:
            Deduplicated list of articles
        """
        if not settings.enable_deduplication:
            return articles

        # Cluster similar articles
        clusters: list[list[T]] = []

        for article in articles:
            matched = False
            for cluster in clusters:
                if self.is_similar(article.title, cluster[0].title):
                    cluster.append(article)
                    matched = True
                    break

            if not matched:
                clusters.append([article])

        # Select best article from each cluster
        deduplicated = []
        for cluster in clusters:
            if len(cluster) == 1:
                deduplicated.append(cluster[0])
            else:
                # For now, just keep the first one (could enhance with priority logic)
                deduplicated.append(cluster[0])
                logger.debug(f"Removed {len(cluster) - 1} duplicates of: {cluster[0].title[:50]}")

        removed_count = len(articles) - len(deduplicated)
        if removed_count > 0:
            logger.info(f"Deduplication removed {removed_count} duplicate articles")

        return deduplicated

    def find_duplicates(self, articles: list[T]) -> list[tuple[T, T]]:
        """Find pairs of duplicate articles.

        Args:
            articles: List of articles to check

        Returns:
            List of (article1, article2) tuples that are duplicates
        """
        duplicates = []

        for i, article1 in enumerate(articles):
            for article2 in articles[i + 1 :]:
                if self.is_similar(article1.title, article2.title):
                    duplicates.append((article1, article2))

        return duplicates
