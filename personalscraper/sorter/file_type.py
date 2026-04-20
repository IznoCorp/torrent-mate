"""File type detection for media sorting.

Determines whether a file or directory is a movie, TV show, ebook, audio,
application, or other type. Detection uses file extensions and filename
patterns (season/episode markers). Guessit-enhanced detection is added
by the cleaner in phase 2.

Ported from FileMate's file_type.py and file_type_extensions.py, simplified
to the 6 types relevant to the PersonalScraper staging directories.
"""

import re
from enum import Enum
from pathlib import Path

# Video extensions handled by the pipeline (matches CLAUDE.md list + extras from FileMate)
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {
        "avi",
        "mkv",
        "mp4",
        "mpg",
        "mpeg",
        "mov",
        "wmv",
        "flv",
        "webm",
        "m4v",
        "ts",
        "m2ts",
        "mts",
        "3gp",
        "vob",
        "ogv",
        "rmvb",
    }
)

AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        "mp3",
        "wav",
        "flac",
        "ogg",
        "m4a",
        "wma",
        "aac",
        "ac3",
        "dts",
        "mka",
        "opus",
        "m4b",
        "m4r",
    }
)

EBOOK_EXTENSIONS: frozenset[str] = frozenset(
    {
        "pdf",
        "epub",
        "mobi",
        "azw",
        "azw3",
        "djvu",
        "cbz",
        "cbr",
        "fb2",
        "lit",
    }
)

APP_EXTENSIONS: frozenset[str] = frozenset(
    {
        "exe",
        "msi",
        "dmg",
        "pkg",
        "deb",
        "rpm",
        "apk",
    }
)

# Regex for season/episode markers in filenames (case-insensitive)
# Matches: S01E04, s01e04, S03, 1x04, Saison 1, Season 1
_TVSHOW_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)"
    r"(?:s\d{1,2}e\d{1,2})"  # S01E04
    r"|(?:s\d{1,2}(?!\d))"  # S03 (season pack, not followed by digit)
    r"|(?:\d{1,2}x\d{2,3})"  # 1x04
    r"|(?:saison[\s.]*\d{1,2})"  # Saison 01, Saison.01
    r"|(?:season[\s.]*\d{1,2})"  # Season 01, Season.01
)


class FileType(Enum):
    """Media type categories matching staging subdirectories.

    Attributes:
        MOVIE: Films — sorted to 001-MOVIES/.
        TVSHOW: TV series — sorted to 002-TVSHOWS/.
        EBOOK: Ebooks — sorted to 003-EBOOKS/.
        AUDIO: Audiobooks/music — sorted to 004-AUDIO/.
        APP: Applications — sorted to 005-APPS/ or 006-ANDROID/.
        OTHER: Unrecognized — sorted to 098-AUTRES/.
    """

    MOVIE = "movie"
    TVSHOW = "tvshow"
    EBOOK = "ebook"
    AUDIO = "audio"
    APP = "app"
    OTHER = "other"


def _extension_of(path: Path) -> str:
    """Extract lowercase extension without dot from a path.

    Args:
        path: File or directory path.

    Returns:
        Lowercase extension string (e.g. "mkv"), or empty string.
    """
    return path.suffix.lstrip(".").lower()


def _has_tvshow_markers(name: str) -> bool:
    """Check if a filename contains TV show markers (S01E04, Saison, etc.).

    Args:
        name: Filename or directory name to check.

    Returns:
        True if the name contains recognizable TV show patterns.
    """
    return bool(_TVSHOW_PATTERN.search(name))


def detect_file_type(path: Path) -> FileType:
    """Detect media type from a single file's extension and name patterns.

    Detection order:
    1. Non-video extensions → EBOOK / AUDIO / APP / OTHER
    2. Video extension → check filename for season/episode markers:
       - Markers found → TVSHOW
       - No markers → MOVIE
    3. Unknown extension → OTHER

    Args:
        path: Path to the file (need not exist on disk).

    Returns:
        The detected FileType.
    """
    ext = _extension_of(path)

    if ext in EBOOK_EXTENSIONS:
        return FileType.EBOOK
    if ext in AUDIO_EXTENSIONS:
        return FileType.AUDIO
    if ext in APP_EXTENSIONS:
        return FileType.APP
    if ext in VIDEO_EXTENSIONS:
        return FileType.TVSHOW if _has_tvshow_markers(path.name) else FileType.MOVIE
    return FileType.OTHER


def detect_dir_type(path: Path) -> FileType:
    """Detect media type of a directory from its contents (majority vote).

    Examines direct children of the directory. If the directory name itself
    contains TV show markers, returns TVSHOW immediately (common case for
    season packs like "Show.S03.MULTi.1080p/").

    For directories with mixed content, uses majority vote on video files.
    Non-video children are ignored for the vote (subtitles, NFOs, images
    travel with their parent).

    Args:
        path: Path to an existing directory.

    Returns:
        The detected FileType. Returns OTHER for empty directories.
    """
    # Directory name itself may contain TV markers (e.g. "Show.S03.1080p/")
    if _has_tvshow_markers(path.name):
        return FileType.TVSHOW

    # Tally types from children
    type_counts: dict[FileType, int] = {}
    for child in path.iterdir():
        if child.is_file():
            ft = detect_file_type(child)
            # Only count meaningful types for the vote (skip OTHER like .nfo, .jpg)
            if ft in (FileType.MOVIE, FileType.TVSHOW, FileType.EBOOK, FileType.AUDIO, FileType.APP):
                type_counts[ft] = type_counts.get(ft, 0) + 1

    if not type_counts:
        return FileType.OTHER

    return max(type_counts, key=type_counts.get)  # type: ignore[arg-type]
