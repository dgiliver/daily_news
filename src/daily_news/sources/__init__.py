"""News source configuration and registry."""

from daily_news.sources.registry import load_sources, get_sources_by_region, get_sources_by_category

__all__ = ["load_sources", "get_sources_by_region", "get_sources_by_category"]
