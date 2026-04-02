"""YouTube scraper using yt-dlp."""

import asyncio
import subprocess
import json
from datetime import datetime
from typing import Optional

from .base import BaseScraper
from ..models.schemas import ContentSource, VideoData


class YouTubeScraper(BaseScraper[VideoData]):
    """Scraper for YouTube videos using yt-dlp."""

    source = ContentSource.YOUTUBE

    def __init__(self):
        """Initialize YouTube scraper."""
        super().__init__()
        self.channels = self.settings.youtube_channels
        self.keywords = self.settings.youtube_keywords
        self.min_vph = self.settings.min_vph_threshold

    async def scrape(self) -> list[VideoData]:
        """Scrape YouTube for recent videos."""
        videos: list[VideoData] = []

        # Scrape YouTube trending page (Poland)
        trending = await self._scrape_trending()
        videos.extend(trending)

        # Scrape from keyword searches
        keyword_tasks = [
            self._scrape_keyword(keyword) for keyword in self.keywords
        ]
        keyword_results = await asyncio.gather(*keyword_tasks, return_exceptions=True)

        for result in keyword_results:
            if isinstance(result, list):
                videos.extend(result)

        # Deduplicate by video_id
        seen_ids = set()
        unique_videos = []
        for video in videos:
            if video.video_id not in seen_ids:
                seen_ids.add(video.video_id)
                unique_videos.append(video)

        # Filter by VPH threshold
        filtered_videos = [v for v in unique_videos if v.vph >= self.min_vph]

        # Sort by VPH descending
        filtered_videos.sort(key=lambda v: v.vph, reverse=True)

        return filtered_videos

    async def _scrape_trending(self) -> list[VideoData]:
        """Scrape YouTube trending page for Poland."""
        self.logger.info("scraping_trending")
        # YouTube trending for Poland
        url = "https://www.youtube.com/feed/trending?gl=PL&hl=pl"
        return await self._extract_videos(url, max_videos=50)

    async def _scrape_keyword(self, keyword: str) -> list[VideoData]:
        """Search YouTube for videos matching keyword."""
        self.logger.info("scraping_keyword", keyword=keyword)

        # yt-dlp search syntax
        url = f"ytsearch20:{keyword}"
        return await self._extract_videos(url, max_videos=20)

    async def _extract_videos(self, url: str, max_videos: int = 10) -> list[VideoData]:
        """Extract video metadata using yt-dlp."""
        videos = []

        try:
            # Run yt-dlp in subprocess to avoid blocking
            result = await asyncio.to_thread(
                self._run_ytdlp,
                url,
                max_videos,
            )

            if not result:
                return []

            entries = result.get("entries", [result])

            for entry in entries[:max_videos]:
                if not entry:
                    continue

                video = self._parse_video_entry(entry)
                if video and self.is_within_timeframe(video.upload_date):
                    # Try to get transcript
                    video.transcript = await self._get_transcript(video.video_id)
                    videos.append(video)

        except Exception as e:
            self.logger.error(
                "extract_videos_failed",
                url=url,
                error=str(e),
            )

        return videos

    def _run_ytdlp(self, url: str, max_videos: int) -> Optional[dict]:
        """Run yt-dlp and return JSON output."""
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--flat-playlist",
            "--no-warnings",
            "--playlist-end", str(max_videos),
            "--extractor-args", "youtube:skip=dash,hls",
            url,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                self.logger.warning(
                    "ytdlp_error",
                    stderr=result.stderr[:500] if result.stderr else None,
                )
                return None

            # Parse JSON lines
            entries = []
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

            return {"entries": entries}

        except subprocess.TimeoutExpired:
            self.logger.warning("ytdlp_timeout", url=url)
            return None
        except Exception as e:
            self.logger.error("ytdlp_exception", error=str(e))
            return None

    def _parse_video_entry(self, entry: dict) -> Optional[VideoData]:
        """Parse yt-dlp entry into VideoData."""
        try:
            video_id = entry.get("id")
            if not video_id:
                return None

            # Parse upload date
            upload_date_str = entry.get("upload_date")
            if upload_date_str:
                upload_date = datetime.strptime(upload_date_str, "%Y%m%d")
            else:
                # Fallback to current time if no date
                upload_date = datetime.now()

            # Calculate hours since upload
            hours_since = (datetime.now() - upload_date).total_seconds() / 3600
            hours_since = max(hours_since, 0.1)  # Prevent division by zero

            views = entry.get("view_count", 0) or 0
            vph = views / hours_since if hours_since > 0 else 0

            return VideoData(
                video_id=video_id,
                title=entry.get("title", "Unknown"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel_name=entry.get("channel") or entry.get("uploader") or "Unknown",
                channel_url=entry.get("channel_url"),
                views=views,
                upload_date=upload_date,
                hours_since_upload=hours_since,
                vph=vph,
                description=entry.get("description"),
            )

        except Exception as e:
            self.logger.warning("parse_entry_failed", error=str(e))
            return None

    async def _get_transcript(self, video_id: str) -> Optional[str]:
        """Get video transcript/subtitles."""
        try:
            cmd = [
                "yt-dlp",
                "--write-auto-sub",
                "--sub-lang", "pl,en",
                "--skip-download",
                "--sub-format", "vtt",
                "--print", "%(subtitles)j",
                f"https://www.youtube.com/watch?v={video_id}",
            ]

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0 and result.stdout.strip():
                # Parse subtitles JSON
                try:
                    subs = json.loads(result.stdout.strip())
                    # Extract text from subtitles
                    if subs and isinstance(subs, dict):
                        for lang in ["pl", "en"]:
                            if lang in subs:
                                # Get subtitle URL and fetch
                                return await self._fetch_subtitle_text(video_id, lang)
                except json.JSONDecodeError:
                    pass

        except Exception as e:
            self.logger.debug("transcript_fetch_failed", video_id=video_id, error=str(e))

        return None

    async def _fetch_subtitle_text(self, video_id: str, lang: str) -> Optional[str]:
        """Fetch and parse subtitle text."""
        try:
            import tempfile
            import os

            with tempfile.TemporaryDirectory() as tmpdir:
                cmd = [
                    "yt-dlp",
                    "--write-auto-sub",
                    "--sub-lang", lang,
                    "--skip-download",
                    "--sub-format", "vtt",
                    "-o", os.path.join(tmpdir, "%(id)s.%(ext)s"),
                    f"https://www.youtube.com/watch?v={video_id}",
                ]

                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # Find and read the subtitle file
                for f in os.listdir(tmpdir):
                    if f.endswith(".vtt"):
                        with open(os.path.join(tmpdir, f), "r", encoding="utf-8") as sf:
                            content = sf.read()
                            # Clean VTT format
                            return self._clean_vtt(content)

        except Exception as e:
            self.logger.debug("subtitle_fetch_failed", error=str(e))

        return None

    def _clean_vtt(self, vtt_content: str) -> str:
        """Clean VTT subtitle format to plain text."""
        lines = []
        for line in vtt_content.split("\n"):
            # Skip timestamps and metadata
            if "-->" in line or line.startswith("WEBVTT") or not line.strip():
                continue
            # Skip position/alignment tags
            if line.strip().startswith("<") or ":" in line[:10]:
                continue
            # Remove HTML-like tags
            clean_line = line.strip()
            if clean_line and not clean_line[0].isdigit():
                lines.append(clean_line)

        # Deduplicate consecutive lines (auto-subs often repeat)
        deduped = []
        prev_line = None
        for line in lines:
            if line != prev_line:
                deduped.append(line)
                prev_line = line

        return " ".join(deduped)
