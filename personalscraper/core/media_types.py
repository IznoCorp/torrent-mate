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

#: Plex's subfolder for TV-show trailer extras (``{show}/Trailers/…`` and
#: ``{show}/Saison NN/Trailers/…``). A video living under it is a re-downloadable
#: auxiliary asset, NOT the collected media — callers that must tell library
#: content from derived assets key off this name.
TV_TRAILER_SUBFOLDER: str = "Trailers"

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


# ---------------------------------------------------------------------------
# Trailer presence — THE shared rule
# ---------------------------------------------------------------------------


#: Extensions yt-dlp may produce for a trailer, in Plex-preference order.
TRAILER_EXTENSIONS: tuple[str, ...] = ("mp4", "mkv", "webm")

#: A yt-dlp per-format fragment left behind by an interrupted download —
#: ``{stem}.f137.mp4``, a video-only stream that was never merged. ``.part`` is
#: swept by the downloader's own cleanup; this residue is not, and a reboot or
#: a SIGKILL mid-download leaves it beside the trailer folder's real contents.
_FORMAT_FRAGMENT = re.compile(r"\.f\d+$")

#: Longest run of alphanumerics still readable as a file extension. ``suffix``
#: returns everything after the LAST dot in the name, so a dotted title with no
#: extension ("Mr. Robot - Saison 1 - trailer") yields a whole phrase; judging
#: that as an unknown extension would hide the file.
_LONGEST_EXTENSION = 5


def trailer_folders_in(media_dir: Path) -> list[Path]:
    """Return every trailer-extras folder directly under *media_dir*.

    Matched case-insensitively against :data:`TV_TRAILER_SUBFOLDER`, because the
    storage mounts are case-sensitive and an earlier release wrote the folder in
    lowercase — so a show can carry two, which are two real directories. The
    canonical spelling sorts first when both are present.

    Args:
        media_dir: The media directory to look inside.

    Returns:
        Matching directories, canonical spelling first; empty when *media_dir*
        cannot be read.
    """
    wanted = TV_TRAILER_SUBFOLDER.casefold()
    try:
        folders = [entry for entry in media_dir.iterdir() if entry.is_dir() and entry.name.casefold() == wanted]
    except OSError:
        return []
    # Exact canonical spelling first, then the rest in a stable order, so the
    # answer does not depend on how the filesystem happens to order entries.
    return sorted(folders, key=lambda folder: (folder.name != TV_TRAILER_SUBFOLDER, folder.name))


def find_trailer_in_media_dir(media_dir: Path, minimum_size_bytes: int = 0) -> Path | None:
    """Return a show-level trailer already on disk, whatever layout wrote it.

    THE single rule for "does this show already have a trailer". It exists
    because the question was answered independently in four places — the
    download decision, the derived ``trailer_found`` index, the audit command
    and the orphan classifier — each naming one exact path,
    ``{show}/Trailers/{show}.{ext}``. A show whose trailer was placed by an
    earlier release keeps it in a lowercase ``trailers/`` under a different file
    name, so every one of them read it as absent. Four answers that must agree
    and do not is how a show gets a second trailer downloaded beside the one it
    owns, and how the shows that stop being downloaded for stay in the
    "missing" query forever.

    A file answers when it is not a sidecar and not an interrupted download.
    A name carrying no extension is NOT a sidecar: 128 of this library's 676
    trailer files have none, and the size floor is what keeps junk out.

    Args:
        media_dir: The show directory on disk.
        minimum_size_bytes: Smallest size counting as a trailer. ``0`` (the
            default) asks only whether a file is there, which is what a
            read-model wants; the downloader passes its configured floor.

    Returns:
        The trailer found, or ``None`` — including when *media_dir* is
        unreadable.
    """
    for folder in trailer_folders_in(media_dir):
        try:
            candidates = sorted(folder.iterdir())
        except OSError:
            continue
        for candidate in candidates:
            if not candidate.is_file() or _is_not_a_trailer(candidate.name):
                continue
            try:
                if candidate.stat().st_size >= minimum_size_bytes:
                    return candidate
            except OSError:
                continue
    return None


def _is_not_a_trailer(name: str) -> bool:
    """Return True for a sidecar or an interrupted download, never for a video.

    Args:
        name: Bare filename inside a trailer folder.

    Returns:
        True when the file must not answer for the show's trailer.
    """
    if _FORMAT_FRAGMENT.search(Path(name).stem):
        return True  # {stem}.f137.mp4 — a stream that was never merged
    suffix = Path(name).suffix.lstrip(".").casefold()
    if not suffix or not suffix.isalnum() or len(suffix) > _LONGEST_EXTENSION:
        return False  # no extension to judge by — the size floor decides
    return suffix not in TRAILER_EXTENSIONS
