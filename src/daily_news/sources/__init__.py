"""News source configuration and registry."""

from daily_news.sources.registry import get_sources_by_category, get_sources_by_region, load_sources

__all__ = ["get_sources_by_category", "get_sources_by_region", "load_sources"]
