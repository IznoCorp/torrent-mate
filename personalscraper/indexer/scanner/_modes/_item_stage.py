"""Unified item/season/episode/issue upsert stage for ScanMode.full.

Self-contained port of the ``media_item`` write path from
``personalscraper.library.scanner`` (functions ``_upsert_media_item``,
``_upsert_seasons_and_episodes``, ``_detect_issues``, ``_ensure_disk_row``,
``scan_movie_dir``, ``scan_tvshow_dir``). During the lib-fold Phase 2
parallel-path window this module duplicates that logic on purpose: both the
legacy ``library-scan`` path and the new ``library-index --mode full`` path must
produce byte-identical ``media_item`` rows (the Task 5 golden test asserts the
equality before Phase 3 deletes ``library/scanner.py``).

Exports
-------
build_item_row          Build a ``media_item`` column dict from parsed NFO inputs.
upsert_item_with_attrs  Write media_item (item_repo.upsert) + item_attribute + item_issue.
scan_and_stage_dir      High-level: parse the NFO in a media dir, detect issues, upsert.
_ensure_disk_row        DEV #50: guarantee a disk row exists before FK writes.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING, Any
from xml.etree import ElementTree as ET

from personalscraper._fs_utils import is_apple_double
from personalscraper.conf.ids import AUDIOBOOKS
from personalscraper.core.media_types import VIDEO_EXTENSIONS as _VIDEO_EXTENSIONS
from personalscraper.indexer.repos import disk_repo, item_repo, tv_repo
from personalscraper.indexer.scanner._modes._canonical import derive_canonical_provider
from personalscraper.indexer.schema import (
    ArtworkInventory,
    DiskRow,
    ItemAttributeRow,
    MediaItemKind,
    MediaItemRow,
    NfoStatus,
    SeasonRow,
)
from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
    ISSUE_NTFS_UNSAFE,
    ISSUE_RELEASE_ARTIFACT,
)
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import extract_nfo_metadata, is_nfo_complete, parse_title_year
from personalscraper.text_utils import JUNK_FILE_NAMES as _JUNK_FILES

if TYPE_CHECKING:
    from personalscraper.conf.models.disks import DiskConfig

log = get_logger("indexer.scanner.item_stage")

# NTFS-illegal characters — mirrors library.scanner._NTFS_ILLEGAL.
_NTFS_ILLEGAL = re.compile(r'[<>:"/\\|?*]')

# Issue types raised by the no-NFO folder-name fallback (scan_and_stage_dir).
# Free-form ``item_issue.type`` strings (the column carries no CHECK), distinct
# from the directory-hygiene constants imported from ``library.models``.
ISSUE_NFO_MISSING = "nfo_missing"
ISSUE_NFO_INCOMPLETE = "nfo_incomplete"

# Inverse map of ``scraper.nfo_generator._NFO_RATING_SOURCE_NAMES`` — kept in
# sync with ``nfo_utils._NFO_RATING_SOURCE_REVERSE`` so ``ratings_json`` stores
# the internal source-name shape the scraper / backfill produce.
_NFO_RATING_SOURCE_REVERSE: dict[str, str] = {
    "imdb": "imdb",
    "themoviedb": "tmdb",
    "tmdb": "tmdb",
    "rottentomatoes": "rotten_tomatoes",
    "rotten_tomatoes": "rotten_tomatoes",
    "metacritic": "metacritic",
    "trakt": "trakt",
}


# ---------------------------------------------------------------------------
# media_item row construction + write path
# ---------------------------------------------------------------------------


def build_item_row(
    *,
    title: str,
    kind: MediaItemKind,
    year: int | None,
    category_id: str,
    tvdb_id: str | None,
    tmdb_id: str | None,
    imdb_id: str | None = None,
    nfo_default: str | None = None,
    nfo_status: NfoStatus,
    artwork_json: str = "{}",
    ratings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a ``media_item`` column dict from parsed NFO inputs.

    Constructs ``external_ids_json`` from the provider IDs (mirroring
    ``library.scanner._upsert_media_item`` lines 645-652: only numeric
    ``tvdb`` / ``tmdb`` ids are persisted, ``imdb`` is stored verbatim,
    ``"{}"`` when no id is present) and resolves ``canonical_provider`` via
    the kind-deterministic SSOT :func:`derive_canonical_provider`.

    Args:
        title: Display title (folder-name title for the no-NFO fallback).
        kind: ``"movie"`` or ``"show"``.
        year: Release year, or ``None`` when unknown.
        category_id: Logical category ID from config.
        tvdb_id: TVDB series id surfaced from the NFO, or ``None``.
        tmdb_id: TMDB id surfaced from the NFO, or ``None``.
        imdb_id: IMDB id surfaced from the NFO, or ``None``.
        nfo_default: The ``<uniqueid default="true">`` family from the NFO,
            forwarded to :func:`derive_canonical_provider` for the WARN trail.
        nfo_status: ``"missing"``, ``"invalid"``, or ``"valid"``.
        artwork_json: Pre-serialised :class:`ArtworkInventory` JSON; defaults
            to the empty inventory ``"{}"``.
        ratings: Optional list of ``{source, score, votes}`` rating dicts;
            ``None`` or empty leaves ``ratings_json`` NULL.

    Returns:
        A dict keyed by the real post-migration-005 ``media_item`` columns,
        suitable for ``MediaItemRow(**row)``.
    """
    # Migration 005 (provider-ids feature) consolidated the flat
    # ``tmdb_id`` / ``imdb_id`` / ``tvdb_id`` columns into a single
    # ``external_ids_json`` column. Build the JSON from whatever the NFO
    # surfaced (parity with scanner.py:645-652).
    eids: dict[str, dict[str, str | None]] = {}
    if tvdb_id and tvdb_id.isdigit():
        eids["tvdb"] = {"series_id": tvdb_id, "episode_id": None}
    if tmdb_id and tmdb_id.isdigit():
        eids["tmdb"] = {"series_id": tmdb_id, "episode_id": None}
    if imdb_id:
        eids["imdb"] = {"series_id": imdb_id, "episode_id": None}
    external_ids_json = json.dumps(eids) if eids else "{}"

    # Ratings — populated from the NFO parse so post-scrape state lives in the
    # indexer DB instead of being write-only on the scraper side.
    ratings_json: str | None
    if ratings:
        ratings_json = json.dumps({"entries": ratings})
    else:
        ratings_json = None

    # Phase 14.1 (reopen 12.1) parity — block the canonical_provider regression
    # at the insertion source. Recompute deterministically from kind + IDs;
    # the NFO-declared default is honoured only for the disagreement WARN.
    canonical_provider = derive_canonical_provider(kind, tvdb_id, tmdb_id, nfo_default)

    return {
        "id": 0,
        "kind": kind,
        "title": title,
        "title_sort": title,  # stripped sort key handled by scraper (7.2+)
        "original_title": None,
        "year": year,
        "category_id": category_id,
        "external_ids_json": external_ids_json,
        "ratings_json": ratings_json,
        "canonical_provider": canonical_provider,
        "nfo_status": nfo_status,
        "artwork_json": artwork_json,
        "date_created": 0,
        "date_modified": 0,
        "date_metadata_refreshed": None,
        "is_locked": 0,
        "preferred_lang": "fr",
    }


