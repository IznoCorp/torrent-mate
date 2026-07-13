"""File type detection for media sorting.

Determines whether a file or directory is a movie, TV show, ebook, audio,
application, or other type. Detection uses file extensions and filename
patterns (season/episode markers). Guessit-enhanced detection is added
by the cleaner in phase 2.

Ported from FileMate's file_type.py and file_type_extensions.py, simplified
to the 6 types relevant to the PersonalScraper staging directories.
"""

import re
from pathlib import Path

# Shared constants and the FileType enum are canonical in core.media_types.
# Imported here as a plain (non-re-exported) dependency so the sorter-internal
# detection functions (detect_file_type / detect_dir_type) can use them. The
# transitional re-export for legacy `from personalscraper.sorter.file_type import …`
# call sites was dropped at the end of arch-cleanup-2 Phase 3 — every external
# caller now imports these symbols from core.media_types directly.
from personalscraper.core.media_types import (
    AUDIO_EXTENSIONS,
    EBOOK_EXTENSIONS,
    VIDEO_EXTENSIONS,
    FileType,
    is_archive_filename,
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

    Archive-only fallback: a scene release ships the real video packed inside
    a multi-part RAR set (e.g. "Movie.2026.1080p.WEB-GRP/" holding only
    .rar/.r00…/.nfo/.sfv), so extension voting finds no video child. Rather
    than typing it OTHER — which strands the release in 098-AUTRES, out of
    reach of the Phase-3 RAR extraction that only scans the movies/tvshows
    dirs — the type is resolved from the directory NAME via guessit.

    Args:
        path: Path to an existing directory.

    Returns:
        The detected FileType. Returns OTHER for empty directories or
        directories holding only non-media, non-archive files.
    """
    # Directory name itself may contain TV markers (e.g. "Show.S03.1080p/")
    if _has_tvshow_markers(path.name):
        return FileType.TVSHOW

    # Tally types from children; note whether a direct child is an archive part.
    type_counts: dict[FileType, int] = {}
    has_archive_child = False
    for child in path.iterdir():
        if child.is_file():
            if is_archive_filename(child.name):
                has_archive_child = True
            ft = detect_file_type(child)
            # Only count meaningful types for the vote (skip OTHER like .nfo, .jpg)
            if ft in (FileType.MOVIE, FileType.TVSHOW, FileType.EBOOK, FileType.AUDIO, FileType.APP):
                type_counts[ft] = type_counts.get(ft, 0) + 1

    if not type_counts:
        # No direct video child. If the release is archive-packed (RAR set), the
        # video is hidden inside the archive — fall back to name-based typing via
        # guessit (the tie-breaker NameCleaner.get_media_type documents) so the
        # release is sorted into MOVIES/TVSHOWS and later extracted, scraped and
        # dispatched instead of being lost in 098-AUTRES. 'episode' → TVSHOW,
        # otherwise MOVIE: staging holds media torrents, so a mistype is recoverable
        # via interactive resolution while a film silently stranded in AUTRES is not.
        if has_archive_child:
            # Local import: keeps guessit off the module-load path for the many
            # callers that only type plain files, and sidesteps any import ordering
            # concern between the sorter's cleaner and file_type modules.
            from personalscraper.sorter.cleaner import NameCleaner

            media_type = NameCleaner().get_media_type(path.name)
            return FileType.TVSHOW if media_type == "episode" else FileType.MOVIE
        return FileType.OTHER

    return max(type_counts, key=type_counts.get)  # type: ignore[arg-type]
