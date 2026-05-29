"""Shared media-type constants and filename predicates.

Promotes the canonical file-extension sets and ``FileType`` enum out of
``sorter/`` into the lowest-layer ``core/`` package so any subpackage
can import them without taking a dependency on the sorter pipeline step
(arch-cleanup-2 Phase 3).

The detection *functions* (``detect_file_type``, ``detect_dir_type``) remain
in ``sorter/file_type.py`` because they contain sorter-specific pipeline
heuristics. This module holds only the shared *constants* and the
cross-package filename predicate ``is_trailer_filename``.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Extension sets
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# FileType enum
# ---------------------------------------------------------------------------


class FileType(Enum):
    """Media type categories matching staging subdirectories.

    Attributes:
        MOVIE: Films — sorted to the movies staging dir.
        TVSHOW: TV series — sorted to the tvshows staging dir.
        EBOOK: Ebooks — sorted to the ebooks staging dir.
        AUDIO: Audiobooks/music — sorted to the audio staging dir.
        APP: Applications — sorted to the apps staging dir.
        OTHER: Unrecognized type.
    """

    MOVIE = "movie"
    TVSHOW = "tvshow"
    EBOOK = "ebook"
    AUDIO = "audio"
    APP = "app"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Shared filename predicate
# ---------------------------------------------------------------------------


def is_trailer_filename(name: str) -> bool:
    """Check if a filename is a flat Plex movie trailer (filename-only check).

    Movies place their trailer FLAT at the movie root following the Plex Local
    Media Assets convention: ``{media_name}-trailer.{ext}``. This predicate
    lets dedup logic exempt that trailer from duplicate-video detection so a
    movie with its trailer is not wrongly flagged as holding two feature videos.

    The match is purely on the filename stem: it is ``True`` only when the stem
    ends with the ``-trailer`` suffix (case-insensitive). A movie literally
    named "The Trailer" has stem "The Trailer" (no hyphen) and is NOT matched.

    Args:
        name: Filename (basename only; any directory part is ignored).

    Returns:
        ``True`` if the filename stem ends with ``-trailer`` (case-insensitive).
    """
    return Path(name).stem.casefold().endswith("-trailer")
