"""Scrapers module - data ingestion from various sources."""

from .base import BaseScraper
from .youtube import YouTubeScraper
from .wykop import WykopScraper
from .google_trends import GoogleTrendsScraper
from .apify import ApifyScraper

__all__ = [
    "BaseScraper",
    "YouTubeScraper",
    "WykopScraper",
    "GoogleTrendsScraper",
    "ApifyScraper",
]
