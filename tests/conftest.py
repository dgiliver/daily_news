"""Pytest fixtures for tests."""

import pytest
from pathlib import Path
from datetime import datetime

from daily_news.models import (
    RawArticle,
    ProcessedArticle,
    RankedArticle,
    SourceConfig,
    Region,
    Category,
)


@pytest.fixture
def sample_source() -> SourceConfig:
    """Create a sample source configuration."""
    return SourceConfig(
        name="Test News",
        region=Region.AMERICAS_US,
        category=Category.GENERAL,
        url="https://example.com/rss",
        language="en",
        priority="high",
    )


@pytest.fixture
def sample_raw_article() -> RawArticle:
    """Create a sample raw article."""
    return RawArticle(
        source_name="Test Source",
        source_region=Region.AMERICAS_US,
        source_category=Category.GENERAL,
        title="Test Article Title",
        url="https://example.com/article/1",
        description="This is a test article description.",
        published_at=datetime.utcnow(),
        language="en",
    )


@pytest.fixture
def sample_processed_article() -> ProcessedArticle:
    """Create a sample processed article."""
    return ProcessedArticle(
        id="abc123",
        source_name="Test Source",
        source_region=Region.AMERICAS_US,
        source_category=Category.GENERAL,
        original_title="Test Article Title",
        title="Test Article Title",
        url="https://example.com/article/1",
        description="This is a test article description.",
        original_language="en",
        published_at=datetime.utcnow(),
        collected_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_ranked_article() -> RankedArticle:
    """Create a sample ranked article."""
    return RankedArticle(
        id="abc123",
        source_name="Test Source",
        source_region=Region.AMERICAS_US,
        source_category=Category.GENERAL,
        original_title="Test Article Title",
        title="Test Article Title",
        url="https://example.com/article/1",
        description="This is a test article description.",
        original_language="en",
        published_at=datetime.utcnow(),
        collected_at=datetime.utcnow(),
        significance_score=75.0,
        ranking_rationale="Important news story",
    )


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    return tmp_path / "test_news.db"
