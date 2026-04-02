"""Google Trends scraper using pytrends."""

import asyncio
from datetime import datetime
from typing import Optional

from pytrends.request import TrendReq

from .base import BaseScraper
from ..models.schemas import ContentSource, TrendData


class GoogleTrendsScraper(BaseScraper[TrendData]):
    """Scraper for Google Trends Poland."""

    source = ContentSource.GOOGLE_TRENDS

    # Keywords to track related queries for
    SEED_KEYWORDS = [
        "youtube polska",
        "youtuber",
        "drama",
        "afera",
        "famemma",
        "freak fight",
    ]

    def __init__(self):
        """Initialize Google Trends scraper."""
        super().__init__()
        self.pytrends = TrendReq(hl="pl-PL", tz=60)  # Poland timezone

    async def scrape(self) -> list[TrendData]:
        """Scrape Google Trends for Poland."""
        trends: list[TrendData] = []

        # Get related queries for seed keywords sequentially to avoid 429
        for keyword in self.SEED_KEYWORDS:
            related = await self._get_related_queries(keyword)
            trends.extend(related)
            await asyncio.sleep(2)

        # Deduplicate
        seen = set()
        unique_trends = []
        for trend in trends:
            key = trend.topic.lower()
            if key not in seen:
                seen.add(key)
                unique_trends.append(trend)

        return unique_trends

    async def _get_trending_searches(self) -> list[TrendData]:
        """Get daily trending searches in Poland."""
        trends = []

        try:
            # Run in thread to avoid blocking
            result = await asyncio.to_thread(
                self.pytrends.trending_searches,
                pn="poland",
            )

            if result is not None and not result.empty:
                for _, row in result.iterrows():
                    topic = row[0] if isinstance(row[0], str) else str(row[0])
                    trends.append(TrendData(
                        topic=topic,
                        source=self.source,
                        related_keywords=["trending"],
                        scraped_at=datetime.now(),
                    ))

        except Exception as e:
            self.logger.warning("trending_searches_failed", error=str(e))

        return trends

    async def _get_related_queries(self, keyword: str) -> list[TrendData]:
        """Get related queries for a keyword."""
        trends = []

        try:
            # Build payload
            await asyncio.to_thread(
                self.pytrends.build_payload,
                [keyword],
                cat=0,
                timeframe="now 7-d",
                geo="PL",
            )

            # Get related queries
            result = await asyncio.to_thread(
                self.pytrends.related_queries,
            )

            if result and keyword in result:
                data = result[keyword]

                # Process rising queries (more interesting)
                if "rising" in data and data["rising"] is not None:
                    for _, row in data["rising"].iterrows():
                        query = row.get("query", "")
                        if query:
                            trends.append(TrendData(
                                topic=query,
                                source=self.source,
                                related_keywords=[keyword, "rising"],
                                engagement=int(row.get("value", 0)) if row.get("value") else None,
                                scraped_at=datetime.now(),
                            ))

                # Process top queries
                if "top" in data and data["top"] is not None:
                    for _, row in data["top"].iterrows():
                        query = row.get("query", "")
                        if query:
                            trends.append(TrendData(
                                topic=query,
                                source=self.source,
                                related_keywords=[keyword, "top"],
                                engagement=int(row.get("value", 0)) if row.get("value") else None,
                                scraped_at=datetime.now(),
                            ))

        except Exception as e:
            self.logger.warning(
                "related_queries_failed",
                keyword=keyword,
                error=str(e),
            )

        return trends

    async def _get_realtime_trends(self) -> list[TrendData]:
        """Get realtime trending searches (if available)."""
        trends = []

        try:
            result = await asyncio.to_thread(
                self.pytrends.realtime_trending_searches,
                pn="PL",
            )

            if result is not None and not result.empty:
                for _, row in result.iterrows():
                    title = row.get("title", "")
                    if title:
                        trends.append(TrendData(
                            topic=title,
                            source=self.source,
                            related_keywords=["realtime"],
                            scraped_at=datetime.now(),
                        ))

        except Exception as e:
            # Realtime trends often fail, just log debug
            self.logger.debug("realtime_trends_failed", error=str(e))

        return trends