def upsert_item_with_attrs(
    conn: sqlite3.Connection,
    row: dict[str, Any],
    attrs: dict[str, str | None],
    issues: list[dict[str, Any]] | None = None,
    *,
    now_s: int | None = None,
) -> int:
    """Write a media_item row plus its flex attributes and issue set.

    Idempotent on ``(kind, title)`` via :func:`item_repo.upsert` (the repo
    strips a trailing `` (YYYY)`` from the title). The ``date_created`` /
    ``date_modified`` placeholders carried in *row* are stamped with *now_s*
    just before the write. Each ``attrs`` pair is upserted via
    :func:`item_repo.upsert_attr` (``ON CONFLICT(item_id, key)``), then the
    whole issue set is **replaced**: ``DELETE FROM item_issue WHERE item_id=?``
    followed by ``INSERT OR IGNORE`` of each issue (parity with
    ``library.scanner._upsert_media_item`` lines 716-721).

    Args:
        conn: Open SQLite connection.
        row: Column dict produced by :func:`build_item_row`.
        attrs: ``key -> value`` flex attributes (e.g. the three
            ``item_repo._ATTR_DISPATCH_*`` keys).
        issues: Optional list of ``{"type": str, "detail": str | None}`` dicts
            to write into ``item_issue``. ``None`` replaces with the empty set.
        now_s: Unix epoch seconds stamped on the row + issue rows; defaults to
            ``int(time.time())``.

    Returns:
        PK of the inserted-or-updated ``media_item`` row.
    """
    stamp = int(time.time()) if now_s is None else now_s

    # Stamp the timestamp placeholders carried by build_item_row.
    write_row = dict(row)
    write_row["date_created"] = stamp
    write_row["date_modified"] = stamp

    item_id = item_repo.upsert(conn, MediaItemRow(**write_row))

    # Persist flex attributes (dispatch path/disk/normalized-title, ...) so
    # consumers that INNER JOIN on them (trailers cross-disk index, dispatch
    # media-index, release_linker) can locate the on-disk media directory.
    for key, value in attrs.items():
        item_repo.upsert_attr(conn, ItemAttributeRow(item_id=item_id, key=key, value=value))

    # Replace the row's whole issue set on every scan: a previously-flagged
    # issue that has since been cleaned up (e.g. .actors/ removed) must drop
    # off the report on the next scan.
    conn.execute("DELETE FROM item_issue WHERE item_id = ?", (item_id,))
    if issues:
        conn.executemany(
            "INSERT OR IGNORE INTO item_issue (item_id, type, detail, detected_at) VALUES (?, ?, ?, ?)",
            [(item_id, issue["type"], issue.get("detail"), stamp) for issue in issues],
        )

    return item_id


