"""Source registry for loading and managing news feeds."""

from pathlib import Path

import yaml

from daily_news.models import SourceConfig, Region, Category


def load_sources(feeds_path: Path | None = None) -> list[SourceConfig]:
    """Load all source configurations from YAML file."""
    if feeds_path is None:
        feeds_path = Path(__file__).parent / "feeds.yaml"

    with open(feeds_path) as f:
        data = yaml.safe_load(f)

    sources = []
    for source_data in data.get("sources", []):
        try:
            source = SourceConfig(
                name=source_data["name"],
                region=Region(source_data["region"]),
                category=Category(source_data["category"]),
                url=source_data["url"],
                language=source_data.get("language", "en"),
                priority=source_data.get("priority", "medium"),
                enabled=source_data.get("enabled", True),
            )
            if source.enabled:
                sources.append(source)
        except (KeyError, ValueError) as e:
            # Log error but continue loading other sources
            print(f"Warning: Failed to load source {source_data.get('name', 'unknown')}: {e}")

    return sources


def get_sources_by_region(
    sources: list[SourceConfig], region: Region
) -> list[SourceConfig]:
    """Filter sources by region."""
    return [s for s in sources if s.region == region]


def get_sources_by_category(
    sources: list[SourceConfig], category: Category
) -> list[SourceConfig]:
    """Filter sources by category."""
    return [s for s in sources if s.category == category]


def get_sources_by_priority(
    sources: list[SourceConfig], priority: str
) -> list[SourceConfig]:
    """Filter sources by priority level."""
    return [s for s in sources if s.priority == priority]


def get_sources_by_language(
    sources: list[SourceConfig], language: str
) -> list[SourceConfig]:
    """Filter sources by language."""
    return [s for s in sources if s.language == language]


def get_non_english_sources(sources: list[SourceConfig]) -> list[SourceConfig]:
    """Get all non-English sources (need translation)."""
    return [s for s in sources if s.language != "en"]
