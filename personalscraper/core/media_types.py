"""Shared media-type constants and filename predicates.

Promotes the canonical file-extension sets and ``FileType`` enum out of
``sorter/`` into the lowest-layer ``core/`` package so any subpackage
can import them without taking a dependency on the sorter pipeline step
(arch-cleanup-2 Phase 3).

The detection *functions* (``detect_file_type``, ``detect_dir_type``) remain
in ``sorter/file_type.py`` because they contain sorter-specific pipeline
heuristics. This module holds the shared *constants*, the ``FileType`` enum
(the sorter filesystem category — distinct from
``core._contracts.MediaType``, the API/metadata kind), and the cross-package
filename predicate ``is_trailer_filename``.
"""

from __future__ import annotations

import re
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

    Distinct from :class:`personalscraper.core._contracts.MediaType`:
    ``MediaType`` is the API/metadata kind (2 values — ``tv`` / ``movie``);
    ``FileType`` is the sorter filesystem category (6 values below).

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


# ---------------------------------------------------------------------------
# Scene-release sample + archive artifacts
# ---------------------------------------------------------------------------

# Subdirectory names that scene releases use for preview clips. A release dir
# named one of these (case-insensitive) holds a short ``*-sample.*`` clip that
# must never be mistaken for the real episode/feature video.
SAMPLE_DIR_NAMES: frozenset[str] = frozenset({"sample", "samples", "proof"})

# Archive container extensions. Scene releases ship the real video inside a
# multi-part RAR set; these are the *primary* archive extensions. Old-style RAR
# volumes (``.r00``..``.r99``) and new-style (``.partNN.rar``) are matched by
# ``is_archive_filename`` via regex in addition to this set.
ARCHIVE_EXTENSIONS: frozenset[str] = frozenset({"rar", "zip", "7z", "tar", "gz", "bz2", "cab"})

# Old-style RAR volume suffix: ``.r00``, ``.r01`` … ``.r99`` (the continuation
# volumes that follow the entry ``.rar``).
_RAR_VOLUME_RE = re.compile(r"\.r\d{2}$", re.IGNORECASE)


def is_sample_filename(name: str) -> bool:
    """Check whether a filename is a scene-release sample clip (name-only check).

    Scene releases name their preview clip ``{release}-sample.{ext}`` or
    ``{release}.sample.{ext}``, or simply ``sample.{ext}``. The match is strict
    on the stem suffix so a legitimate title that merely *contains* the word
    "sample" (e.g. ``Free.Sample.2012.1080p.x264.mkv``) is NOT matched — only a
    delimited ``-sample`` / ``.sample`` suffix (or the bare stem ``sample``).

    Args:
        name: Filename (basename only; any directory part is ignored).

    Returns:
        ``True`` if the filename stem marks it as a sample clip.
    """
    stem = Path(name).stem.casefold()
    return stem == "sample" or stem.endswith("-sample") or stem.endswith(".sample")


def is_sample_path(path: Path) -> bool:
    """Check whether a path is (or is inside) a scene-release sample location.

    ``True`` when any path component is a sample directory (``Sample/``,
    ``Samples/``, ``Proof/`` — case-insensitive) OR the basename is a sample
    clip per :func:`is_sample_filename`. This is the single predicate every
    video-discovery glob uses to keep sample clips out of episode/feature
    selection.

    Args:
        path: Path to test (file or directory).

    Returns:
        ``True`` if the path lies under a sample dir or is a sample file.
    """
    if any(part.casefold() in SAMPLE_DIR_NAMES for part in path.parts):
        return True
    return is_sample_filename(path.name)


def is_archive_filename(name: str) -> bool:
    """Check whether a filename is an archive container or RAR volume part.

    Matches primary archive extensions (:data:`ARCHIVE_EXTENSIONS`, e.g.
    ``.rar``/``.zip``/``.7z``) and old-style multi-volume RAR continuation
    parts (``.r00``..``.r99``). Used to (a) preserve a release directory from
    deletion when extraction failed (no silent data loss) and (b) block
    dispatch of an item that still holds un-extracted archives.

    Args:
        name: Filename (basename only).

    Returns:
        ``True`` if the filename is an archive container or RAR volume part.
    """
    ext = Path(name).suffix.lstrip(".").lower()
    if ext in ARCHIVE_EXTENSIONS:
        return True
    return bool(_RAR_VOLUME_RE.search(name))
