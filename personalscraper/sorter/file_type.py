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

#: Tokens that mark a directory NAME as a VIDEO release (resolution / source /
#: video codec). Used ONLY to gate the archive-packed → movie fallback, so a
#: non-media pack (a game/app RePack in a .rar with a filmish name) is not
#: misrouted into 001-MOVIES; without such a token an archive-only dir stays
#: OTHER (→ 098-AUTRES), where it is interactively resolvable if it is media.
_VIDEO_RELEASE_PATTERN: re.Pattern[str] = re.compile(
    r"(?i)(?:"
    r"\b(?:480|540|576|720|1080|1440|2160|4320)p\b"  # resolution
    r"|\b[xh]\.?26[45]\b|\bhevc\b|\bxvid\b|\bdivx\b|\bav1\b"  # video codec
    r"|\bblu-?ray\b|\bbd(?:rip|mux)?\b|\bbrrip\b|\bremux\b"  # disc sources
    r"|\bweb-?dl\b|\bweb-?rip\b|\bwebrip\b|\bhdrip\b|\bdvdrip\b|\bhdtv\b|\bweb\b"  # web/tv sources
    r")"
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


def _looks_like_video_release(name: str) -> bool:
    """Whether *name* carries a video-release signal (resolution / source / codec).

    A scene movie release always carries such a token
    (``Movie.2026.1080p.WEB.h264-GRP``); a non-media RAR pack (game/app RePack)
    does not. Used to gate the archive-packed fallback so the latter stays OTHER
    (→ 098-AUTRES) instead of polluting 001-MOVIES.

    Args:
        name: Directory name to inspect.

    Returns:
        True when a video resolution/source/codec token is present.
    """
    return bool(_VIDEO_RELEASE_PATTERN.search(name))


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
        # No direct video child. If the release is archive-packed (RAR set) AND its
        # name carries a video-release signal (resolution/source/codec), the video is
        # hidden inside the archive — fall back to name-based typing via guessit (the
        # tie-breaker NameCleaner.get_media_type documents) so the release is sorted
        # into MOVIES/TVSHOWS and later extracted, scraped and dispatched instead of
        # being lost in 098-AUTRES. 'episode' → TVSHOW, otherwise MOVIE.
        #
        # The video-release gate avoids the mirror over-reach: a non-media pack
        # (game/app RePack) in a .rar with a filmish name must NOT be routed into
        # 001-MOVIES. Both directions are now recoverable via interactive resolution
        # (an AUTRES item is resolvable + reclassable), so when the archive pack shows
        # no video signal we favour the SAFE default (AUTRES) over polluting MOVIES.
        if has_archive_child and _looks_like_video_release(path.name):
            # Local import: keeps guessit off the module-load path for the many
            # callers that only type plain files, and sidesteps any import ordering
            # concern between the sorter's cleaner and file_type modules.
            from personalscraper.sorter.cleaner import NameCleaner

            media_type = NameCleaner().get_media_type(path.name)
            return FileType.TVSHOW if media_type == "episode" else FileType.MOVIE
        return FileType.OTHER

    return max(type_counts, key=type_counts.get)  # type: ignore[arg-type]
