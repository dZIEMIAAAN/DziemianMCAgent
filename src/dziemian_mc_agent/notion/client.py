"""Notion database client for storing analyzed topics."""

from typing import Optional

import structlog
from notion_client import Client
from notion_client.errors import APIResponseError

from ..config import get_settings
from ..models.schemas import AnalyzedTopic, TopicType


logger = structlog.get_logger(__name__)


class NotionClient:
    """Client for interacting with Notion database."""

    def __init__(self):
        """Initialize Notion client."""
        self.settings = get_settings()
        self.enabled = bool(
            self.settings.notion_api_key and self.settings.notion_database_id
        )

        if self.enabled:
            self.client = Client(auth=self.settings.notion_api_key)
            self.database_id = self.settings.notion_database_id
        else:
            self.client = None
            self.database_id = None

        self.logger = structlog.get_logger(self.__class__.__name__)

        if not self.enabled:
            self.logger.info("notion_disabled", reason="Missing API key or database ID")

    async def add_topics(self, topics: list[AnalyzedTopic]) -> list[str]:
        """
        Add analyzed topics to Notion database.

        Args:
            topics: List of analyzed topics to add.

        Returns:
            List of created page IDs.
        """
        if not self.enabled:
            self.logger.info("notion_skipped", reason="Not configured")
            return []

        page_ids = []

        for topic in topics:
            try:
                page_id = await self._create_page(topic)
                if page_id:
                    page_ids.append(page_id)
                    self.logger.info(
                        "notion_page_created",
                        topic=topic.temat[:50],
                        page_id=page_id,
                    )
            except Exception as e:
                self.logger.error(
                    "notion_create_failed",
                    topic=topic.temat[:50],
                    error=str(e),
                )

        return page_ids

    async def _create_page(self, topic: AnalyzedTopic) -> Optional[str]:
        """Create a single page in Notion database."""
        try:
            # Build properties
            properties = self._build_properties(topic)

            # Create page
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
            )

            return response.get("id")

        except APIResponseError as e:
            self.logger.error(
                "notion_api_error",
                status=e.status,
                code=e.code,
                message=str(e),
            )
            return None

    def _build_properties(self, topic: AnalyzedTopic) -> dict:
        """Build Notion properties from analyzed topic."""
        # Format golden quotes as text
        quotes_text = "\n".join([
            f'"{q.quote}"' + (f" ({q.context})" if q.context else "")
            for q in topic.zlote_cytaty
        ])

        # Map topic type to Notion select
        typ_map = {
            TopicType.OUTLIER: "🔥 TOTALNY OUTLIER",
            TopicType.HIGH_POTENTIAL: "💎 Duży potencjał",
            TopicType.TREND: "📈 Trend",
        }

        properties = {
            # Title property (usually named "Name" or "Temat")
            "Temat": {
                "title": [
                    {
                        "text": {
                            "content": topic.temat[:100],  # Notion title limit
                        }
                    }
                ]
            },
            # URL property
            "Link": {
                "url": str(topic.link),
            },
            # Select property - Status
            "Status": {
                "select": {
                    "name": "Do przejrzenia",
                }
            },
            # Select property - Type
            "Typ": {
                "select": {
                    "name": typ_map.get(topic.typ, "📈 Trend"),
                }
            },
            # Rich text - Musical angle
            "Kąt Muzyczny": {
                "rich_text": [
                    {
                        "text": {
                            "content": topic.kat_muzyczny[:2000],  # Notion text limit
                        }
                    }
                ]
            },
            # Rich text - Golden quotes
            "Złote Cytaty": {
                "rich_text": [
                    {
                        "text": {
                            "content": quotes_text[:2000] if quotes_text else "Brak",
                        }
                    }
                ]
            },
            # Rich text - Reasoning
            "Uzasadnienie": {
                "rich_text": [
                    {
                        "text": {
                            "content": topic.uzasadnienie[:2000],
                        }
                    }
                ]
            },
        }

        # Add VPH if available
        if topic.vph is not None:
            properties["VPH"] = {
                "number": round(topic.vph, 1),
            }

        # Add cross-platform score
        properties["Cross-Platform Score"] = {
            "number": round(topic.cross_platform_score * 100, 1),
        }

        return properties

    async def clear_old_entries(self, days: int = 7) -> int:
        """
        Archive old entries from the database.

        Args:
            days: Number of days after which to archive entries.

        Returns:
            Number of archived entries.
        """
        if not self.enabled:
            return 0

        # This would require querying and archiving pages
        # Keeping it simple for now - can be implemented later
        self.logger.info("clear_old_entries_not_implemented")
        return 0

    def test_connection(self) -> bool:
        """Test connection to Notion."""
        if not self.enabled:
            return False

        try:
            # Try to retrieve database
            self.client.databases.retrieve(self.database_id)
            return True
        except Exception as e:
            self.logger.error("notion_connection_test_failed", error=str(e))
            return False
