"""Base collector interface."""

from abc import ABC, abstractmethod

from daily_news.models import RawArticle, SourceConfig


class BaseCollector(ABC):
    """Abstract base class for news collectors."""

    @abstractmethod
    async def collect(self, source: SourceConfig) -> list[RawArticle]:
        """Collect articles from a single source.

        Args:
            source: Source configuration

        Returns:
            List of raw articles collected from the source
        """
        ...

    @abstractmethod
    async def health_check(self, source: SourceConfig) -> bool:
        """Check if source is accessible.

        Args:
            source: Source configuration

        Returns:
            True if source is reachable, False otherwise
        """
        ...
