"""Content analyzer using Claude 3.5 Sonnet."""

import json
from typing import Optional

import anthropic
import structlog

from ..config import get_settings
from ..models.schemas import (
    AnalyzedTopic,
    ContentSource,
    GoldenQuote,
    ScrapedContent,
    TopicType,
    VideoData,
    TrendData,
)
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = structlog.get_logger(__name__)


class ContentAnalyzer:
    """Analyzer that uses Claude to evaluate scraped content."""

    MODEL = "claude-sonnet-4-20250514"
    MAX_TOKENS = 8000

    def __init__(self):
        """Initialize the analyzer."""
        self.settings = get_settings()
        self.client = anthropic.Anthropic(
            api_key=self.settings.anthropic_api_key,
        )
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def analyze(self, content: ScrapedContent) -> list[AnalyzedTopic]:
        """
        Analyze scraped content and return ranked topics.

        Args:
            content: Aggregated scraped content from all sources.

        Returns:
            List of analyzed topics, sorted by potential.
        """
        self.logger.info(
            "starting_analysis",
            videos=len(content.videos),
            trends=len(content.trends),
        )

        # Prepare data for the prompt
        user_prompt = self._build_user_prompt(content)

        try:
            # Call Claude
            response = self.client.messages.create(
                model=self.MODEL,
                max_tokens=self.MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_prompt},
                ],
            )

            # Extract response text
            response_text = response.content[0].text

            # Parse JSON response
            topics = self._parse_response(response_text)

            self.logger.info(
                "analysis_complete",
                topics_found=len(topics),
                outliers=len([t for t in topics if t.typ == TopicType.OUTLIER]),
            )

            return topics

        except anthropic.APIError as e:
            self.logger.error("anthropic_api_error", error=str(e))
            raise
        except Exception as e:
            self.logger.error("analysis_failed", error=str(e))
            raise

    def _build_user_prompt(self, content: ScrapedContent) -> str:
        """Build the user prompt with scraped data."""
        # Format YouTube videos
        youtube_data = self._format_videos(content.videos)

        # Format trends by source
        wykop_data = self._format_trends(
            [t for t in content.trends if t.source == ContentSource.WYKOP]
        )
        google_data = self._format_trends(
            [t for t in content.trends if t.source == ContentSource.GOOGLE_TRENDS]
        )
        twitter_data = self._format_trends(
            [t for t in content.trends if t.source == ContentSource.TWITTER]
        )
        tiktok_data = self._format_trends(
            [t for t in content.trends if t.source == ContentSource.TIKTOK]
        )

        return USER_PROMPT_TEMPLATE.format(
            youtube_data=youtube_data or "Brak danych",
            wykop_data=wykop_data or "Brak danych",
            google_trends_data=google_data or "Brak danych",
            twitter_data=twitter_data or "Brak danych",
            tiktok_data=tiktok_data or "Brak danych",
        )

    def _format_videos(self, videos: list[VideoData]) -> str:
        """Format videos for the prompt."""
        if not videos:
            return ""

        lines = []
        for i, video in enumerate(videos[:30], 1):  # Limit to top 30
            transcript_preview = ""
            if video.transcript:
                # First 500 chars of transcript
                transcript_preview = f"\n   Transkrypcja: {video.transcript[:500]}..."

            lines.append(
                f"{i}. [{video.channel_name}] {video.title}\n"
                f"   URL: {video.url}\n"
                f"   Wyświetlenia: {video.views:,} | VPH: {video.vph:.1f}\n"
                f"   Opis: {(video.description or '')[:200]}..."
                f"{transcript_preview}"
            )

        return "\n\n".join(lines)

    def _format_trends(self, trends: list[TrendData]) -> str:
        """Format trends for the prompt."""
        if not trends:
            return ""

        lines = []
        for i, trend in enumerate(trends[:20], 1):  # Limit to top 20
            engagement_str = f" | Engagement: {trend.engagement}" if trend.engagement else ""
            url_str = f"\n   URL: {trend.url}" if trend.url else ""
            keywords_str = f"\n   Keywords: {', '.join(trend.related_keywords)}" if trend.related_keywords else ""

            lines.append(
                f"{i}. {trend.topic}{engagement_str}{url_str}{keywords_str}"
            )

        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> list[AnalyzedTopic]:
        """Parse Claude's JSON response into AnalyzedTopic objects."""
        try:
            # Try to extract JSON from response
            json_text = response_text.strip()

            # Handle markdown code blocks
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0]
            elif "```" in json_text:
                json_text = json_text.split("```")[1].split("```")[0]

            data = json.loads(json_text)
            topics_data = data.get("topics", data) if isinstance(data, dict) else data

            topics = []
            for item in topics_data:
                try:
                    # Parse golden quotes
                    zlote_cytaty = []
                    for quote_data in item.get("zlote_cytaty", []):
                        if isinstance(quote_data, str):
                            zlote_cytaty.append(GoldenQuote(quote=quote_data))
                        elif isinstance(quote_data, dict):
                            zlote_cytaty.append(GoldenQuote(
                                quote=quote_data.get("quote", ""),
                                context=quote_data.get("context"),
                                timestamp=quote_data.get("timestamp"),
                            ))

                    # Parse topic type
                    typ_str = item.get("typ", "📈 Trend")
                    if "OUTLIER" in typ_str.upper():
                        typ = TopicType.OUTLIER
                    elif "potencjał" in typ_str.lower() or "DUŻY" in typ_str.upper():
                        typ = TopicType.HIGH_POTENTIAL
                    else:
                        typ = TopicType.TREND

                    # Parse source
                    source_str = item.get("source", "youtube").lower()
                    source_map = {
                        "youtube": ContentSource.YOUTUBE,
                        "wykop": ContentSource.WYKOP,
                        "google_trends": ContentSource.GOOGLE_TRENDS,
                        "twitter": ContentSource.TWITTER,
                        "tiktok": ContentSource.TIKTOK,
                    }
                    source = source_map.get(source_str, ContentSource.YOUTUBE)

                    topic = AnalyzedTopic(
                        temat=item.get("temat", "Unknown"),
                        link=item.get("link", "https://youtube.com"),
                        typ=typ,
                        vph=item.get("vph"),
                        kat_muzyczny=item.get("kat_muzyczny", ""),
                        zlote_cytaty=zlote_cytaty,
                        uzasadnienie=item.get("uzasadnienie", ""),
                        cross_platform_score=item.get("cross_platform_score", 0.0),
                        source=source,
                    )
                    topics.append(topic)

                except Exception as e:
                    self.logger.warning(
                        "parse_topic_failed",
                        item=item,
                        error=str(e),
                    )

            return topics

        except json.JSONDecodeError as e:
            self.logger.error(
                "json_parse_failed",
                error=str(e),
                response_preview=response_text[:500],
            )
            return []
