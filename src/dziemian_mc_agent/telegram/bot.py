"""Telegram bot for sending notifications."""

from typing import Optional

import httpx
import structlog

from ..config import get_settings
from ..models.schemas import AnalyzedTopic, TopicType


logger = structlog.get_logger(__name__)


class TelegramBot:
    """Bot for sending Telegram notifications."""

    API_BASE = "https://api.telegram.org/bot"

    def __init__(self):
        """Initialize Telegram bot."""
        self.settings = get_settings()
        self.enabled = bool(
            self.settings.telegram_bot_token and self.settings.telegram_chat_id
        )

        self.token = self.settings.telegram_bot_token
        self.chat_id = self.settings.telegram_chat_id
        self.logger = structlog.get_logger(self.__class__.__name__)

        if not self.enabled:
            self.logger.info("telegram_disabled", reason="Missing token or chat ID")

    async def send_report(self, topics: list[AnalyzedTopic]) -> bool:
        """
        Send analysis report to Telegram.

        Args:
            topics: List of analyzed topics.

        Returns:
            True if message was sent successfully.
        """
        if not self.enabled:
            self.logger.info("telegram_skipped", reason="Not configured")
            return False

        message = self._build_message(topics)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.API_BASE}{self.token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    self.logger.info("telegram_message_sent")
                    return True
                else:
                    self.logger.error(
                        "telegram_send_failed",
                        status=response.status_code,
                        response=response.text[:500],
                    )
                    return False

        except Exception as e:
            self.logger.error("telegram_error", error=str(e))
            return False

    def _build_message(self, topics: list[AnalyzedTopic]) -> str:
        """Build the Telegram message."""
        # Get outliers
        outliers = [t for t in topics if t.typ == TopicType.OUTLIER][:3]

        # Build message
        lines = [
            "🚀 *SZEFIE, MAMY NOWE BANGERY!*",
            "",
            "🔥 *TOP OUTLIERS:*",
            "",
        ]

        for i, topic in enumerate(outliers, 1):
            # Title with link
            lines.append(f"*{i}. [{self._escape_markdown(topic.temat[:50])}]({topic.link})*")

            # Musical angle
            lines.append(f"🎵 _{self._escape_markdown(topic.kat_muzyczny[:100])}_")

            # Best quote
            if topic.zlote_cytaty:
                best_quote = topic.zlote_cytaty[0].quote
                lines.append(f'💬 "{self._escape_markdown(best_quote[:80])}"')

            # VPH if available
            if topic.vph:
                lines.append(f"📊 VPH: {topic.vph:,.0f}")

            lines.append("")

        # Summary
        total_high_potential = len([t for t in topics if t.typ == TopicType.HIGH_POTENTIAL])
        total_trends = len([t for t in topics if t.typ == TopicType.TREND])

        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📊 *Podsumowanie:*",
            f"🔥 Outliery: {len(outliers)}",
            f"💎 Duży potencjał: {total_high_potential}",
            f"📈 Trendy: {total_trends}",
            "",
        ])

        # Notion link
        if self.settings.notion_database_url:
            lines.append(f"📝 [Pełna lista w Notion]({self.settings.notion_database_url})")
        else:
            lines.append("📝 _Sprawdź pełną listę w Notion_")

        lines.extend([
            "",
            "🤖 _Agent Dziemiana_",
        ])

        return "\n".join(lines)

    def _escape_markdown(self, text: str) -> str:
        """Escape Markdown special characters."""
        # Characters to escape in Markdown
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    async def send_error_notification(self, error: str) -> bool:
        """Send error notification to Telegram."""
        if not self.enabled:
            return False

        message = f"⚠️ *Agent Error*\n\n```\n{error[:500]}\n```"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.API_BASE}{self.token}/sendMessage",
                    json={
                        "chat_id": self.chat_id,
                        "text": message,
                        "parse_mode": "Markdown",
                    },
                    timeout=30.0,
                )
                return response.status_code == 200

        except Exception as e:
            self.logger.error("telegram_error_notification_failed", error=str(e))
            return False

    async def test_connection(self) -> bool:
        """Test connection to Telegram."""
        if not self.enabled:
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.API_BASE}{self.token}/getMe",
                    timeout=10.0,
                )
                return response.status_code == 200

        except Exception as e:
            self.logger.error("telegram_connection_test_failed", error=str(e))
            return False
