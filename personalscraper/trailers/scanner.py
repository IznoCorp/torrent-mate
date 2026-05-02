"""Trailers scanner.

Media-without-trailer detection for staging and library.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from personalscraper.indexer import query as indexer_query
from personalscraper.indexer.repos import item_repo
from personalscraper.library.scanner import extract_nfo_ids, parse_title_year
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

    def scan_staging(self, staging_dir: Path, config: Any | None = None) -> list[ScanItem]:
        """Walk a staging directory tree and return items missing trailers.

        Only the staging subdirs configured for FileType.MOVIE and
        FileType.TVSHOW are scanned. Other category dirs (audio, ebooks,
        scripts…) are skipped — the trailer feature is meaningless for them
        and scanning would produce false positives classified as movies (see
        commit 3792ea9: 47 audio books triggered YouTube downloads).

        When ``config`` is None, the legacy permissive walk is used: every
        subdir is scanned and items without ``tvshow.nfo`` default to movies.
        This branch is retained for tests and for callers that have not yet
        wired the config through; production callers must pass ``config``.

        Args:
            staging_dir: Root staging directory.
            config: Loaded pipeline Config. When provided, restricts the
                scan to the configured movie/tvshow staging subdirs and
                forwards the resolved media_type to ``_scan_media_dir`` so
                classification is deterministic instead of file-presence
                inferred.

        Returns:
            List of ScanItem objects for media directories lacking a trailer.
        """
        items: list[ScanItem] = []
        if not staging_dir.is_dir():
            log.warning("scanner_staging_dir_missing", path=str(staging_dir))
            return items

        scan_specs = self._resolve_scan_specs(staging_dir, config)
        for category_dir, forced_type in scan_specs:
            if not category_dir.is_dir():
                log.debug("scanner_category_dir_missing", path=str(category_dir))
                continue
            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                items.extend(self._scan_media_dir(media_dir, forced_type=forced_type))
        log.debug(
            "scanner_staging_scan_complete",
            staging_dir=str(staging_dir),
            items_found=len(items),
            whitelisted=config is not None,
        )
        return items

    @staticmethod
    def _resolve_scan_specs(staging_dir: Path, config: Any | None) -> list[tuple[Path, MediaTypeLiteral | None]]:
        """Return the (category_dir, forced_media_type) pairs to scan.

        With ``config``: lookup FileType.MOVIE and FileType.TVSHOW staging
        entries and return their absolute paths with the matching media_type
        forced. Without ``config``: legacy permissive walk over every direct
        subdirectory, with media_type left to per-item heuristic.

        Args:
            staging_dir: Root staging directory.
            config: Loaded Config or None.

        Returns:
            List of (path, forced_media_type) tuples. ``forced_media_type``
            is None in the legacy branch.
        """
        if config is None:
            return [
                (sub, None) for sub in sorted(staging_dir.iterdir()) if sub.is_dir() and not sub.name.startswith(".")
            ]

        # Lazy import to avoid a hard dependency on conf/sorter from tests
        # that mock Scanner with stub configs.
        from personalscraper.conf.staging import find_by_file_type, folder_name
        from personalscraper.sorter.file_type import FileType

        specs: list[tuple[Path, MediaTypeLiteral | None]] = []
        for ft, media_type in ((FileType.MOVIE, "movie"), (FileType.TVSHOW, "tvshow")):
            try:
                entry = find_by_file_type(config, ft)
            except KeyError:
                log.warning("scanner_staging_dir_unmapped", file_type=ft.value)
                continue
            specs.append((staging_dir / folder_name(entry), media_type))  # type: ignore[arg-type]
        return specs

    def scan_library(
        self,
        conn: sqlite3.Connection,
        disk_filter: str | None = None,
        category_filter: str | None = None,
    ) -> list[ScanItem]:
        """Scan the permanent library for media missing trailers using the indexer DB.

        Queries the indexer database for media items that have no
        ``item_attribute(key='trailer_found')`` row.  The filesystem path for
        each item is recovered from the ``dispatch_path`` flex attribute,
        which is written both by the dispatch layer (on move into permanent
        storage) and by ``library/scanner.scan_library`` (on direct disk
        indexing).  Items reach the indexer through either entry point and
        are therefore visible regardless of how they were first registered.

        Items whose ``dispatch_path`` attribute is absent or whose path does
        not exist on disk are skipped with a debug-level log — they may belong
        to an unmounted disk or to a stale row that has not yet been
        reconciled.

        Args:
            conn: Open, readable SQLite connection to the indexer database.
            disk_filter: When provided, restrict to items on this disk ID
                (matches the ``dispatch_disk`` attribute value).  None = all disks.
            category_filter: When provided, restrict to items with this
                ``category_id`` value.  None = all categories.

        Returns:
            List of ScanItem objects for library entries missing a valid trailer.
        """
        log.info("scanner_library_scan_start", disk_filter=disk_filter, category_filter=category_filter)

        # Query the indexer for every item that has not yet received a trailer.
        candidate_items = indexer_query.find_items_without_trailer(conn)

        items: list[ScanItem] = []
        for db_item in candidate_items:
            # Recover the on-disk path stored by the dispatch layer.
            dispatch_path_attr = item_repo.get_attr(conn, db_item.id, "dispatch_path")
            if dispatch_path_attr is None or dispatch_path_attr.value is None:
                log.debug(
                    "scanner_library_item_no_dispatch_path",
                    item_id=db_item.id,
                    title=db_item.title,
                )
                continue

            media_dir = Path(dispatch_path_attr.value)

            # Apply optional disk filter (matches the dispatch_disk attribute).
            if disk_filter is not None:
                dispatch_disk_attr = item_repo.get_attr(conn, db_item.id, "dispatch_disk")
                if dispatch_disk_attr is None or dispatch_disk_attr.value != disk_filter:
                    continue

            # Apply optional category filter.
            if category_filter is not None and db_item.category_id != category_filter:
                continue

            if not media_dir.exists():
                log.debug(
                    "scanner_library_item_path_missing",
                    item_id=db_item.id,
                    title=db_item.title,
                    path=str(media_dir),
                )
                continue

            # Narrow the DB kind ('movie' / 'show') to the scanner Literal.
            if db_item.kind == "show":
                media_type: MediaTypeLiteral = "tvshow"
            elif db_item.kind == "movie":
                media_type = "movie"
            else:
                log.debug(
                    "scanner_library_unknown_kind",
                    item_id=db_item.id,
                    kind=db_item.kind,
                )
                continue

            nfo_path: Path | None = self._nfo_path_for(media_dir, db_item.title, media_type)
            media_name = media_dir.name
            expected = trailer_path_for(media_dir, media_name, media_type=media_type)
            if trailer_exists(expected, self._min_size):
                # Trailer file already present (DB not yet updated); skip.
                continue

            # tmdb_id in the DB is an int; ScanItem expects str | None.
            tmdb_id_str: str | None = str(db_item.tmdb_id) if db_item.tmdb_id is not None else None

            scan_item = ScanItem(
                path=media_dir,
                media_type=media_type,
                title=db_item.title,
                year=db_item.year,
                tmdb_id=tmdb_id_str,
                imdb_id=db_item.imdb_id,
                nfo_path=nfo_path,
                season_number=None,
            )
            items.append(scan_item)

            if self._seasons_enabled and media_type == "tvshow":
                items.extend(self._scan_seasons(media_dir, scan_item))

        log.debug("scanner_library_scan_complete", items_found=len(items))
        return items

    def _scan_media_dir(self, media_dir: Path, forced_type: MediaTypeLiteral | None = None) -> list[ScanItem]:
        """Scan a single media directory and return missing-trailer ScanItems.

        Args:
            media_dir: Absolute path to the media directory.
            forced_type: When provided, classifies the item as this media_type
                without inspecting filesystem markers. Set by the FileType-aware
                staging walk so e.g. items in the configured movies dir are
                always tagged "movie" even if they happen to contain a stale
                ``tvshow.nfo``. ``None`` falls back to the legacy heuristic.

        Returns:
            List of ScanItem instances for the show-level item plus any
            season-level entries when seasons_enabled is True.
        """
        media_name = media_dir.name
        is_tvshow = forced_type == "tvshow" if forced_type is not None else (media_dir / "tvshow.nfo").is_file()
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
        expected = trailer_path_for(media_dir, media_name, media_type=media_type)
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
