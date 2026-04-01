"""Configuration module using Pydantic Settings."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Anthropic (Claude)
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude",
    )

    # Notion
    notion_api_key: str = Field(
        default="",
        description="Notion integration API key",
    )
    notion_database_id: str = Field(
        default="",
        description="Notion database ID for storing results",
    )

    # Telegram
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token from BotFather",
    )
    telegram_chat_id: str = Field(
        default="",
        description="Telegram chat ID for notifications",
    )

    # Apify (optional)
    apify_api_token: Optional[str] = Field(
        default=None,
        description="Apify API token for X/TikTok scraping",
    )

    # Application settings
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    dry_run: bool = Field(
        default=False,
        description="Run in dry mode (no Notion/Telegram output)",
    )
    lookback_hours: int = Field(
        default=48,
        description="How many hours back to search for content",
    )

    # YouTube settings
    youtube_channels: list[str] = Field(
        default=[
            "KanalZero",
            "Ksiazulo",
            "Rembol",
            "FameMMA",
            "CLOUTMMA",
            "Matura2Bzdura",
            "StuurTV",
            "KrzysztofGonciarz",
            "LekkoStronniczy",
            "Pyta",
            "Imponderabilia",
            "20m2Lodzka",
        ],
        description="YouTube channel handles to monitor",
    )
    youtube_keywords: list[str] = Field(
        default=[
            "drama polska youtube",
            "afera youtube",
            "commentary pl",
            "zgrzyt",
            "beef youtube polska",
            "patologia youtube",
            "cringe polska",
            "famemma",
            "cloutmma",
        ],
        description="Keywords to search on YouTube",
    )
    min_vph_threshold: float = Field(
        default=100.0,
        description="Minimum views per hour to consider a video",
    )

    # Notion database URL (for linking)
    notion_database_url: str = Field(
        default="",
        description="Full URL to Notion database (for Telegram links)",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
