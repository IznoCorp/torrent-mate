"""Lightweight library scanner — structure, NFO, artwork inventory.

Scans storage disks without ffprobe. Produces ``LibraryScanItem`` for each
media directory found and writes the result to the indexer DB. Uses existing
utilities: ``is_nfo_complete()`` and ``SEASON_DIR_RE``.

``scan_library`` accepts a ``Config`` object and a SQLite connection and
populates the indexer DB (``media_item``, ``season``, ``episode`` tables via
repos; ``media_file`` / ``path`` via :func:`personalscraper.indexer.scanner.scan`;
``dispatch_path`` / ``dispatch_disk`` flex attributes via
:func:`personalscraper.indexer.repos.item_repo.upsert_attr`).

The helper functions ``scan_movie_dir``, ``scan_tvshow_dir``,
``parse_title_year``, and ``extract_nfo_ids`` remain public for callers that
still use them directly (e.g. ``library/rescraper.py``,
``trailers/scanner.py``).
"""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.conf.models.disks import DiskConfig

from personalscraper.conf.ids import AUDIOBOOKS, TV_CATEGORY_IDS
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.repos import disk_repo, tv_repo
from personalscraper.indexer.repos import item_repo as _item_repo
from personalscraper.indexer.scanner import ScanMode
from personalscraper.indexer.scanner import scan as _indexer_scan
from personalscraper.indexer.schema import (
    ArtworkInventory,
    DiskRow,
    MediaItemKind,
    MediaItemRow,
    SeasonRow,
)
from personalscraper.indexer.schema import (
    NfoStatus as DbNfoStatus,
)
from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
    ISSUE_NTFS_UNSAFE,
    ISSUE_RELEASE_ARTIFACT,
    ArtworkStatus,
    LibraryScanItem,
    NfoStatus,
    SeasonInfo,
)
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete

log = get_logger("library.scanner")

# Title (Year) pattern — same as _parse_folder_name in scraper
_TITLE_YEAR_RE = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")

# NTFS-illegal characters
_NTFS_ILLEGAL = re.compile(r'[<>:"/\\|?*]')

# Junk files: shared SSOT in text_utils.JUNK_FILE_NAMES.  macOS resource
# fork prefix "._" is matched separately at every call site.
# Video extensions: re-exported from sorter.file_type so the library
# scanner and the sorter share the single source of truth for what counts
# as a video file across the pipeline.
from personalscraper.sorter.file_type import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS  # noqa: E402
from personalscraper.text_utils import JUNK_FILE_NAMES as _JUNK_FILES  # noqa: E402


def parse_title_year(dirname: str) -> tuple[str, int | None]:
    """Parse 'Title (Year)' from a directory name.

    Args:
        dirname: Directory name (not full path).

    Returns:
        Tuple of (title, year). Year is None if not found.
    """
    m = _TITLE_YEAR_RE.match(dirname)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return dirname, None


def _dir_size_gb(path: Path) -> float:
    """Calculate total size of all files in a directory (recursive), in GB.

    Args:
        path: Directory to measure.

    Returns:
        Total size in GB.
    """
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    continue
    except OSError as exc:
        log.warning("library_scan_dir_size_error", path=str(path), exc_info=True, error=str(exc))
    return total / (1024**3)