# ---------------------------------------------------------------------------
# Directory-hygiene issue detection (port of scanner.py:_detect_issues)
# ---------------------------------------------------------------------------


def _detect_issues(
    media_dir: Path,
    title: str,
    year: int | None,
    is_tvshow: bool,
    category_id: str = "",
) -> tuple[list[str], bool]:
    """Detect common directory-hygiene issues in a media directory.

    Verbatim port of ``library.scanner._detect_issues`` (lines 342-446).

    Args:
        media_dir: Path to the media directory.
        title: Parsed title (unused beyond signature parity with the source).
        year: Parsed year (``None`` if missing).
        is_tvshow: Whether this is a TV show directory.
        category_id: Category ID (used to skip the year check for audiobooks).

    Returns:
        Tuple of (deduplicated issue list, actors_dir_present bool).
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
        if name in _JUNK_FILES or is_apple_double(name):
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


# ---------------------------------------------------------------------------
# Artwork inventory (port of scanner.py:_check_artwork_* + _artwork_inventory)
# ---------------------------------------------------------------------------


def _artwork_inventory_movie(movie_dir: Path, title: str) -> ArtworkInventory:
    """Build the artwork inventory for a movie directory.

    Mirrors ``library.scanner._check_artwork_movie`` (title-prefixed filenames)
    folded directly into an :class:`ArtworkInventory`.

    Args:
        movie_dir: Path to the movie directory.
        title: Movie title (used in the filename pattern).

    Returns:
        Populated :class:`ArtworkInventory` for the movie.
    """
    return ArtworkInventory(
        poster=(movie_dir / f"{title}-poster.jpg").exists(),
        fanart=(movie_dir / f"{title}-fanart.jpg").exists(),
        landscape=(movie_dir / f"{title}-landscape.jpg").exists(),
        banner=(movie_dir / f"{title}-banner.jpg").exists(),
        clearlogo=(movie_dir / f"{title}-clearlogo.png").exists(),
        clearart=(movie_dir / f"{title}-clearart.png").exists(),
        discart=(movie_dir / f"{title}-discart.png").exists(),
    )


def _artwork_inventory_tvshow(show_dir: Path) -> ArtworkInventory:
    """Build the artwork inventory for a TV show directory.

    Mirrors ``library.scanner._check_artwork_tvshow`` (fixed filenames) folded
    directly into an :class:`ArtworkInventory`.

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        Populated :class:`ArtworkInventory` for the show.
    """
    return ArtworkInventory(
        poster=(show_dir / "poster.jpg").exists(),
        fanart=(show_dir / "fanart.jpg").exists(),
        landscape=(show_dir / "landscape.jpg").exists(),
        banner=(show_dir / "banner.jpg").exists(),
        clearlogo=(show_dir / "clearlogo.png").exists(),
        clearart=(show_dir / "clearart.png").exists(),
        characterart=(show_dir / "characterart.png").exists(),
    )


# ---------------------------------------------------------------------------
# Season / episode walk (port of scanner.py:_scan_seasons /
# _upsert_seasons_and_episodes / _read_episode_titles)
# ---------------------------------------------------------------------------


def _scan_seasons(show_dir: Path) -> list[SeasonRow]:
    """Scan a TV show's season directories into :class:`SeasonRow` rows.

    Verbatim port of ``library.scanner._scan_seasons`` (lines 399-444), but
    emits :class:`SeasonRow` (``item_id=0`` placeholder, filled at upsert)
    instead of the intermediate ``SeasonInfo``. The season directory's path is
    not stored on :class:`SeasonRow`; it is recovered by
    :func:`_upsert_seasons_and_episodes` from the show directory + season number.

    Args:
        show_dir: Path to the TV show directory.

    Returns:
        List of :class:`SeasonRow`, sorted by season number.
    """
    seasons: list[SeasonRow] = []
    for subdir in sorted(show_dir.iterdir()):
        if not subdir.is_dir() or not SEASON_DIR_RE.match(subdir.name):
            continue
        # Extract season number from the trailing token (e.g. "Saison 03").
        parts = subdir.name.split()
        try:
            season_num = int(parts[-1])
        except (ValueError, IndexError):
            continue

        # Count video files and NFO files.
        episode_count = 0
        nfo_count = 0
        for f in subdir.iterdir():
            if f.is_file():
                ext = f.suffix.lstrip(".").lower()
                if ext in _VIDEO_EXTENSIONS:
                    episode_count += 1
                elif ext == "nfo":
                    nfo_count += 1

        # Check season poster (lives at the show-dir level, not in the season dir).
        poster_name = f"season{season_num:02d}-poster.jpg"
        has_poster = (show_dir / poster_name).exists()

        seasons.append(
            SeasonRow(
                id=0,
                item_id=0,
                number=season_num,
                episode_count=episode_count,
                has_poster=int(has_poster),
                episodes_with_nfo=nfo_count,
            )
        )

    return seasons


def _read_episode_titles(season_dir: Path, episode_count: int) -> dict[int, str | None]:
    r"""Read ``<title>`` from each episode .nfo in a season directory.

    Verbatim port of ``library.scanner._read_episode_titles`` (lines 773-823).
    Pairs episode video files with their sibling NFO by stem and parses the
    ``<title>`` tag; files without a sibling NFO, an unparseable NFO, or an
    empty title map to ``None``.

    Args:
        season_dir: Path to the ``Saison NN/`` directory.
        episode_count: Number of episode video files expected (used to pre-size
            the result mapping).

    Returns:
        Mapping ``episode_number → title | None``.
    """
    out: dict[int, str | None] = {}
    if not season_dir.exists():
        return out
    try:
        files = list(season_dir.iterdir())
    except OSError:
        return out
    nfo_by_stem = {f.stem: f for f in files if f.suffix.lower() == ".nfo"}
    for video in files:
        if not video.is_file():
            continue
        if video.suffix.lstrip(".").lower() not in _VIDEO_EXTENSIONS:
            continue
        match = re.search(r"[sS](\d{1,2})[eE](\d{1,3})", video.name)
        if match is None:
            continue
        ep_num = int(match.group(2))
        nfo = nfo_by_stem.get(video.stem)
        if nfo is None:
            out.setdefault(ep_num, None)
            continue
        try:
            root = ET.parse(nfo).getroot()  # noqa: S314 — trusted NFO we wrote
        except (ET.ParseError, OSError) as exc:
            log.debug("indexer_item_stage_episode_nfo_parse_error", nfo=str(nfo), exc_info=True, error=str(exc))
            out.setdefault(ep_num, None)
            continue
        title_text = (root.findtext("title") or "").strip()
        out[ep_num] = title_text or None
    # Backfill missing episode numbers with None so callers iterating
    # ``range(1, episode_count+1)`` always get an entry.
    for n in range(1, episode_count + 1):
        out.setdefault(n, None)
    return out


def _upsert_seasons_and_episodes(
    conn: sqlite3.Connection,
    item_id: int,
    show_dir: Path,
    seasons: list[SeasonRow],
) -> None:
    """Insert/refresh ``season`` and ``episode`` rows for a TV show.

    Verbatim port of ``library.scanner._upsert_seasons_and_episodes``
    (lines 726-771): :func:`tv_repo.upsert_season` refreshes the denormalized
    counts on every scan, and episode stubs get their ``<title>`` from the
    sibling NFO via :func:`_read_episode_titles`.

    Args:
        conn: Open SQLite connection.
        item_id: PK of the owning ``media_item`` (kind must be ``"show"``).
        show_dir: Path to the show directory (used to locate season dirs).
        seasons: Season rows from :func:`_scan_seasons` (``item_id`` placeholder
            is overridden here).
    """
    for season in seasons:
        season_row = SeasonRow(
            id=0,
            item_id=item_id,
            number=season.number,
            episode_count=season.episode_count,
            has_poster=season.has_poster,
            episodes_with_nfo=season.episodes_with_nfo,
        )
        season_id = tv_repo.upsert_season(conn, season_row)

        if season.episode_count > 0:
            season_dir = show_dir / f"Saison {season.number:02d}"
            episode_titles = _read_episode_titles(season_dir, season.episode_count)
            conn.executemany(
                """
                INSERT INTO episode (season_id, number, title) VALUES (?, ?, ?)
                ON CONFLICT(season_id, number) DO UPDATE SET title = excluded.title
                """,
                [(season_id, ep_num, episode_titles.get(ep_num)) for ep_num in range(1, season.episode_count + 1)],
            )


# ---------------------------------------------------------------------------
# Disk-row guarantee (port of scanner.py:_build_disk_row / _ensure_disk_row)
# ---------------------------------------------------------------------------


def _build_disk_row(disk_cfg: DiskConfig, now_s: int) -> DiskRow:
    """Build a :class:`DiskRow` from a :class:`DiskConfig`.

    Verbatim port of ``library.scanner._build_disk_row`` (line 826). Uses
    ``DiskConfig.id`` as both the uuid and label fallback.

    Args:
        disk_cfg: Config entry for a storage disk.
        now_s: Unix epoch seconds stamped on ``last_seen_at``.

    Returns:
        :class:`DiskRow` with ``id=0`` (assigned by the DB on insert).
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
    """Ensure a ``disk`` row exists for the config entry and return it.

    Verbatim port of ``library.scanner._ensure_disk_row`` (line 851, DEV #50):
    SELECT-by-label (config-stable key set by both insertion paths) then INSERT
    if absent, so the bootstrap row (real VolumeUUID) is not duplicated.

    Args:
        conn: Open SQLite connection.
        disk_cfg: Config entry for a storage disk.
        now_s: Unix epoch seconds passed to :func:`_build_disk_row`.

    Returns:
        :class:`DiskRow` with the PK assigned by the DB.
    """
    existing = disk_repo.get_by_label(conn, disk_cfg.id)
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


