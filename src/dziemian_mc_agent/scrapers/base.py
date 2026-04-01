"""Base scraper class with common functionality."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Generic, TypeVar

import structlog

from ..config import get_settings
from ..models.schemas import ContentSource, TrendData, VideoData

T = TypeVar("T", VideoData, TrendData)

logger = structlog.get_logger(__name__)


class BaseScraper(ABC, Generic[T]):
    """Abstract base class for all scrapers."""

    source: ContentSource

    def __init__(self):
        """Initialize scraper with settings."""
        self.settings = get_settings()
        self.lookback_hours = self.settings.lookback_hours
        self.cutoff_time = datetime.now() - timedelta(hours=self.lookback_hours)
        self.logger = structlog.get_logger(self.__class__.__name__)

    @abstractmethod
    async def scrape(self) -> list[T]:
        """
        Scrape data from the source.

        Returns:
            List of scraped items (VideoData or TrendData).
        """
        pass

    async def safe_scrape(self) -> list[T]:
        """
        Safely scrape with error handling.

        Returns:
            List of scraped items, empty list on error.
        """
        try:
            self.logger.info(
                "starting_scrape",
                source=self.source.value,
                lookback_hours=self.lookback_hours,
            )
            results = await self.scrape()
            self.logger.info(
                "scrape_complete",
                source=self.source.value,
                items_found=len(results),
            )
            return results
        except Exception as e:
            self.logger.error(
                "scrape_failed",
                source=self.source.value,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    def is_within_timeframe(self, dt: datetime) -> bool:
        """Check if datetime is within the lookback window."""
        return dt >= self.cutoff_time

    def test(self) -> str:
        """Test method for quick validation."""
        return f"{self.__class__.__name__} initialized for {self.source.value}"
