"""Pydantic schemas for data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class ContentSource(str, Enum):
    """Source of scraped content."""

    YOUTUBE = "youtube"
    WYKOP = "wykop"
    GOOGLE_TRENDS = "google_trends"
    TWITTER = "twitter"
    TIKTOK = "tiktok"


class TopicType(str, Enum):
    """Classification of topic potential."""

    OUTLIER = "🔥 TOTALNY OUTLIER"
    HIGH_POTENTIAL = "💎 Duży potencjał"
    TREND = "📈 Trend"


class VideoData(BaseModel):
    """Data model for YouTube video."""

    video_id: str
    title: str
    url: HttpUrl
    channel_name: str
    channel_url: Optional[HttpUrl] = None
    views: int
    upload_date: datetime
    hours_since_upload: float
    vph: float = Field(description="Views Per Hour")
    transcript: Optional[str] = None
    description: Optional[str] = None
    source: ContentSource = ContentSource.YOUTUBE

    def model_post_init(self, __context) -> None:
        """Calculate VPH if not set."""
        if self.hours_since_upload > 0:
            self.vph = self.views / self.hours_since_upload


class TrendData(BaseModel):
    """Data model for trending topic from various sources."""

    topic: str
    url: Optional[HttpUrl] = None
    source: ContentSource
    engagement: Optional[int] = Field(
        default=None,
        description="Engagement metric (wykops, retweets, etc.)",
    )
    related_keywords: list[str] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)


class ScrapedContent(BaseModel):
    """Aggregated scraped content from all sources."""

    videos: list[VideoData] = Field(default_factory=list)
    trends: list[TrendData] = Field(default_factory=list)
    scraped_at: datetime = Field(default_factory=datetime.now)

    @property
    def total_items(self) -> int:
        """Total number of scraped items."""
        return len(self.videos) + len(self.trends)


class GoldenQuote(BaseModel):
    """A 'golden quote' extracted from content."""

    quote: str
    timestamp: Optional[str] = None
    context: Optional[str] = None


class AnalyzedTopic(BaseModel):
    """Analyzed topic with AI-generated insights."""

    temat: str = Field(description="Topic title")
    link: HttpUrl = Field(description="Link to source")
    typ: TopicType = Field(description="Topic classification")
    vph: Optional[float] = Field(default=None, description="Views per hour if from YouTube")
    kat_muzyczny: str = Field(description="Suggested musical angle for Dziemian")
    zlote_cytaty: list[GoldenQuote] = Field(
        default_factory=list,
        description="Golden quotes for hooks/choruses",
    )
    uzasadnienie: str = Field(description="Reasoning for the classification")
    cross_platform_score: float = Field(
        default=0.0,
        description="Score based on cross-platform presence",
    )
    source: ContentSource
    raw_data: Optional[dict] = Field(
        default=None,
        description="Original scraped data",
    )


class AgentResult(BaseModel):
    """Final result from the agent run."""

    run_id: str
    run_at: datetime = Field(default_factory=datetime.now)
    topics: list[AnalyzedTopic] = Field(default_factory=list)
    outliers: list[AnalyzedTopic] = Field(default_factory=list)
    total_scraped: int = 0
    total_analyzed: int = 0
    errors: list[str] = Field(default_factory=list)

    @property
    def top_outliers(self) -> list[AnalyzedTopic]:
        """Get topics classified as TOTALNY OUTLIER."""
        return [t for t in self.topics if t.typ == TopicType.OUTLIER]

    def model_post_init(self, __context) -> None:
        """Populate outliers list."""
        self.outliers = self.top_outliers
