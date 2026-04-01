"""Main orchestrator for DziemianMCAgent."""

import argparse
import asyncio
import sys
import uuid
from datetime import datetime

import structlog

from .config import get_settings
from .models.schemas import AgentResult, ScrapedContent
from .scrapers import (
    YouTubeScraper,
    WykopScraper,
    GoogleTrendsScraper,
    ApifyScraper,
)
from .ai import ContentAnalyzer
from .notion import NotionClient
from .telegram import TelegramBot


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


async def scrape_all_sources() -> ScrapedContent:
    """Scrape data from all configured sources."""
    logger.info("starting_scrape_phase")

    content = ScrapedContent()

    # Initialize scrapers
    youtube_scraper = YouTubeScraper()
    wykop_scraper = WykopScraper()
    trends_scraper = GoogleTrendsScraper()
    apify_scraper = ApifyScraper()

    # Run all scrapers concurrently
    tasks = [
        youtube_scraper.safe_scrape(),
        wykop_scraper.safe_scrape(),
        trends_scraper.safe_scrape(),
        apify_scraper.safe_scrape(),
    ]

    results = await asyncio.gather(*tasks)

    # Collect results
    content.videos = results[0]  # YouTube videos

    # Collect all trends
    for result in results[1:]:
        content.trends.extend(result)

    logger.info(
        "scrape_phase_complete",
        videos=len(content.videos),
        trends=len(content.trends),
        total=content.total_items,
    )

    return content


async def analyze_content(content: ScrapedContent) -> AgentResult:
    """Analyze scraped content using Claude."""
    logger.info("starting_analysis_phase")

    run_id = str(uuid.uuid4())[:8]
    result = AgentResult(
        run_id=run_id,
        total_scraped=content.total_items,
    )

    if content.total_items == 0:
        logger.warning("no_content_to_analyze")
        result.errors.append("No content scraped from any source")
        return result

    try:
        analyzer = ContentAnalyzer()
        topics = await analyzer.analyze(content)

        result.topics = topics
        result.total_analyzed = len(topics)

        logger.info(
            "analysis_phase_complete",
            topics=len(topics),
            outliers=len(result.outliers),
        )

    except Exception as e:
        logger.error("analysis_failed", error=str(e))
        result.errors.append(f"Analysis failed: {str(e)}")

    return result


async def save_to_notion(result: AgentResult) -> list[str]:
    """Save analyzed topics to Notion database."""
    logger.info("starting_notion_phase")

    notion = NotionClient()
    page_ids = await notion.add_topics(result.topics)

    logger.info("notion_phase_complete", pages_created=len(page_ids))

    return page_ids


async def send_notification(result: AgentResult) -> bool:
    """Send Telegram notification with results."""
    logger.info("starting_notification_phase")

    bot = TelegramBot()
    success = await bot.send_report(result.topics)

    if success:
        logger.info("notification_sent")
    else:
        logger.warning("notification_failed")

    return success


async def run_agent(dry_run: bool = False) -> AgentResult:
    """
    Run the complete agent pipeline.

    Args:
        dry_run: If True, skip Notion and Telegram output.

    Returns:
        AgentResult with analyzed topics.
    """
    settings = get_settings()
    dry_run = dry_run or settings.dry_run

    logger.info(
        "agent_starting",
        dry_run=dry_run,
        lookback_hours=settings.lookback_hours,
    )

    start_time = datetime.now()

    try:
        # Phase 1: Scrape all sources
        content = await scrape_all_sources()

        # Phase 2: Analyze with Claude
        result = await analyze_content(content)

        # Phase 3: Save to Notion (unless dry run)
        if not dry_run and result.topics:
            await save_to_notion(result)

        # Phase 4: Send Telegram notification (unless dry run)
        if not dry_run and result.topics:
            await send_notification(result)

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            "agent_complete",
            run_id=result.run_id,
            duration_seconds=duration,
            topics=len(result.topics),
            outliers=len(result.outliers),
            errors=len(result.errors),
        )

        return result

    except Exception as e:
        logger.error("agent_failed", error=str(e))

        # Try to send error notification
        if not dry_run:
            bot = TelegramBot()
            await bot.send_error_notification(str(e))

        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DziemianMCAgent - AI-powered trend research for YouTube",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without sending to Notion/Telegram",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test connections only",
    )

    args = parser.parse_args()

    if args.test:
        # Test mode - check all connections
        print("Testing connections...")

        settings = get_settings()
        print(f"  Anthropic API Key: {'✓ Set' if settings.anthropic_api_key else '✗ Missing'}")
        print(f"  Notion API Key: {'✓ Set' if settings.notion_api_key else '✗ Missing'}")
        print(f"  Notion Database ID: {'✓ Set' if settings.notion_database_id else '✗ Missing'}")
        print(f"  Telegram Bot Token: {'✓ Set' if settings.telegram_bot_token else '✗ Missing'}")
        print(f"  Telegram Chat ID: {'✓ Set' if settings.telegram_chat_id else '✗ Missing'}")
        print(f"  Apify Token: {'✓ Set' if settings.apify_api_token else '○ Optional'}")

        # Test Notion
        notion = NotionClient()
        if notion.test_connection():
            print("  Notion connection: ✓ OK")
        else:
            print("  Notion connection: ✗ Failed")

        # Test Telegram
        async def test_telegram():
            bot = TelegramBot()
            return await bot.test_connection()

        if asyncio.run(test_telegram()):
            print("  Telegram connection: ✓ OK")
        else:
            print("  Telegram connection: ✗ Failed")

        sys.exit(0)

    # Run the agent
    try:
        result = asyncio.run(run_agent(dry_run=args.dry_run))

        # Print summary
        print("\n" + "=" * 50)
        print(f"🎯 Agent Run Complete (ID: {result.run_id})")
        print("=" * 50)
        print(f"📊 Scraped: {result.total_scraped} items")
        print(f"🔍 Analyzed: {result.total_analyzed} topics")
        print(f"🔥 Outliers: {len(result.outliers)}")

        if result.outliers:
            print("\n🔥 TOP OUTLIERS:")
            for i, topic in enumerate(result.outliers, 1):
                print(f"  {i}. {topic.temat[:60]}")
                print(f"     🎵 {topic.kat_muzyczny[:80]}")

        if result.errors:
            print(f"\n⚠️ Errors: {len(result.errors)}")
            for error in result.errors:
                print(f"  - {error}")

        sys.exit(0 if not result.errors else 1)

    except KeyboardInterrupt:
        print("\n👋 Agent interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Agent failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