# ---------------------------------------------------------------------------
# High-level directory scan + stage
# ---------------------------------------------------------------------------


def _nfo_metadata_for_dir(media_dir: Path, title: str, is_tvshow: bool) -> tuple[dict[str, Any], NfoStatus]:
    """Resolve the NFO for a media dir and return its metadata + DB status.

    Mirrors the NFO branch of ``library.scanner.scan_movie_dir`` /
    ``scan_tvshow_dir``: the show NFO is the fixed ``tvshow.nfo``; the movie NFO
    is ``<title>.nfo``. ``nfo_status`` follows ``_nfo_status_string`` (lines
    562-576): ``valid`` when present + complete, ``invalid`` when present but
    incomplete, ``missing`` when absent.

    Args:
        media_dir: Path to the media directory.
        title: Folder-name title (used to resolve the movie NFO filename).
        is_tvshow: Whether the directory is a TV show.

    Returns:
        Tuple of (NFO metadata dict from :func:`extract_nfo_metadata`,
        ``media_item.nfo_status`` value).
    """
    nfo_path = media_dir / "tvshow.nfo" if is_tvshow else media_dir / f"{title}.nfo"
    blank: dict[str, Any] = {
        "tmdb_id": None,
        "imdb_id": None,
        "tvdb_id": None,
        "canonical_provider": None,
        "ratings": [],
    }
    present = nfo_path.exists()
    valid = is_nfo_complete(nfo_path)
    meta = extract_nfo_metadata(nfo_path) if valid else blank

    nfo_status: NfoStatus
    if not present:
        nfo_status = "missing"
    elif valid:
        nfo_status = "valid"
    else:
        nfo_status = "invalid"
    return meta, nfo_status


