"""Trailers scanner.

Media-without-trailer detection for staging and library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from personalscraper.library.scanner import extract_nfo_ids, parse_title_year
from personalscraper.library.scanner import scan_library as _lib_scan
from personalscraper.logger import get_logger
from personalscraper.trailers.placement import (
    trailer_exists,
    trailer_path_for,
    trailer_path_for_season,
)
from personalscraper.trailers.state import _validate_season_number

log = get_logger(__name__)

_SEASON_DIR_RE = re.compile(r"^Saison (\d{2})$")

MediaTypeLiteral = Literal["movie", "tvshow"]


@dataclass(frozen=True, slots=True)
class ScanItem:
    """One piece of media that requires a trailer download attempt.

    Frozen and slotted: scanner output is treated as immutable downstream.
    The orchestrator never mutates a ScanItem; it constructs new state-store
    entries instead.

    Attributes:
        path: Absolute path to the media directory on disk. For season-level
            items this is the show directory (NOT the season subfolder).
        media_type: Literal "movie" or "tvshow" — narrowed at construction.
        title: Human-readable title from directory name or NFO.
        year: Release year, or None when absent from the directory name.
        tmdb_id: TMDB numeric ID as a string, or None if unavailable.
        imdb_id: IMDB tt-prefixed ID, or None if unavailable.
        nfo_path: Path to the NFO file, or None.
        season_number: None for movies/show-level items. Positive integer
            (1-indexed, TMDB convention; 0 = "specials") for season-level
            ScanItems when seasons_enabled is True.
    """

    path: Path
    media_type: MediaTypeLiteral
    title: str
    year: int | None
    tmdb_id: str | None
    imdb_id: str | None = None
    nfo_path: Path | None = None
    season_number: int | None = None

    def __post_init__(self) -> None:
        """Validate season_number domain (TMDB convention: 0 for specials, ≥1 for regular).

        Raises:
            ValueError: If season_number is negative.
        """
        _validate_season_number(self.season_number, "ScanItem")


class Scanner:
    """Detect media directories missing a trailer file.

    Args:
        min_file_size_bytes: Minimum byte size for a trailer file to count as
            present. Files smaller than this are treated as absent.
        seasons_enabled: When True, TV-show directories are also enumerated for
            per-season ScanItems. Defaults to False.
    """

    def __init__(self, min_file_size_bytes: int, seasons_enabled: bool = False) -> None:
        """Initialise the scanner.

        Args:
            min_file_size_bytes: Minimum byte size for a valid trailer file.
            seasons_enabled: Opt-in season-level scanning for TV shows.
        """
        self._min_size = min_file_size_bytes
        self._seasons_enabled = seasons_enabled
        self._last_scan_time: datetime | None = None

    def scan_staging(self, staging_dir: Path) -> list[ScanItem]:
        """Walk a staging directory tree and return items missing trailers.

        Args:
            staging_dir: Root staging directory. May contain multiple
                category subdirs (e.g. 001-MOVIES/, 002-TVSHOWS/).

        Returns:
            List of ScanItem objects for media directories lacking a trailer.
        """
        items: list[ScanItem] = []
        if not staging_dir.is_dir():
            log.warning("scanner_staging_dir_missing", path=str(staging_dir))
            return items
        for category_dir in sorted(staging_dir.iterdir()):
            if not category_dir.is_dir() or category_dir.name.startswith("."):
                continue
            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                items.extend(self._scan_media_dir(media_dir))
        log.debug(
            "scanner_staging_scan_complete",
            staging_dir=str(staging_dir),
            items_found=len(items),
        )
        return items

    def scan_library(
        self,
        config: Any,
        disk_filter: str | None = None,
        category_filter: str | None = None,
        force_refresh: bool = False,
    ) -> list[ScanItem]:
        """Scan the permanent library for media missing trailers.

        Args:
            config: Loaded pipeline Config. Must expose config.disks and
                optionally config.trailers.library_scan_max_age_hours.
            disk_filter: Only scan this disk (by disk.id). None = all.
            category_filter: Only scan this category_id. None = all.
            force_refresh: If True, bypass the age threshold and always rescan.

        Returns:
            List of ScanItem objects for library entries missing a valid trailer.
        """
        # Pydantic strict guarantees this attribute on a real Config; the
        # ``Any`` annotation lets test fixtures pass narrower mocks without
        # going through the loader. Direct access surfaces test misconfig loudly.
        max_age_hours = int(config.trailers.library_scan_max_age_hours)
        if not force_refresh and self._is_scan_fresh(max_age_hours):
            log.debug("scanner_library_scan_skipped_fresh", max_age_hours=max_age_hours)
            return []
        log.info("scanner_library_scan_start", disk_filter=disk_filter, category_filter=category_filter)
        result = _lib_scan(config.disks, config, disk_filter=disk_filter, category_filter=category_filter)
        self._last_scan_time = datetime.now(tz=timezone.utc)
        items: list[ScanItem] = []
        for lib_item in result.items:
            media_dir = Path(lib_item.path)
            media_name = media_dir.name
            # Narrow library_scanner's str media_type to the strict Literal.
            if lib_item.media_type not in ("movie", "tvshow"):
                log.debug(
                    "scanner_unknown_media_type",
                    media_type=lib_item.media_type,
                    path=str(media_dir),
                )
                continue
            media_type: MediaTypeLiteral = "tvshow" if lib_item.media_type == "tvshow" else "movie"
            nfo_path: Path | None = self._nfo_path_for(media_dir, lib_item.title, media_type)
            expected = trailer_path_for(media_dir, media_name)
            if trailer_exists(expected, self._min_size):
                continue
            scan_item = ScanItem(
                path=media_dir,
                media_type=media_type,
                title=lib_item.title,
                year=lib_item.year,
                tmdb_id=lib_item.nfo.tmdb_id,
                imdb_id=lib_item.nfo.imdb_id,
                nfo_path=nfo_path,
                season_number=None,
            )
            items.append(scan_item)
            if self._seasons_enabled and media_type == "tvshow":
                items.extend(self._scan_seasons(media_dir, scan_item))
        log.debug("scanner_library_scan_complete", items_found=len(items))
        return items

    def _is_scan_fresh(self, max_age_hours: int) -> bool:
        """Return True when the cached scan is younger than max_age_hours.

        Args:
            max_age_hours: Threshold for treating the cached scan as fresh.

        Returns:
            True if a previous scan completed within the window.
        """
        if self._last_scan_time is None:
            return False
        age_seconds = (datetime.now(tz=timezone.utc) - self._last_scan_time).total_seconds()
        return age_seconds < max_age_hours * 3600

    def _scan_media_dir(self, media_dir: Path) -> list[ScanItem]:
        """Scan a single media directory and return missing-trailer ScanItems.

        Args:
            media_dir: Absolute path to the media directory.

        Returns:
            List of ScanItem instances for the show-level item plus any
            season-level entries when seasons_enabled is True.
        """
        media_name = media_dir.name
        is_tvshow = (media_dir / "tvshow.nfo").is_file()
        media_type: MediaTypeLiteral = "tvshow" if is_tvshow else "movie"
        title, year = parse_title_year(media_name)
        nfo_path = self._nfo_path_for(media_dir, title, media_type)
        tmdb_id: str | None = None
        imdb_id: str | None = None
        if nfo_path is not None and nfo_path.is_file():
            tmdb_id, imdb_id = extract_nfo_ids(nfo_path)
        show_item = ScanItem(
            path=media_dir,
            media_type=media_type,
            title=title,
            year=year,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            nfo_path=nfo_path,
            season_number=None,
        )
        items: list[ScanItem] = []
        expected = trailer_path_for(media_dir, media_name)
        if not trailer_exists(expected, self._min_size):
            items.append(show_item)
        if self._seasons_enabled and is_tvshow:
            items.extend(self._scan_seasons(media_dir, show_item))
        return items

    def _scan_seasons(self, show_dir: Path, show_item: ScanItem) -> list[ScanItem]:
        """Enumerate Saison NN/ subfolders and return missing-trailer ScanItems.

        Args:
            show_dir: TV-show root directory containing Saison XX subfolders.
            show_item: Show-level ScanItem whose IDs/title are inherited.

        Returns:
            List of season-level ScanItems whose ``path`` is the show directory
            and ``season_number`` is 1-indexed (TMDB convention).
        """
        season_items: list[ScanItem] = []
        for sub in sorted(show_dir.iterdir()):
            if not sub.is_dir():
                continue
            m = _SEASON_DIR_RE.match(sub.name)
            if not m:
                continue
            season_number = int(m.group(1))
            expected_season = trailer_path_for_season(show_dir, season_number, "mp4")
            if trailer_exists(expected_season, self._min_size):
                continue
            season_items.append(
                ScanItem(
                    path=show_dir,
                    media_type="tvshow",
                    title=show_item.title,
                    year=show_item.year,
                    tmdb_id=show_item.tmdb_id,
                    imdb_id=show_item.imdb_id,
                    nfo_path=show_item.nfo_path,
                    season_number=season_number,
                )
            )
        return season_items

    @staticmethod
    def _nfo_path_for(media_dir: Path, title: str, media_type: str) -> Path | None:
        """Compute the conventional NFO path for a media directory.

        Args:
            media_dir: Directory holding the NFO.
            title: Movie title used as the NFO filename for movies.
            media_type: ``"movie"`` or ``"tvshow"``.

        Returns:
            Path to the expected NFO file, or None for unknown media types.
        """
        if media_type == "tvshow":
            return media_dir / "tvshow.nfo"
        if media_type == "movie":
            return media_dir / f"{title}.nfo"
        return None  # pragma: no cover
