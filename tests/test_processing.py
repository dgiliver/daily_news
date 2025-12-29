"""Tests for processing modules."""

import pytest
from datetime import datetime

from daily_news.models import ProcessedArticle, Region, Category
from daily_news.processing.deduplicator import ArticleDeduplicator


class TestDeduplicator:
    """Tests for ArticleDeduplicator."""

    def create_article(self, title: str, source: str = "Source") -> ProcessedArticle:
        """Helper to create test articles."""
        return ProcessedArticle(
            id=f"id_{hash(title)}",
            source_name=source,
            source_region=Region.AMERICAS_US,
            source_category=Category.GENERAL,
            original_title=title,
            title=title,
            url=f"https://example.com/{hash(title)}",
            description="Test description",
            original_language="en",
            published_at=datetime.utcnow(),
            collected_at=datetime.utcnow(),
        )

    def test_is_similar_identical(self):
        """Test that identical texts are similar."""
        dedup = ArticleDeduplicator()
        assert dedup.is_similar("Hello World", "Hello World")

    def test_is_similar_slight_difference(self):
        """Test that slightly different texts are similar."""
        dedup = ArticleDeduplicator(similarity_threshold=0.7)
        assert dedup.is_similar(
            "Breaking: Major earthquake strikes Japan",
            "Breaking: Major earthquake strikes Japan today",
        )

    def test_is_similar_different(self):
        """Test that different texts are not similar."""
        dedup = ArticleDeduplicator()
        assert not dedup.is_similar(
            "Stock market reaches all-time high",
            "New species discovered in Amazon",
        )

    def test_deduplicate_removes_duplicates(self):
        """Test that duplicates are removed."""
        dedup = ArticleDeduplicator(similarity_threshold=0.7)

        articles = [
            self.create_article("Major earthquake strikes Japan", "Source A"),
            self.create_article("Major earthquake strikes Japan today", "Source B"),
            self.create_article("Earthquake hits Japan region", "Source C"),
            self.create_article("Stock market news today", "Source D"),
        ]

        unique = dedup.deduplicate(articles)

        # Should keep first earthquake article and stock market article
        assert len(unique) < len(articles)
        assert any("earthquake" in a.title.lower() for a in unique)
        assert any("stock" in a.title.lower() for a in unique)

    def test_deduplicate_preserves_unique(self):
        """Test that unique articles are preserved."""
        dedup = ArticleDeduplicator()

        articles = [
            self.create_article("First unique story"),
            self.create_article("Second completely different story"),
            self.create_article("Third unrelated article"),
        ]

        unique = dedup.deduplicate(articles)
        assert len(unique) == 3

    def test_find_duplicates(self):
        """Test finding duplicate pairs."""
        dedup = ArticleDeduplicator(similarity_threshold=0.7)

        articles = [
            self.create_article("Breaking news: President speaks"),
            self.create_article("Breaking news: President speaks today"),
            self.create_article("Weather forecast for tomorrow"),
        ]

        duplicates = dedup.find_duplicates(articles)
        assert len(duplicates) == 1
        assert "President" in duplicates[0][0].title
