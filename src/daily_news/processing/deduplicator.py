"""Article deduplication using similarity matching."""

import json
import logging
from difflib import SequenceMatcher
from typing import TypeVar

import anthropic

from daily_news.config import settings
from daily_news.models import ProcessedArticle

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=ProcessedArticle)


class ArticleDeduplicator:
    """Deduplicate articles based on title and description similarity."""

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

    def articles_are_similar(self, article1: T, article2: T) -> bool:
        """Check if two articles are similar using title and description.

        Args:
            article1: First article
            article2: Second article

        Returns:
            True if articles appear to cover the same story
        """
        # Check title similarity
        title_ratio = SequenceMatcher(None, article1.title.lower(), article2.title.lower()).ratio()
        if title_ratio > self.threshold:
            return True

        # Check combined title+description similarity
        text1 = f"{article1.title} {article1.description or ''}"
        text2 = f"{article2.title} {article2.description or ''}"
        combined_ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        if combined_ratio > self.threshold:
            return True

        # Check if key phrases overlap significantly (for headlines about same event)
        words1 = set(article1.title.lower().split())
        words2 = set(article2.title.lower().split())
        # Remove common words
        stopwords = {
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "and",
            "is",
            "are",
            "was",
            "were",
            "be",
        }
        words1 -= stopwords
        words2 -= stopwords
        if len(words1) > 2 and len(words2) > 2:
            overlap = len(words1 & words2) / min(len(words1), len(words2))
            if overlap > 0.6:
                return True

        return False

    def deduplicate(self, articles: list[T]) -> list[T]:
        """Remove duplicate articles, keeping the first occurrence.

        Articles are considered duplicates if their titles/descriptions are similar.
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
                if self.articles_are_similar(article, cluster[0]):
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


class SemanticDeduplicator:
    """Deduplicate articles using Claude AI for semantic understanding.

    This is used as a final pass on top-ranked articles to ensure the digest
    doesn't contain multiple articles about the same event.
    """

    def __init__(self):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for semantic deduplication")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model

    def deduplicate_top_stories(self, articles: list[T], target_count: int = 15) -> list[T]:
        """Deduplicate top stories semantically, keeping diverse events.

        Args:
            articles: List of ranked articles (should already be sorted by score)
            target_count: Desired number of unique stories

        Returns:
            Deduplicated list with one article per unique event
        """
        if len(articles) <= target_count:
            return articles

        # Take more candidates than needed to allow for deduplication
        candidates = articles[: target_count * 3]

        try:
            clusters = self._identify_event_clusters(candidates)
            return self._select_best_per_cluster(candidates, clusters, target_count)
        except Exception as e:
            logger.error(f"Semantic deduplication failed: {e}")
            # Fall back to returning top N
            return articles[:target_count]

    def _identify_event_clusters(self, articles: list[T]) -> list[list[int]]:
        """Use Claude to identify which articles cover the same event.

        Args:
            articles: List of articles to cluster

        Returns:
            List of clusters, where each cluster is a list of article indices
        """
        articles_text = ""
        for i, article in enumerate(articles):
            articles_text += f"[{i}] {article.title}\n"

        prompt = f"""You are an expert news editor. Below are headlines from different news sources.
Group them by the underlying EVENT they cover. Articles about the same event/story should be in the same group.

Headlines:
{articles_text}

Return a JSON array of arrays, where each inner array contains the indices of articles about the SAME event.
Single-article events should still be in their own array.

Example output for 6 articles where 0,2,4 are about one event and 1,3,5 are three separate events:
[[0, 2, 4], [1], [3], [5]]

Important:
- Focus on the core EVENT, not just similar topics
- "Trump meets Zelensky" and "Peace talks progress" about the SAME meeting = same event
- "Trump on Iran" and "Netanyahu visits" if about the SAME meeting = same event
- Different aspects of same breaking story = same event

Return ONLY the JSON array:"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.content[0].text.strip()

        # Handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1])

        clusters: list[list[int]] = json.loads(response_text)
        logger.info(f"Semantic dedup: {len(articles)} articles -> {len(clusters)} unique events")

        return clusters

    def _select_best_per_cluster(
        self, articles: list[T], clusters: list[list[int]], target_count: int
    ) -> list[T]:
        """Select the best article from each cluster.

        Args:
            articles: Original article list
            clusters: List of index clusters
            target_count: Max articles to return

        Returns:
            Best article from each cluster, up to target_count
        """
        selected: list[T] = []

        for cluster in clusters:
            if len(selected) >= target_count:
                break

            if not cluster:
                continue

            # Articles are already sorted by score, so first in cluster is best
            # But we need to find which cluster member has lowest index (highest score)
            best_idx = min(cluster)
            if best_idx < len(articles):
                selected.append(articles[best_idx])

        return selected