def scan_and_stage_dir(
    conn: sqlite3.Connection,
    media_dir: Path,
    disk_cfg: DiskConfig,
    category_id: str,
    kind: MediaItemKind,
    now_s: int | None = None,
) -> int:
    """Scan a single media directory and stage its full DB end-state.

    High-level port that folds ``scan_movie_dir`` / ``scan_tvshow_dir`` +
    ``_upsert_media_item`` + ``_upsert_seasons_and_episodes`` into one call:

    1. Parse the directory name (``parse_title_year`` folder-name fallback).
    2. Resolve the NFO, detect directory-hygiene issues (:func:`_detect_issues`).
    3. Build + upsert the ``media_item`` row with the three
       ``_ATTR_DISPATCH_*`` flex attributes (path = abs media dir,
       disk = ``disk_cfg.id``, norm_title = NFC-lower-stripped title — parity
       with scanner.py lines 699-708).
    4. **Never drop** a NFO-less directory: it is still indexed via the
       folder-name fallback and flagged (``nfo_missing`` /  ``nfo_incomplete``).
    5. For shows, scan + upsert seasons and episode stubs.

    :func:`_ensure_disk_row` is called first so FK-bearing writes have a disk row.

    Args:
        conn: Open SQLite connection.
        media_dir: Absolute path to the movie / TV show directory.
        disk_cfg: Config entry for the owning storage disk.
        category_id: Logical category ID from config.
        kind: ``"movie"`` or ``"show"``.
        now_s: Unix epoch seconds stamped on the rows; defaults to
            ``int(time.time())``.

    Returns:
        PK of the inserted-or-updated ``media_item`` row.
    """
    stamp = int(time.time()) if now_s is None else now_s
    is_tvshow = kind == "show"

    # Ensure the disk row exists before any FK-bearing write.
    _ensure_disk_row(conn, disk_cfg, stamp)

    title, year = parse_title_year(media_dir.name)
    meta, nfo_status = _nfo_metadata_for_dir(media_dir, title, is_tvshow)

    if is_tvshow:
        artwork = _artwork_inventory_tvshow(media_dir)
    else:
        artwork = _artwork_inventory_movie(media_dir, title)

    hygiene_issues, _actors_dir = _detect_issues(media_dir, title, year, is_tvshow=is_tvshow, category_id=category_id)

    # Folder-name fallback flag: a NFO-less / incomplete dir is still indexed
    # (never silently dropped) but flagged so the report layer surfaces it.
    issues: list[dict[str, Any]] = [{"type": tag, "detail": None} for tag in hygiene_issues]
    if nfo_status == "missing":
        issues.append({"type": ISSUE_NFO_MISSING, "detail": None})
    elif nfo_status == "invalid":
        issues.append({"type": ISSUE_NFO_INCOMPLETE, "detail": None})

    row = build_item_row(
        title=title,
        kind=kind,
        year=year,
        category_id=category_id,
        tvdb_id=meta["tvdb_id"],
        tmdb_id=meta["tmdb_id"],
        imdb_id=meta["imdb_id"],
        nfo_default=meta["canonical_provider"],
        nfo_status=nfo_status,
        artwork_json=artwork.model_dump_json(),
        ratings=meta["ratings"],
    )

    # Dispatch flex attributes. Normalization mirrors
    # ``dispatch.media_index._normalize_key``: NFC, lowercase, stripped.
    norm_title = unicodedata.normalize("NFC", title).lower().strip()
    attrs: dict[str, str | None] = {
        item_repo._ATTR_DISPATCH_PATH: str(media_dir),
        item_repo._ATTR_DISPATCH_DISK: disk_cfg.id,
        item_repo._ATTR_DISPATCH_NORM_TITLE: norm_title,
    }

    item_id = upsert_item_with_attrs(conn, row, attrs, issues=issues, now_s=stamp)

    if is_tvshow:
        seasons = _scan_seasons(media_dir)
        if seasons:
            _upsert_seasons_and_episodes(conn, item_id, media_dir, seasons)

    return item_id