def extract_nfo_ids(nfo_path: Path) -> tuple[str | None, str | None]:
    """Extract TMDB and IMDB IDs from a valid NFO file.

    Args:
        nfo_path: Path to .nfo file (must exist and be valid XML).

    Returns:
        Tuple of (tmdb_id, imdb_id). Either can be None.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
        tmdb_id = None
        imdb_id = None
        for uid in root.iter("uniqueid"):
            uid_type = uid.get("type", "").lower()
            text = (uid.text or "").strip()
            if not text:
                continue
            if uid_type == "tmdb":
                tmdb_id = text
            elif uid_type == "imdb":
                imdb_id = text
        return tmdb_id, imdb_id
    except (ET.ParseError, OSError) as exc:
        log.debug("library_scan_nfo_ids_parse_error", nfo=str(nfo_path), exc_info=True, error=str(exc))
        return None, None


def _check_artwork_movie(movie_dir: Path, title: str) -> ArtworkStatus:
    """Check which movie artwork files exist.

    Args:
        movie_dir: Path to movie directory.
        title: Movie title (used in filename pattern).

    Returns:
        ArtworkStatus with presence flags.
    """
    return ArtworkStatus(
        poster=(movie_dir / f"{title}-poster.jpg").exists(),
        fanart=(movie_dir / f"{title}-fanart.jpg").exists(),
        landscape=(movie_dir / f"{title}-landscape.jpg").exists(),
        banner=(movie_dir / f"{title}-banner.jpg").exists(),
        clearlogo=(movie_dir / f"{title}-clearlogo.png").exists(),
        clearart=(movie_dir / f"{title}-clearart.png").exists(),
        discart=(movie_dir / f"{title}-discart.png").exists(),
    )


def _check_artwork_tvshow(show_dir: Path) -> ArtworkStatus:
    """Check which TV show artwork files exist (fixed names).

    Args:
        show_dir: Path to TV show directory.

    Returns:
        ArtworkStatus with presence flags.
    """
    return ArtworkStatus(
        poster=(show_dir / "poster.jpg").exists(),
        fanart=(show_dir / "fanart.jpg").exists(),
        landscape=(show_dir / "landscape.jpg").exists(),
        banner=(show_dir / "banner.jpg").exists(),
        clearlogo=(show_dir / "clearlogo.png").exists(),
        clearart=(show_dir / "clearart.png").exists(),
        characterart=(show_dir / "characterart.png").exists(),
    )


def _detect_issues(
    media_dir: Path,
    title: str,
    year: int | None,
    is_tvshow: bool,
    category_id: str = "",
) -> tuple[list[str], bool]:
    """Detect common issues in a media directory.

    Args:
        media_dir: Path to media directory.
        title: Parsed title.
        year: Parsed year (None if missing).
        is_tvshow: Whether this is a TV show.
        category_id: Category ID (used to skip year check for audiobooks).

    Returns:
        Tuple of (issues list, actors_dir_present bool).
    """
    issues: list[str] = []
    actors_dir = False

    for item in media_dir.iterdir():
        name = item.name

        # .actors directory
        if name == ".actors" and item.is_dir():
            actors_dir = True
            issues.append(ISSUE_ACTORS_DIR)
            continue

        # Junk files (including macOS resource forks "._*")
        if name in _JUNK_FILES or name.startswith("._"):
            issues.append(ISSUE_JUNK_FILES)
            continue

        # Empty subdirectories
        if item.is_dir() and not any(item.iterdir()):
            if is_tvshow and not SEASON_DIR_RE.match(name):
                # Non-season empty dir in a tvshow (likely release artifact)
                issues.append(ISSUE_RELEASE_ARTIFACT)
            else:
                # Empty dir in a movie, or empty season dir in a tvshow
                issues.append(ISSUE_EMPTY_SUBDIR)

        # NTFS-unsafe names
        if _NTFS_ILLEGAL.search(name):
            issues.append(ISSUE_NTFS_UNSAFE)

    # Bad directory naming (no year) — skip for audiobooks (author naming is normal)
    if year is None and category_id != AUDIOBOOKS:
        issues.append(ISSUE_BAD_DIR_NAME)

    # Deduplicate (e.g. multiple junk files -> one issue)
    return list(dict.fromkeys(issues)), actors_dir


def _scan_seasons(show_dir: Path) -> list[SeasonInfo]:
    """Scan TV show season directories.

    Args:
        show_dir: Path to TV show directory.

    Returns:
        List of SeasonInfo, sorted by season number.
    """
    seasons: list[SeasonInfo] = []
    for subdir in sorted(show_dir.iterdir()):
        if not subdir.is_dir() or not SEASON_DIR_RE.match(subdir.name):
            continue
        # Extract season number from "Saison XX"
        parts = subdir.name.split()
        try:
            season_num = int(parts[-1])
        except (ValueError, IndexError):
            continue

        # Count video files and NFO files
        episode_count = 0
        nfo_count = 0
        for f in subdir.iterdir():
            if f.is_file():
                ext = f.suffix.lstrip(".").lower()
                if ext in _VIDEO_EXTENSIONS:
                    episode_count += 1
                elif ext == "nfo":
                    nfo_count += 1

        # Check season poster
        poster_name = f"season{season_num:02d}-poster.jpg"
        has_poster = (show_dir / poster_name).exists()

        seasons.append(
            SeasonInfo(
                number=season_num,
                path=str(subdir),
                episode_count=episode_count,
                has_poster=has_poster,
                episodes_with_nfo=nfo_count,
            )
        )

    return seasons


def scan_movie_dir(movie_dir: Path, disk_id: str, category_id: str) -> LibraryScanItem:
    """Scan a single movie directory and collect metadata.

    Args:
        movie_dir: Path to the movie directory.
        disk_id: Disk identifier (e.g. "disk_a").
        category_id: Category ID (e.g. "movies").

    Returns:
        LibraryScanItem with all collected metadata.
    """
    title, year = parse_title_year(movie_dir.name)

    # NFO check
    nfo_path = movie_dir / f"{title}.nfo"
    nfo_valid = is_nfo_complete(nfo_path)
    tmdb_id, imdb_id = (None, None)
    if nfo_valid:
        tmdb_id, imdb_id = extract_nfo_ids(nfo_path)

    nfo = NfoStatus(
        present=nfo_path.exists(),
        valid=nfo_valid,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
    )

    artwork = _check_artwork_movie(movie_dir, title)
    issues, actors_dir = _detect_issues(movie_dir, title, year, is_tvshow=False, category_id=category_id)
    size_gb = _dir_size_gb(movie_dir)

    return LibraryScanItem(
        path=str(movie_dir),
        disk=disk_id,
        category=category_id,
        media_type="movie",
        title=title,
        year=year,
        folder_size_gb=round(size_gb, 3),
        nfo=nfo,
        artwork=artwork,
        actors_dir=actors_dir,
        issues=issues,
        seasons=None,
        scanned_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def scan_tvshow_dir(show_dir: Path, disk_id: str, category_id: str) -> LibraryScanItem:
    """Scan a single TV show directory and collect metadata.

    Args:
        show_dir: Path to the TV show directory.
        disk_id: Disk identifier (e.g. "disk_a").
        category_id: Category ID (e.g. "tv_shows").

    Returns:
        LibraryScanItem with all collected metadata including seasons.
    """
    title, year = parse_title_year(show_dir.name)

    # NFO check (tvshow.nfo is a fixed name)
    nfo_path = show_dir / "tvshow.nfo"
    nfo_valid = is_nfo_complete(nfo_path)
    tmdb_id, imdb_id = (None, None)
    if nfo_valid:
        tmdb_id, imdb_id = extract_nfo_ids(nfo_path)

    nfo = NfoStatus(
        present=nfo_path.exists(),
        valid=nfo_valid,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
    )

    artwork = _check_artwork_tvshow(show_dir)
    issues, actors_dir = _detect_issues(show_dir, title, year, is_tvshow=True, category_id=category_id)
    seasons = _scan_seasons(show_dir)
    size_gb = _dir_size_gb(show_dir)

    return LibraryScanItem(
        path=str(show_dir),
        disk=disk_id,
        category=category_id,
        media_type="tvshow",
        title=title,
        year=year,
        folder_size_gb=round(size_gb, 3),
        nfo=nfo,
        artwork=artwork,
        actors_dir=actors_dir,
        issues=issues,
        seasons=seasons,
        scanned_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def _nfo_status_string(nfo: NfoStatus) -> DbNfoStatus:
    """Map a NfoStatus to the DB status string.

    Args:
        nfo: NfoStatus from library scan.

    Returns:
        ``'valid'`` when NFO is present and valid, ``'invalid'`` when present
        but invalid, ``'missing'`` when absent.
    """
    if not nfo.present:
        return "missing"
    if nfo.valid:
        return "valid"
    return "invalid"


def _artwork_inventory(artwork: ArtworkStatus) -> ArtworkInventory:
    """Convert an ArtworkStatus to the DB-friendly ArtworkInventory Pydantic model.

    Args:
        artwork: ArtworkStatus populated by the library scanner.

    Returns:
        :class:`~personalscraper.indexer.schema.ArtworkInventory` instance.
    """
    return ArtworkInventory(
        poster=artwork.poster,
        fanart=artwork.fanart,
        landscape=artwork.landscape,
        banner=artwork.banner,
        clearlogo=artwork.clearlogo,
        clearart=artwork.clearart,
        discart=artwork.discart,
        characterart=artwork.characterart,
    )


def _upsert_media_item(
    conn: sqlite3.Connection,
    scan_item: LibraryScanItem,
    now_s: int,
) -> int:
    """Upsert a ``media_item`` row from a library scan result.

    Converts a :class:`LibraryScanItem` into a :class:`MediaItemRow` and calls
    :func:`personalscraper.indexer.repos.item_repo.upsert`.  Also writes the
    ``dispatch_path`` and ``dispatch_disk`` flex attributes so consumers that
    rely on them (``trailers/scanner.py``, ``indexer/release_linker.py``) can
    locate the on-disk media directory regardless of whether the item was
    discovered by the dispatch layer or by this library scanner.  The
    attribute key prefix is historical (originally introduced by dispatch);
    the values stored here are the same shape — absolute media-dir path and
    config-level disk ID.

    Args:
        conn: Open SQLite connection.
        scan_item: Library scan result for one media directory.
        now_s: Current time in unix epoch seconds (stamped on ``date_created``
            and ``date_modified`` for new rows).

    Returns:
        PK of the inserted or updated ``media_item`` row.
    """
    import unicodedata  # noqa: PLC0415

    from personalscraper.indexer.repos.item_repo import (  # noqa: PLC0415
        _ATTR_DISPATCH_DISK,
        _ATTR_DISPATCH_NORM_TITLE,
        _ATTR_DISPATCH_PATH,
    )
    from personalscraper.indexer.schema import ItemAttributeRow  # noqa: PLC0415

    kind: MediaItemKind = "show" if scan_item.media_type == "tvshow" else "movie"
    nfo_status = _nfo_status_string(scan_item.nfo)
    artwork_json = _artwork_inventory(scan_item.artwork).model_dump_json()

    # Migration 005 (provider-ids feature) consolidated the flat
    # ``tmdb_id`` / ``imdb_id`` / ``tvdb_id`` columns into a single
    # ``external_ids_json`` column. Build the JSON here from whatever
    # the NFO surfaced.
    import json as _json  # noqa: PLC0415

    eids: dict[str, dict[str, str | None]] = {}
    if scan_item.nfo.tmdb_id and scan_item.nfo.tmdb_id.isdigit():
        eids["tmdb"] = {"series_id": scan_item.nfo.tmdb_id, "episode_id": None}
    if scan_item.nfo.imdb_id:
        eids["imdb"] = {"series_id": scan_item.nfo.imdb_id, "episode_id": None}
    external_ids_json = _json.dumps(eids) if eids else "{}"

    row = MediaItemRow(
        id=0,
        kind=kind,
        title=scan_item.title,
        title_sort=scan_item.title,  # stripped sort key is handled by scraper (7.2+)
        original_title=None,
        year=scan_item.year,
        category_id=scan_item.category,
        external_ids_json=external_ids_json,
        ratings_json=None,
        canonical_provider=None,
        nfo_status=nfo_status,
        artwork_json=artwork_json,
        date_created=now_s,
        date_modified=now_s,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )
    item_id = _item_repo.upsert(conn, row)

    # Persist dispatch flex attributes so trailers, release_linker, and the
    # dispatch index rebuild can locate the media directory and look it up by
    # normalized title.  Without ``dispatch_normalized_title`` items inserted
    # by this scanner are invisible to ``find_by_normalized_name`` /
    # ``list_all_dispatch_items`` (both INNER JOIN on that key), which would
    # silently break the trailers cross-disk index after a clean DB rebuild.
    # Normalization mirrors ``dispatch.media_index._normalize_key``: NFC,
    # lowercase, stripped — APFS / macFUSE-NTFS may otherwise differ on
    # decomposed accents.
    norm_title = unicodedata.normalize("NFC", scan_item.title).lower().strip()
    for key, value in (
        (_ATTR_DISPATCH_PATH, scan_item.path),
        (_ATTR_DISPATCH_DISK, scan_item.disk),
        (_ATTR_DISPATCH_NORM_TITLE, norm_title),
    ):
        _item_repo.upsert_attr(conn, ItemAttributeRow(item_id=item_id, key=key, value=value))

    # Persist the directory-hygiene issue tags into ``item_issue`` so the
    # report layer (and any downstream maintenance UI) can surface them
    # without re-walking the disks.  We replace the row's whole issue set
    # on every scan: a previously-flagged issue that has since been
    # cleaned up (e.g. .actors/ removed by ``library-clean``) must drop
    # off the report on the next scan.
    conn.execute("DELETE FROM item_issue WHERE item_id = ?", (item_id,))
    if scan_item.issues:
        conn.executemany(
            "INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) VALUES (?, ?, NULL, ?)",
            [(item_id, issue, now_s) for issue in scan_item.issues],
        )

    return item_id


def _upsert_seasons_and_episodes(
    conn: sqlite3.Connection,
    item_id: int,
    seasons: list[SeasonInfo],
) -> None:
    """Insert ``season`` and ``episode`` rows for a TV show.

    Skips inserting a season if a row with the same ``(item_id, number)`` pair
    already exists (idempotent on repeated calls).

    Args:
        conn: Open SQLite connection.
        item_id: PK of the owning ``media_item`` (kind must be ``'show'``).
        seasons: Season list from :func:`scan_tvshow_dir`.
    """
    for season_info in seasons:
        # Idempotent insert: rely on UNIQUE(item_id, number) at the schema
        # level and follow up with one SELECT to recover the id (works
        # whether we just inserted or matched an existing row).  Replaces
        # the previous SELECT-then-INSERT round-trip pair with one INSERT
        # OR IGNORE + one SELECT — same row count, half the trips on the
        # already-indexed insert path.
        season_row = SeasonRow(
            id=0,
            item_id=item_id,
            number=season_info.number,
            episode_count=season_info.episode_count,
            has_poster=int(season_info.has_poster),
            episodes_with_nfo=season_info.episodes_with_nfo,
        )
        tv_repo.insert_season(conn, season_row, ignore_conflict=True)
        season_id_row = conn.execute(
            "SELECT id FROM season WHERE item_id = ? AND number = ?",
            (item_id, season_info.number),
        ).fetchone()
        if season_id_row is None:
            # Should not happen — INSERT OR IGNORE + UNIQUE guarantees this row exists.
            continue
        season_id: int = season_id_row[0]

        # Insert episode stubs in a single batched executemany; UNIQUE
        # (season_id, number) makes INSERT OR IGNORE idempotent across
        # repeated scans without per-episode SELECTs.
        if season_info.episode_count > 0:
            conn.executemany(
                "INSERT OR IGNORE INTO episode (season_id, number, title) VALUES (?, ?, NULL)",
                [(season_id, ep_num) for ep_num in range(1, season_info.episode_count + 1)],
            )


def _build_disk_row(disk_cfg: DiskConfig, now_s: int) -> DiskRow:
    """Build a :class:`DiskRow` from a :class:`DiskConfig`.

    Uses the ``DiskConfig.id`` as both the UUID and label so that the library
    scanner's DB rows can be correlated back to config identifiers.

    Args:
        disk_cfg: Config entry for a storage disk.
        now_s: Current unix epoch seconds (stamped on ``last_seen_at``).

    Returns:
        :class:`DiskRow` with ``id=0`` (to be assigned by the DB on insert).
    """
    return DiskRow(
        id=0,
        uuid=disk_cfg.id,
        label=disk_cfg.id,
        mount_path=str(disk_cfg.path),
        last_seen_at=now_s,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )


def _ensure_disk_row(conn: sqlite3.Connection, disk_cfg: DiskConfig, now_s: int) -> DiskRow:
    """Ensure a ``disk`` row exists for the given config entry and return it.

    Performs a SELECT-then-INSERT pattern: if a disk with the same UUID
    (i.e. ``DiskConfig.id``) already exists it is returned unchanged; otherwise
    a new row is inserted.

    Args:
        conn: Open SQLite connection.
        disk_cfg: Config entry for a storage disk.
        now_s: Current unix epoch seconds passed to :func:`_build_disk_row`.

    Returns:
        :class:`DiskRow` with the PK assigned by the DB.
    """
    existing = disk_repo.get_by_uuid(conn, disk_cfg.id)
    if existing is not None:
        return existing

    row = _build_disk_row(disk_cfg, now_s)
    disk_id = disk_repo.insert(conn, row)
    return DiskRow(
        id=disk_id,
        uuid=row.uuid,
        label=row.label,
        mount_path=row.mount_path,
        last_seen_at=row.last_seen_at,
        merkle_root=row.merkle_root,
        is_mounted=row.is_mounted,
        unreachable_strikes=row.unreachable_strikes,
    )


def scan_library(
    config: Config,
    conn: sqlite3.Connection,
    *,
    event_bus: EventBus,
) -> None:
    """Populate the indexer DB from a full walk of all mounted storage disks.

    For each media directory found on disk the function writes:

    * ``media_item`` — one row per movie / TV show directory.
    * ``season`` — one row per season directory found inside a TV show.
    * ``episode`` — one stub row per video file found in each season.
    * ``media_file`` / ``path`` — populated by delegating to
      :func:`personalscraper.indexer.scanner.scan` (full mode).
    * ``item_attribute`` — ``dispatch_path`` and ``dispatch_disk`` so that
      consumers (``trailers/scanner.py``, ``indexer/release_linker.py``) can
      locate the on-disk media directory for any indexed item.

    Disks that are not mounted (``disk_cfg.path`` does not exist) are skipped
    with a warning log.

    Args:
        config: Loaded pipeline :class:`~personalscraper.conf.models.Config`.
        conn: Open SQLite connection with all migrations applied.
        event_bus: Required :class:`EventBus` forwarded to the underlying
            indexer scan so disk-circuit and ``LibraryScanCompleted`` events
            reach the run's subscribers.
    """
    now_s = int(time.time())
    disk_rows: list[DiskRow] = []

    for disk_cfg in config.disks:
        # Skip unmounted disks.
        if not disk_cfg.path.exists():
            log.warning("library_scan_disk_not_mounted", disk=disk_cfg.id, path=str(disk_cfg.path))
            continue

        # Ensure a disk row exists in the DB so that indexer.scanner.scan()
        # can write media_file rows linked to it.
        disk_row = _ensure_disk_row(conn, disk_cfg, now_s)
        disk_rows.append(disk_row)

        for category_id in disk_cfg.categories:
            cat_cfg = config.category(category_id)
            category_dir = disk_cfg.path / cat_cfg.folder_name
            if not category_dir.is_dir():
                # Bumped from DEBUG to WARNING (2026-04-30): when a user
                # misconfigures categories[id].folder_name, every category
                # silently produces zero rows.  WARNING surfaces the
                # misconfig without flooding noisy logs in the common case
                # (the warning fires at most once per missing dir per scan).
                log.warning(
                    "library_scan_category_not_found",
                    category_dir=str(category_dir),
                    disk=disk_cfg.id,
                    category_id=category_id,
                    folder_name=cat_cfg.folder_name,
                )
                continue

            is_tvshow = category_id in TV_CATEGORY_IDS

            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                try:
                    if is_tvshow:
                        scan_item = scan_tvshow_dir(media_dir, disk_cfg.id, category_id)
                    else:
                        scan_item = scan_movie_dir(media_dir, disk_cfg.id, category_id)

                    item_id = _upsert_media_item(conn, scan_item, now_s)

                    # Insert season and episode stubs for TV shows.
                    if is_tvshow and scan_item.seasons:
                        _upsert_seasons_and_episodes(conn, item_id, scan_item.seasons)

                except OSError as exc:
                    log.warning(
                        "library_scan_item_error",
                        media_dir=str(media_dir),
                        exc_info=True,
                        error=str(exc),
                    )

    # Delegate file-level indexing to the indexer scanner so that media_file
    # and path rows are populated alongside the media_item rows created above.
    if disk_rows:
        # Allocate the next scan generation monotonically from scan_run so that
        # miss-strike escalation logic in the analyzer works correctly across
        # consecutive library walks (DESIGN §8.1).
        gen_row = conn.execute("SELECT COALESCE(MAX(generation), 0) FROM scan_run").fetchone()
        next_generation: int = (gen_row[0] or 0) + 1

        _indexer_scan(
            disks=disk_rows,
            mode=ScanMode.full,
            generation=next_generation,
            conn=conn,
            event_bus=event_bus,
        )
