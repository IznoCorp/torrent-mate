"""Extracted scraper service module."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.logger import get_logger
from personalscraper.scraper.confidence import MatchResult
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS

log = get_logger("scraper")

_FOLDER_PATTERN = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")
_SXXEXX_RE = re.compile(r"S(\d+)E(\d+)", re.IGNORECASE)
_EPISODE_STRICT_RE = re.compile(r"^S\d{2}E\d{2} - .+\.\w+$")
_EPISODE_FALLBACK_RE = re.compile(r"^S\d{2}E0*(\d+) - Episode 0*\1\.\w+$", re.IGNORECASE)


@dataclass
class ScrapeResult:
    """Result of scraping a single media item.

    Attributes:
        media_path: Path to the media directory.
        media_type: Type of media ("movie" or "tvshow").
        match: Matched API result, or None if no match.
        category_id: Category ID from classifier.classify(), or None.
        nfo_written: Whether an NFO file was written.
        artwork_downloaded: List of downloaded artwork filenames.
        episodes_renamed: Number of episodes renamed (0 for movies).
        action: Result action ("scraped", "skipped_low_confidence",
            "skipped_already_done", "artwork_recovered", "error",
            "skipped_no_category").
        error: Error message if action is "error".
        warnings: Non-fatal issues (e.g. artwork download failure).
    """

    media_path: Path
    media_type: str
    match: MatchResult | None = None
    category_id: str | None = None
    nfo_written: bool = False
    artwork_downloaded: list[str] = field(default_factory=list)
    episodes_renamed: int = 0
    action: str = "error"
    error: str | None = None
    warnings: list[str] = field(default_factory=list)


def _find_video_file(directory: Path) -> Path | None:
    """Find the main video file in a directory tree.

    Searches recursively for video files. When multiple are found,
    returns the largest one (main feature, not sample/extra).
    Skips hidden files and .actors/ directories.

    Args:
        directory: Root directory to search.

    Returns:
        Path to the largest video file, or None if no video found.
    """
    candidates = [
        f
        for f in directory.rglob("*")
        if f.is_file()
        and f.suffix.lstrip(".").lower() in VIDEO_EXTENSIONS
        and not f.name.startswith(".")
        and ".actors" not in f.parts
        and "Trailers" not in f.parts
    ]
    if not candidates:
        return None
    try:
        return max(candidates, key=lambda f: f.stat().st_size)
    except OSError:
        # stat() failed on a candidate (broken symlink, NTFS metadata issue)
        # — fall back to first candidate rather than crashing the scrape
        log.warning("video_stat_failed", directory=directory.name)
        return candidates[0]
