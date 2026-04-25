"""Flat trailer placement + NFO trailer-tag population.

Naming convention (see DESIGN section 4):

    {media_dir}/{media_name}-trailer.{ext}

Used for both movies and TV shows -- this is the single convention that
works across Plex, Kodi, Jellyfin and Emby.

This module is pure path computation + a small NFO XML tweak. It does NOT
write media files -- download is owned by YtdlpDownloader (Phase 3b).
"""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.logger import get_logger

logger = get_logger(__name__)

# Extensions yt-dlp may produce, ordered by Plex-friendliness.
_KNOWN_TRAILER_EXTENSIONS: tuple[str, ...] = ("mp4", "mkv", "webm")


def trailer_path_for(media_dir: Path, media_name: str, *, ext: str = "mp4") -> Path:
    """Compute the expected trailer path for a movie or TV show.

    Flat convention: ``{media_dir}/{media_name}-trailer.{ext}``. Used for
    both movies and TV shows. See DESIGN section 4 for the rationale.

    Args:
        media_dir: Absolute path to the media directory on disk.
        media_name: Folder name of the media directory
            (e.g. "Fight Club (1999)" or "Breaking Bad (2008)").
        ext: File extension for the trailer ("mp4" default; leading dot
            accepted and stripped).

    Returns:
        Absolute Path where the trailer file should be placed.
    """
    ext_clean = ext.lstrip(".")
    return media_dir / f"{media_name}-trailer.{ext_clean}"


def trailer_path_for_season(show_dir: Path, season_number: int, extension: str) -> Path:
    """Return the expected season-trailer placement path.

    Convention: ``{show_dir}/Saison {SS:02d}/{show_dir.name} - Saison {SS:02d}-trailer.{ext}``.

    Opt-in via ``config.trailers.seasons.enabled`` (default off). The path mirrors
    the existing personalscraper French season layout ("Saison XX/") and keeps the
    show-name prefix so Plex Local Media Assets recognises the file as a trailer
    for the parent show. NOT placed in a trailers/ subfolder.

    Args:
        show_dir: Path to the root show folder (contains Saison XX subdirectories).
        season_number: 1-indexed season number (TMDB convention; specials = 0).
        extension: File extension without the leading dot (e.g. "mp4").
            A leading dot, if present, is tolerated and stripped.

    Returns:
        Full path where the season trailer should be written.
    """
    ext_clean = extension.lstrip(".")
    season_dir = show_dir / f"Saison {season_number:02d}"
    return season_dir / f"{show_dir.name} - Saison {season_number:02d}-trailer.{ext_clean}"


def find_existing_trailer(media_dir: Path, media_name: str) -> Path | None:
    """Locate an existing trailer file across known extensions.

    Iterates through ``_KNOWN_TRAILER_EXTENSIONS`` in Plex-preference order
    and returns the first candidate that exists.

    Args:
        media_dir: Absolute path to the media directory.
        media_name: Folder name of the media directory.

    Returns:
        Absolute Path to the existing trailer file, or ``None`` when none
        of the candidates exist.
    """
    for ext in _KNOWN_TRAILER_EXTENSIONS:
        candidate = trailer_path_for(media_dir, media_name, ext=ext)
        if candidate.is_file():
            return candidate
    return None


def trailer_exists(path: Path, min_size_bytes: int) -> bool:
    """Check whether a trailer file exists and meets the minimum size requirement.

    This is the canonical "already present" check -- callers use this before
    initiating any download to ensure idempotence.

    Args:
        path: Absolute path to the expected trailer file.
        min_size_bytes: Minimum file size in bytes to consider the trailer valid.
            A file smaller than this threshold is treated as absent.

    Returns:
        True if the file exists, is a regular file, and its size is at least
        ``min_size_bytes``. False in all other cases.
    """
    if not path.is_file():
        return False
    try:
        return path.stat().st_size >= min_size_bytes
    except OSError:
        return False


def write_trailer_url_to_nfo(nfo_path: Path, youtube_url: str) -> None:
    """Populate the ``<trailer>`` tag in a Kodi/Plex-style NFO with a YouTube URL.

    ``scraper/nfo_generator.py`` currently emits an empty ``<trailer></trailer>``
    tag (lines 160 for movies, 269 for TV shows). Filling it with the discovered
    YouTube URL gives Plex a remote-trailer fallback and gives Kodi/downstream
    tools a cross-referenceable source URL.

    Failure modes are soft: a missing NFO or a parse error logs a WARNING
    and returns -- this function never raises.

    Args:
        nfo_path: Absolute path to the NFO file to update.
        youtube_url: Full YouTube URL to write into the ``<trailer>`` tag.
    """
    if not nfo_path.is_file():
        logger.warning("NFO not found -- skipping trailer URL write: %s", nfo_path)
        return

    try:
        tree = ET.parse(nfo_path)
    except ET.ParseError as exc:
        logger.warning("Cannot parse NFO %s -- skipping trailer URL write: %s", nfo_path, exc)
        return

    root = tree.getroot()
    trailer_elem = root.find("trailer")
    if trailer_elem is None:
        trailer_elem = ET.SubElement(root, "trailer")
    trailer_elem.text = youtube_url

    try:
        tree.write(nfo_path, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        logger.warning("Cannot write NFO %s -- trailer URL not persisted: %s", nfo_path, exc)
