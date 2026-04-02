"""Apify scraper for X (Twitter) and TikTok trends."""

import asyncio
from datetime import datetime
from typing import Optional

import httpx

from .base import BaseScraper
from ..models.schemas import ContentSource, TrendData


class ApifyScraper(BaseScraper[TrendData]):
    """Scraper using Apify actors for X and TikTok."""

    source = ContentSource.TWITTER  # Primary source, will be set per-item

    # Apify actor IDs (these are example public actors)
    TWITTER_ACTOR = "apidojo/twitter-scraper-lite"
    TIKTOK_ACTOR = "clockworks/tiktok-scraper"

    API_BASE = "https://api.apify.com/v2"

    def __init__(self):
        """Initialize Apify scraper."""
        super().__init__()
        self.api_token = self.settings.apify_api_token
        self.enabled = bool(self.api_token)

        if not self.enabled:
            self.logger.info("apify_disabled", reason="No API token configured")

        self.client = httpx.AsyncClient(
            timeout=120.0,
            headers={
                "Authorization": f"Bearer {self.api_token}" if self.api_token else "",
            },
        )

    async def scrape(self) -> list[TrendData]:
        """Scrape X and TikTok via Apify."""
        if not self.enabled:
            self.logger.info("apify_skipped", reason="Not configured")
            return []

        trends: list[TrendData] = []

        # Run both scrapers
        tasks = [
            self._scrape_twitter(),
            self._scrape_tiktok(),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                trends.extend(result)
            elif isinstance(result, Exception):
                self.logger.warning("apify_task_failed", error=str(result))

        return trends

    async def _scrape_twitter(self) -> list[TrendData]:
        """Scrape trending topics from X (Twitter) Poland."""
        trends = []

        try:
            # Run the Twitter trends actor
            run_input = {
                "searchTerms": [
                    "#polska",
                    "#youtube",
                    "#drama",
                    "#famemma",
                ],
                "maxTweets": 50,
                "language": "pl",
            }

            result = await self._run_actor(self.TWITTER_ACTOR, run_input)

            if result:
                for item in result:
                    text = item.get("full_text", item.get("text", ""))
                    if not text:
                        continue

                    # Extract topic from tweet
                    topic = text[:150] + "..." if len(text) > 150 else text

                    trends.append(TrendData(
                        topic=topic,
                        url=item.get("url"),
                        source=ContentSource.TWITTER,
                        engagement=item.get("retweet_count", 0) + item.get("favorite_count", 0),
                        scraped_at=datetime.now(),
                    ))

        except Exception as e:
            self.logger.warning("twitter_scrape_failed", error=str(e))

        return trends

    async def _scrape_tiktok(self) -> list[TrendData]:
        """Scrape trending content from TikTok Poland."""
        trends = []

        try:
            # Run the TikTok trends actor
            run_input = {
                "hashtags": [
                    "polska",
                    "polskitiktok",
                    "drama",
                    "youtube",
                ],
                "resultsPerPage": 30,
            }

            result = await self._run_actor(self.TIKTOK_ACTOR, run_input)

            if result:
                for item in result:
                    desc = item.get("desc", item.get("description", ""))
                    if not desc:
                        continue

                    topic = desc[:150] + "..." if len(desc) > 150 else desc

                    trends.append(TrendData(
                        topic=topic,
                        url=item.get("webVideoUrl", item.get("url")),
                        source=ContentSource.TIKTOK,
                        engagement=item.get("diggCount", 0) + item.get("shareCount", 0),
                        scraped_at=datetime.now(),
                    ))

        except Exception as e:
            self.logger.warning("tiktok_scrape_failed", error=str(e))

        return trends

    async def _run_actor(self, actor_id: str, run_input: dict) -> Optional[list]:
        """Run an Apify actor and wait for results."""
        try:
            # Start actor run
            start_url = f"{self.API_BASE}/acts/{actor_id}/runs"
            response = await self.client.post(
                start_url,
                json=run_input,
                params={"token": self.api_token},
            )
            response.raise_for_status()

            run_data = response.json()
            run_id = run_data["data"]["id"]

            # Poll for completion
            status_url = f"{self.API_BASE}/actor-runs/{run_id}"
            for _ in range(30):  # Max 5 minutes
                await asyncio.sleep(10)

                status_response = await self.client.get(
                    status_url,
                    params={"token": self.api_token},
                )
                status_response.raise_for_status()

                status_data = status_response.json()
                status = status_data["data"]["status"]

                if status == "SUCCEEDED":
                    # Get results
                    dataset_id = status_data["data"]["defaultDatasetId"]
                    items_url = f"{self.API_BASE}/datasets/{dataset_id}/items"

                    items_response = await self.client.get(
                        items_url,
                        params={"token": self.api_token},
                    )
                    items_response.raise_for_status()

                    return items_response.json()

                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    self.logger.warning(
                        "actor_run_failed",
                        actor_id=actor_id,
                        status=status,
                    )
                    return None

            self.logger.warning("actor_run_timeout", actor_id=actor_id)
            return None

        except Exception as e:
            self.logger.error("actor_run_error", actor_id=actor_id, error=str(e))
            return None

    async def __aenter__(self):
        """Async context manager enter."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close client."""
        await self.client.aclose()
