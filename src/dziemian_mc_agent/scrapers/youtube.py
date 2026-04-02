"""YouTube scraper using YouTube Data API v3."""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from .base import BaseScraper
from ..models.schemas import ContentSource, VideoData


class YouTubeScraper(BaseScraper[VideoData]):
    """Scraper for YouTube videos using YouTube Data API v3."""

    source = ContentSource.YOUTUBE
    API_BASE = "https://www.googleapis.com/youtube/v3"

    def __init__(self):
        """Initialize YouTube scraper."""
        super().__init__()
        self.api_key = self.settings.youtube_api_key
        self.keywords = self.settings.youtube_keywords
        self.min_vph = self.settings.min_vph_threshold
        self.enabled = bool(self.api_key)

        if not self.enabled:
            self.logger.info("youtube_api_disabled", reason="No API key configured")

        self.client = httpx.AsyncClient(timeout=30.0)

    async def scrape(self) -> list[VideoData]:
        """Scrape YouTube for recent videos."""
        if not self.enabled:
            self.logger.info("youtube_skipped", reason="Not configured")
            return []

        videos: list[VideoData] = []

        # Trending Poland
        trending = await self._scrape_trending()
        videos.extend(trending)

        # Keyword searches (concurrent)
        keyword_tasks = [self._search_keyword(kw) for kw in self.keywords]
        keyword_results = await asyncio.gather(*keyword_tasks, return_exceptions=True)
        for result in keyword_results:
            if isinstance(result, list):
                videos.extend(result)

        # Deduplicate
        seen = set()
        unique = []
        for v in videos:
            if v.video_id not in seen:
                seen.add(v.video_id)
                unique.append(v)

        # Filter by VPH and sort
        filtered = [v for v in unique if v.vph >= self.min_vph]
        filtered.sort(key=lambda v: v.vph, reverse=True)

        self.logger.info(
            "youtube_scrape_done",
            total=len(unique),
            after_vph_filter=len(filtered),
        )

        return filtered

    async def _scrape_trending(self) -> list[VideoData]:
        """Fetch YouTube trending videos for Poland."""
        self.logger.info("fetching_trending_pl")
        try:
            resp = await self.client.get(
                f"{self.API_BASE}/videos",
                params={
                    "part": "snippet,statistics",
                    "chart": "mostPopular",
                    "regionCode": "PL",
                    "maxResults": 50,
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            return self._parse_items(items)
        except Exception as e:
            self.logger.warning("trending_failed", error=str(e))
            return []

    async def _search_keyword(self, keyword: str) -> list[VideoData]:
        """Search YouTube for recent videos matching keyword."""
        self.logger.info("searching_keyword", keyword=keyword)
        try:
            published_after = (
                datetime.now(timezone.utc) - timedelta(hours=self.settings.lookback_hours)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Step 1: search for video IDs
            resp = await self.client.get(
                f"{self.API_BASE}/search",
                params={
                    "part": "id",
                    "q": keyword,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": published_after,
                    "regionCode": "PL",
                    "relevanceLanguage": "pl",
                    "maxResults": 25,
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            video_ids = [
                item["id"]["videoId"]
                for item in resp.json().get("items", [])
                if item.get("id", {}).get("videoId")
            ]

            if not video_ids:
                return []

            # Step 2: fetch full stats for those IDs
            return await self._fetch_video_details(video_ids)

        except Exception as e:
            self.logger.warning("keyword_search_failed", keyword=keyword, error=str(e))
            return []

    async def _fetch_video_details(self, video_ids: list[str]) -> list[VideoData]:
        """Fetch snippet + statistics for a list of video IDs."""
        try:
            resp = await self.client.get(
                f"{self.API_BASE}/videos",
                params={
                    "part": "snippet,statistics",
                    "id": ",".join(video_ids),
                    "key": self.api_key,
                },
            )
            resp.raise_for_status()
            return self._parse_items(resp.json().get("items", []))
        except Exception as e:
            self.logger.warning("video_details_failed", error=str(e))
            return []

    def _parse_items(self, items: list[dict]) -> list[VideoData]:
        """Parse API response items into VideoData objects."""
        videos = []
        for item in items:
            video = self._parse_item(item)
            if video and self.is_within_timeframe(video.upload_date.replace(tzinfo=None)):
                videos.append(video)
        return videos

    def _parse_item(self, item: dict) -> Optional[VideoData]:
        """Parse a single API item into VideoData."""
        try:
            video_id = item.get("id")
            if not video_id:
                return None

            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})

            published_at = snippet.get("publishedAt")
            if not published_at:
                return None

            upload_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            hours_since = max(
                (datetime.now(timezone.utc) - upload_date).total_seconds() / 3600,
                0.1,
            )

            views = int(stats.get("viewCount", 0) or 0)
            vph = views / hours_since

            return VideoData(
                video_id=video_id,
                title=snippet.get("title", "Unknown"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_name=snippet.get("channelTitle") or "Unknown",
                channel_url=f"https://www.youtube.com/channel/{snippet.get('channelId', '')}",
                views=views,
                upload_date=upload_date.replace(tzinfo=None),
                hours_since_upload=hours_since,
                vph=vph,
                description=snippet.get("description"),
            )

        except Exception as e:
            self.logger.warning("parse_item_failed", error=str(e))
            return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
