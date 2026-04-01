"""Wykop.pl scraper using RSS and web scraping."""

import asyncio
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper
from ..models.schemas import ContentSource, TrendData


class WykopScraper(BaseScraper[TrendData]):
    """Scraper for Wykop.pl trending topics."""

    source = ContentSource.WYKOP

    # RSS feeds
    RSS_FEEDS = [
        "https://www.wykop.pl/rss/",
        "https://www.wykop.pl/rss/mikroblog/",
    ]

    # Hot page URL
    HOT_URL = "https://www.wykop.pl/hot/"
    MIKROBLOG_URL = "https://www.wykop.pl/mikroblog/hot/"

    def __init__(self):
        """Initialize Wykop scraper."""
        super().__init__()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
        )

    async def scrape(self) -> list[TrendData]:
        """Scrape Wykop for trending content."""
        trends: list[TrendData] = []

        # Gather from multiple sources
        tasks = [
            self._scrape_rss(),
            self._scrape_hot_page(),
            self._scrape_mikroblog(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                trends.extend(result)
            elif isinstance(result, Exception):
                self.logger.warning("wykop_task_failed", error=str(result))

        # Deduplicate by topic name
        seen = set()
        unique_trends = []
        for trend in trends:
            if trend.topic.lower() not in seen:
                seen.add(trend.topic.lower())
                unique_trends.append(trend)

        # Sort by engagement
        unique_trends.sort(
            key=lambda t: t.engagement or 0,
            reverse=True,
        )

        return unique_trends

    async def _scrape_rss(self) -> list[TrendData]:
        """Scrape Wykop RSS feeds."""
        trends = []

        for feed_url in self.RSS_FEEDS:
            try:
                response = await self.client.get(feed_url)
                response.raise_for_status()

                feed = feedparser.parse(response.text)

                for entry in feed.entries[:20]:
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
                self.logger.warning(
                    "rss_scrape_failed",
                    feed_url=feed_url,
                    error=str(e),
                )

        return trends

    async def _scrape_hot_page(self) -> list[TrendData]:
        """Scrape Wykop hot page."""
        trends = []

        try:
            response = await self.client.get(self.HOT_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Find wykop entries (adjust selectors based on current layout)
            entries = soup.select("article.link, div.link-block, section.entry")

            for entry in entries[:30]:
                trend = self._parse_wykop_entry(entry)
                if trend:
                    trends.append(trend)

        except Exception as e:
            self.logger.warning("hot_page_scrape_failed", error=str(e))

        return trends

    async def _scrape_mikroblog(self) -> list[TrendData]:
        """Scrape Wykop mikroblog hot entries."""
        trends = []

        try:
            response = await self.client.get(self.MIKROBLOG_URL)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            # Find mikroblog entries
            entries = soup.select("div.entry, article.entry")

            for entry in entries[:30]:
                trend = self._parse_mikroblog_entry(entry)
                if trend:
                    trends.append(trend)

        except Exception as e:
            self.logger.warning("mikroblog_scrape_failed", error=str(e))

        return trends

    def _parse_wykop_entry(self, entry) -> Optional[TrendData]:
        """Parse a Wykop link entry."""
        try:
            # Try to find title
            title_elem = entry.select_one("h2 a, .title a, a.link-title")
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            url = title_elem.get("href")
            if url and not url.startswith("http"):
                url = urljoin("https://www.wykop.pl", url)

            # Try to find vote count
            votes_elem = entry.select_one(".diggbox, .vote-count, .votes")
            engagement = None
            if votes_elem:
                try:
                    engagement = int(votes_elem.get_text(strip=True).replace("+", ""))
                except (ValueError, TypeError):
                    pass

            return TrendData(
                topic=title,
                url=url,
                source=self.source,
                engagement=engagement,
                scraped_at=datetime.now(),
            )

        except Exception as e:
            self.logger.debug("parse_entry_failed", error=str(e))
            return None

    def _parse_mikroblog_entry(self, entry) -> Optional[TrendData]:
        """Parse a Wykop mikroblog entry."""
        try:
            # Find entry content
            content_elem = entry.select_one(".text, .content, p")
            if not content_elem:
                return None

            content = content_elem.get_text(strip=True)
            if len(content) < 20:
                return None

            # Truncate for topic
            topic = content[:150] + "..." if len(content) > 150 else content

            # Try to find permalink
            link_elem = entry.select_one("a.permalink, time a, .date a")
            url = None
            if link_elem:
                url = link_elem.get("href")
                if url and not url.startswith("http"):
                    url = urljoin("https://www.wykop.pl", url)

            # Try to find vote count
            votes_elem = entry.select_one(".vote-count, .votes, .uv")
            engagement = None
            if votes_elem:
                try:
                    engagement = int(votes_elem.get_text(strip=True).replace("+", ""))
                except (ValueError, TypeError):
                    pass

            return TrendData(
                topic=topic,
                url=url,
                source=self.source,
                engagement=engagement,
                scraped_at=datetime.now(),
            )

        except Exception as e:
            self.logger.debug("parse_mikroblog_failed", error=str(e))
            return None

    async def __aenter__(self):
        """Async context manager enter."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close client."""
        await self.client.aclose()
