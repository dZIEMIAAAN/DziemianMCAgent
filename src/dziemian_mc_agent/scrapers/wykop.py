"""Wykop.pl scraper using RSS feeds."""

import asyncio
from datetime import datetime

import feedparser
import httpx

from .base import BaseScraper
from ..models.schemas import ContentSource, TrendData


class WykopScraper(BaseScraper[TrendData]):
    """Scraper for Wykop.pl trending topics via RSS."""

    source = ContentSource.WYKOP

    RSS_FEEDS = [
        "https://wykop.pl/rss/",
    ]

    def __init__(self):
        """Initialize Wykop scraper."""
        super().__init__()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )

    async def scrape(self) -> list[TrendData]:
        """Scrape Wykop RSS feeds for trending content."""
        trends = await self._scrape_rss()

        # Deduplicate by topic
        seen = set()
        unique = []
        for t in trends:
            if t.topic.lower() not in seen:
                seen.add(t.topic.lower())
                unique.append(t)

        unique.sort(key=lambda t: t.engagement or 0, reverse=True)
        return unique

    async def _scrape_rss(self) -> list[TrendData]:
        """Scrape Wykop RSS feeds."""
        trends = []

        for feed_url in self.RSS_FEEDS:
            try:
                response = await self.client.get(feed_url)
                response.raise_for_status()

                feed = feedparser.parse(response.text)

                for entry in feed.entries[:50]:
                    published = entry.get("published_parsed")
                    if published:
                        dt = datetime(*published[:6])
                        if not self.is_within_timeframe(dt):
                            continue

                    trends.append(TrendData(
                        topic=entry.get("title", "Unknown"),
                        url=entry.get("link"),
                        source=self.source,
                        scraped_at=datetime.now(),
                    ))

            except Exception as e:
                self.logger.warning("rss_scrape_failed", feed_url=feed_url, error=str(e))

        return trends

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
