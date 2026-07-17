"""Trailer placement + NFO trailer-tag population.

Naming conventions, derived directly from the Plex documentation:

- Movies (Plex Local Media Assets): flat naming next to the media file —
  ``{movie_dir}/{movie_name}-trailer.{ext}``. Reference:
  https://support.plex.tv/articles/local-files-for-trailers-and-extras/
- TV shows (Plex TV Series agent extras): subfolder convention only —
  ``{show_dir}/Trailers/{show_name}.{ext}`` for show-level and
  ``{show_dir}/Saison {NN}/Trailers/{show_name} - Saison {NN}.{ext}`` for
  season-level. Reference:
  https://support.plex.tv/articles/local-files-for-tv-show-trailers-and-extras/
  The Plex doc explicitly restricts the flat ``-trailer`` suffix to inline-
  episode extras (``S01E01 - Title-trailer.ext``); using it at show or season
  level produces an unrecognised orphan video, which is what shipped in the
  initial trailer feature and was caught by the 2026-04-25 pipeline run.

This module is pure path computation + a small NFO XML tweak. It does NOT
write media files -- download is owned by
``personalscraper.trailers.discovery.ytdlp_downloader.YtdlpDownloader``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from xml.etree import ElementTree as ET

from personalscraper.logger import get_logger

logger = get_logger(__name__)

# Extensions yt-dlp may produce, ordered by Plex-friendliness.
_KNOWN_TRAILER_EXTENSIONS: tuple[str, ...] = ("mp4", "mkv", "webm")

# Plex's required subfolder name for TV-show trailer extras. Plex documents an
# enum of Extra_Directory_Type folders ("Behind The Scenes", "Featurettes",
# "Trailers", …); we only emit "Trailers" since this is the only kind we
# produce.
_TV_TRAILER_SUBFOLDER: str = "Trailers"

MediaTypeLiteral = Literal["movie", "tvshow"]


def trailer_path_for(
    media_dir: Path,
    media_name: str,
    *,
    media_type: MediaTypeLiteral = "movie",
    ext: str = "mp4",
) -> Path:
    """Compute the expected trailer path for a movie or TV show.

    Args:
        media_dir: Absolute path to the media directory on disk.
        media_name: Folder name of the media directory
            (e.g. "Fight Club (1999)" or "Breaking Bad (2008)").
        media_type: ``"movie"`` (flat ``{media_name}-trailer.{ext}`` next to
            the media file, per Plex Local Media Assets) or ``"tvshow"``
            (subfolder ``Trailers/{media_name}.{ext}``, the only convention
            recognised by Plex's TV Series agent for show-level extras).
        ext: File extension for the trailer ("mp4" default; leading dot
            accepted and stripped).

    Returns:
        Absolute Path where the trailer file should be placed.
    """
    ext_clean = ext.lstrip(".")
    if media_type == "tvshow":
        return media_dir / _TV_TRAILER_SUBFOLDER / f"{media_name}.{ext_clean}"
    return media_dir / f"{media_name}-trailer.{ext_clean}"


def trailer_path_for_season(show_dir: Path, season_number: int, extension: str) -> Path:
    """Return the expected season-trailer placement path.

    Convention (Plex TV-show season extras):
    ``{show_dir}/Saison {SS:02d}/Trailers/{show_dir.name} - Saison {SS:02d}.{ext}``.

    Opt-in via ``config.trailers.seasons.enabled`` (default off). The path
    mirrors the existing personalscraper French season layout
    (``Saison XX/``) — the project library uses this name and Plex matches it
    correctly — and the inner ``Trailers/`` subfolder follows the Plex
    documented convention for per-season extras. The show-name prefix on the
    file gives the file a human-readable identity when listed inside Plex's
    extras row alongside Behind The Scenes / Featurettes etc.

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
    return season_dir / _TV_TRAILER_SUBFOLDER / f"{show_dir.name} - Saison {season_number:02d}.{ext_clean}"


def find_existing_trailer(
    media_dir: Path,
    media_name: str,
    *,
    media_type: MediaTypeLiteral = "movie",
) -> Path | None:
    """Locate an existing trailer file across known extensions.

    Iterates through ``_KNOWN_TRAILER_EXTENSIONS`` in Plex-preference order
    and returns the first candidate that exists. The location scanned depends
    on ``media_type``: flat ``{name}-trailer.{ext}`` for movies, subfolder
    ``Trailers/{name}.{ext}`` for TV shows.

    Args:
        media_dir: Absolute path to the media directory.
        media_name: Folder name of the media directory.
        media_type: Selects between movie (flat) and tvshow (subfolder)
            placement.

    Returns:
        Absolute Path to the existing trailer file, or ``None`` when none
        of the candidates exist.
    """
    for ext in _KNOWN_TRAILER_EXTENSIONS:
        candidate = trailer_path_for(media_dir, media_name, media_type=media_type, ext=ext)
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


def write_trailer_url_to_nfo(nfo_path: Path, youtube_url: str) -> bool:
    """Populate the ``<trailer>`` tag in a Kodi/Plex-style NFO with a YouTube URL.

    ``scraper/nfo_generator.py`` currently emits an empty ``<trailer></trailer>``
    tag (in ``_build_movie_nfo`` and ``_build_tv_nfo``). Filling it with the
    discovered YouTube URL gives Plex a remote-trailer fallback and gives
    Kodi/downstream tools a cross-referenceable source URL.

    Writes are atomic: the updated XML is written to a ``{nfo_path}.tmp-{pid}``
    sibling first, then ``os.replace`` swaps it onto the real path. This
    mirrors the ``state.py``/``json_ttl_cache`` pattern so a SIGINT mid-write
    can never truncate the original NFO.

    The ``finally`` block guarantees that the ``.tmp-{pid}`` sibling is removed
    on every error path — including ``xml.etree.ElementTree.ParseError``,
    ``UnicodeEncodeError``, ``TypeError``, and ``OSError`` — so no orphan temp
    file is ever left on disk.

    Failure modes are soft: a missing NFO or a parse error logs a WARNING
    and returns ``False`` — this function never raises.

    Args:
        nfo_path: Absolute path to the NFO file to update.
        youtube_url: Full YouTube URL to write into the ``<trailer>`` tag.

    Returns:
        ``True`` if the NFO was updated successfully, ``False`` on any failure
        (missing file, parse error, write error).
    """
    import os

    if not nfo_path.is_file():
        logger.warning("trailer_nfo_missing", nfo_path=str(nfo_path))
        return False

    try:
        tree = ET.parse(nfo_path)
    except ET.ParseError as exc:
        logger.warning("trailer_nfo_parse_failed", nfo_path=str(nfo_path), error=str(exc))
        return False

    root = tree.getroot()
    trailer_elem = root.find("trailer")
    if trailer_elem is None:
        trailer_elem = ET.SubElement(root, "trailer")
    trailer_elem.text = youtube_url

    tmp_path = nfo_path.with_name(f"{nfo_path.name}.tmp-{os.getpid()}")
    try:
        tree.write(str(tmp_path), encoding="utf-8", xml_declaration=True)
        os.replace(str(tmp_path), str(nfo_path))
        return True
    except Exception as exc:
        # The trailer file downloaded successfully; failing to record the URL
        # in NFO leaves Plex without the remote-trailer fallback.
        logger.error(
            "trailer_nfo_write_failed",
            nfo_path=str(nfo_path),
            error=str(exc),
            exc_info=True,
        )
        return False
    finally:
        # Unconditional cleanup: remove the temp sibling on every error path
        # (OSError, UnicodeEncodeError, ParseError, etc.) so no orphan is left.
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            logger.debug(
                "placement.tmp_cleanup_failed",
                path=str(tmp_path),
                error=str(cleanup_exc),
            )
