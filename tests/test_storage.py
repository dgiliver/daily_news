"""Tests for storage module."""

from datetime import date, datetime
from pathlib import Path

import pytest

from daily_news.models import Category, CollectionStats, RankedArticle, Region
from daily_news.storage import NewsDatabase


class TestNewsDatabase:
    """Tests for NewsDatabase."""

    @pytest.fixture
    def db(self, temp_db_path: Path) -> NewsDatabase:
        """Create a test database."""
        return NewsDatabase(db_path=temp_db_path)

    def create_ranked_article(
        self, title: str, score: float = 50.0, region: Region = Region.AMERICAS_US
    ) -> RankedArticle:
        """Helper to create test articles."""
        return RankedArticle(
            id=f"id_{hash(title)}",
            source_name="Test Source",
            source_region=region,
            source_category=Category.GENERAL,
            original_title=title,
            title=title,
            url=f"https://example.com/{hash(title)}",
            description="Test description",
            original_language="en",
            published_at=datetime.utcnow(),
            collected_at=datetime.utcnow(),
            significance_score=score,
            ranking_rationale="Test rationale",
        )

    def test_init_creates_tables(self, db: NewsDatabase):
        """Test that database initialization creates required tables."""
        import sqlite3

        conn = sqlite3.connect(db.db_path)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        assert "articles" in tables
        assert "digests" in tables
        assert "collection_runs" in tables
        conn.close()

    def test_save_articles(self, db: NewsDatabase):
        """Test saving articles."""
        articles = [
            self.create_ranked_article("Article 1", 80.0),
            self.create_ranked_article("Article 2", 60.0),
        ]

        saved = db.save_articles(articles)
        assert saved == 2

    def test_save_prevents_duplicates(self, db: NewsDatabase):
        """Test that duplicate URLs are not saved."""
        article = self.create_ranked_article("Test Article")

        saved1 = db.save_articles([article])
        saved2 = db.save_articles([article])  # Same article again

        assert saved1 == 1
        assert saved2 == 1  # Replace, not duplicate

    def test_get_articles_by_date(self, db: NewsDatabase):
        """Test retrieving articles by date."""
        today = date.today()
        articles = [
            self.create_ranked_article("Today Article 1", 90.0),
            self.create_ranked_article("Today Article 2", 70.0),
        ]

        db.save_articles(articles, digest_date=today)
        retrieved = db.get_articles_by_date(today)

        assert len(retrieved) == 2
        # Should be sorted by score descending
        assert retrieved[0].significance_score >= retrieved[1].significance_score

    def test_search_articles(self, db: NewsDatabase):
        """Test full-text search."""
        articles = [
            self.create_ranked_article("Earthquake strikes Japan"),
            self.create_ranked_article("Stock market reaches new high"),
            self.create_ranked_article("Weather forecast sunny"),
        ]

        db.save_articles(articles)

        results = db.search_articles("earthquake")
        assert len(results) == 1
        assert "earthquake" in results[0].title.lower()

    def test_search_with_region_filter(self, db: NewsDatabase):
        """Test search with region filter."""
        articles = [
            self.create_ranked_article("US News", region=Region.AMERICAS_US),
            self.create_ranked_article("Europe News", region=Region.EUROPE),
        ]

        db.save_articles(articles)

        results = db.search_articles("News", region="americas_us")
        assert len(results) == 1
        assert results[0].source_region == Region.AMERICAS_US

    def test_save_collection_stats(self, db: NewsDatabase):
        """Test saving collection statistics."""
        stats = CollectionStats(
            sources_attempted=60,
            sources_succeeded=55,
            articles_collected=300,
            articles_after_dedup=200,
            errors=["Error 1", "Error 2"],
            duration_seconds=120.5,
        )

        db.save_collection_stats(stats)

        # Verify it was saved
        db_stats = db.get_stats(days=1)
        assert db_stats["collection_runs"] == 1

    def test_get_stats(self, db: NewsDatabase):
        """Test getting statistics."""
        articles = [
            self.create_ranked_article("Article 1", region=Region.AMERICAS_US),
            self.create_ranked_article("Article 2", region=Region.EUROPE),
            self.create_ranked_article("Article 3", region=Region.EUROPE),
        ]

        db.save_articles(articles)
        stats = db.get_stats()

        assert stats["total_articles"] == 3
        assert stats["articles_by_region"]["europe"] == 2
        assert stats["articles_by_region"]["americas_us"] == 1
