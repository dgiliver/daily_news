"""Tests for data models."""

import pytest

from daily_news.models import (
    Category,
    ProcessedArticle,
    RankedArticle,
    RawArticle,
    Region,
)


class TestRawArticle:
    """Tests for RawArticle model."""

    def test_create_article(self):
        """Test creating a raw article."""
        article = RawArticle(
            source_name="Test",
            source_region=Region.AMERICAS_US,
            source_category=Category.GENERAL,
            title="Test Title",
            url="https://example.com/test",
        )
        assert article.title == "Test Title"
        assert article.language == "en"  # default

    def test_generate_id(self, sample_raw_article: RawArticle):
        """Test ID generation from URL."""
        id1 = sample_raw_article.generate_id()
        id2 = sample_raw_article.generate_id()
        assert id1 == id2
        assert len(id1) == 16

    def test_clean_text(self):
        """Test text cleaning in validator."""
        article = RawArticle(
            source_name="Test",
            source_region=Region.AMERICAS_US,
            source_category=Category.GENERAL,
            title="  Test Title  ",
            url="https://example.com/test",
            description="  Some description  ",
        )
        assert article.title == "Test Title"
        assert article.description == "Some description"


class TestProcessedArticle:
    """Tests for ProcessedArticle model."""

    def test_from_raw(self, sample_raw_article: RawArticle):
        """Test creating processed article from raw."""
        processed = ProcessedArticle.from_raw(sample_raw_article)

        assert processed.original_title == sample_raw_article.title
        assert processed.title == sample_raw_article.title
        assert processed.source_name == sample_raw_article.source_name

    def test_from_raw_with_translation(self, sample_raw_article: RawArticle):
        """Test creating processed article with translation."""
        processed = ProcessedArticle.from_raw(
            sample_raw_article,
            translated_title="Translated Title",
            translated_description="Translated description",
        )

        assert processed.original_title == sample_raw_article.title
        assert processed.title == "Translated Title"
        assert processed.description == "Translated description"


class TestRankedArticle:
    """Tests for RankedArticle model."""

    def test_score_bounds(self, sample_processed_article: ProcessedArticle):
        """Test that score is bounded correctly."""
        ranked = RankedArticle(
            **sample_processed_article.model_dump(),
            significance_score=85.0,
            ranking_rationale="High importance",
        )
        assert ranked.significance_score == 85.0

    def test_invalid_score_raises(self, sample_processed_article: ProcessedArticle):
        """Test that invalid score raises validation error."""
        with pytest.raises(ValueError):
            RankedArticle(
                **sample_processed_article.model_dump(),
                significance_score=150.0,  # Invalid - over 100
                ranking_rationale="Test",
            )
