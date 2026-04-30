"""Thin indexer-backed wrapper for cross-disk media tracking.

Replaces the old JSON-file ``MediaIndex`` with a wrapper over
``personalscraper.indexer`` repositories.  The public API
(``find``, ``add``, ``rebuild``, ``remove_stale``, ``load``, ``save``)
is preserved exactly; callers (``dispatch/dispatcher.py``,
``dispatch/run.py``) need zero behavioural change.

``load()`` and ``save()`` are no-ops: the SQLite DB has its own
lifecycle and does not need explicit flush/hydrate calls.

``media_index.json`` is no longer written or read.  If one is present on
disk it is silently ignored (a deprecation warning is logged once).  Run
``personalscraper library index --mode full`` to populate the indexer and
make dispatch decisions accurate on a fresh install.

On first run (empty DB), ``__init__`` triggers an automatic full rebuild
when a ``Config`` is supplied.  Subsequent ``__init__`` calls that find
existing ``media_item`` rows skip the rebuild.

IndexEntry.category and IndexEntry.disk always store canonical IDs
(e.g. ``"movies"``, ``"drive_a"``).
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.indexer.db import apply_migrations, open_db
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.repos.item_repo import (
    _ATTR_DISPATCH_DISK,
    _ATTR_DISPATCH_NORM_TITLE,
    _ATTR_DISPATCH_PATH,
)
from personalscraper.indexer.schema import ItemAttributeRow, MediaItemRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models import CategoryConfig, Config, DiskConfig, FuzzyMatchConfig

log = get_logger("media_index")

_YEAR_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")

# Categories that represent TV-like content (episodic/serialized)
_SERIES_CATEGORY_IDS = frozenset(
    {
        "tv_shows",
        "tv_shows_animation",
        "tv_shows_documentary",
        "anime",
        "tv_programs",
    }
)

# Path to the migration SQL scripts, relative to this package.
_MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "indexer" / "migrations"


def _extract_year(name: str) -> int | None:
    """Extract a year (19xx/20xx) from a media name.

    Args:
        name: Media directory name, possibly containing a year.

    Returns:
        The year as int, or None if not found.
    """
    match = _YEAR_PATTERN.search(name)
    return int(match.group(1)) if match else None


def _normalize_key(name: str) -> str:
    """Normalize a media name for index lookup.

    Applies NFC Unicode normalization, lowercases, and strips whitespace.
    NFC is required because staging (APFS/HFS) and NTFS disks may store
    the same visual name with different byte sequences (e.g. ``è`` as
    precomposed U+00E8 vs. decomposed ``e`` + U+0300). Without
    normalization the index would grow two keys for the same show.

    Args:
        name: Media directory name.

    Returns:
        Normalized key string.
    """
    return unicodedata.normalize("NFC", name).lower().strip()


def _media_type_to_kind(media_type: str) -> str:
    """Map dispatch ``media_type`` to indexer DB ``kind`` value.

    Args:
        media_type: Dispatch layer value — ``"movie"`` or ``"tvshow"``.

    Returns:
        Indexer DB value — ``"movie"`` or ``"show"``.
    """
    return "show" if media_type == "tvshow" else "movie"


def _kind_to_media_type(kind: str) -> str:
    """Map indexer DB ``kind`` value back to dispatch ``media_type``.

    Args:
        kind: Indexer DB value — ``"movie"`` or ``"show"``.

    Returns:
        Dispatch layer value — ``"movie"`` or ``"tvshow"``.
    """
    return "tvshow" if kind == "show" else "movie"


@dataclass
class IndexEntry:
    """A single media entry in the index.

    Category stores a category_id (e.g. "movies"), disk stores a disk_id
    (e.g. "drive_a" or "disk_1") — not legacy French labels/names.

    Attributes:
        name: Original directory name.
        disk: Disk identifier (disk_id from Config, e.g. "drive_a").
        category: Category ID (e.g. "movies").
        path: Full path on disk.
        media_type: "movie" or "tvshow".
        last_updated: ISO datetime of last update.
    """

    name: str
    disk: str
    category: str
    path: str
    media_type: str
    last_updated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MediaIndex:
    """Indexer-backed dispatcher cache of all media across storage disks.

    Wraps ``personalscraper.indexer`` SQLite repositories.  Provides the
    same exact-and-fuzzy lookup API as the former JSON-file implementation,
    delegating storage to ``media_item`` + ``item_attribute`` rows.

    ``load()`` and ``save()`` are intentional no-ops: the DB has its own
    lifecycle; explicit flushes are not needed.

    On first run (empty DB), if a ``Config`` is passed the constructor
    triggers an automatic full rebuild so that dispatch decisions are
    immediately accurate.  Subsequent instantiations with rows present
    skip the rebuild.

    The class implements the context manager protocol so it can be used
    with ``with MediaIndex(...) as idx:`` to guarantee the underlying
    SQLite connection is closed when the block exits.
    """

    def __init__(self, index_path: Path, *, config: Config | None = None) -> None:
        """Open the configured indexer database.

        ``index_path`` is accepted for backward compatibility with existing
        callers.  When *config* is supplied, ``config.indexer.db_path`` is the
        source of truth.  Without *config*, a ``*.db`` path is used directly;
        legacy JSON-style paths still resolve to ``index_path.parent / "library.db"``.

        If the DB is empty (no ``media_item`` rows) and ``config`` is
        supplied, a full rebuild is triggered automatically so that
        dispatch decisions are accurate from the very first run.

        If a legacy ``media_index.json`` file is found next to *index_path*,
        a one-time deprecation warning is logged; the file is NOT read.

        Args:
            index_path: Legacy path argument (ignored; kept for API compat).
            config: Optional Config used for the automatic first-run rebuild.
                If None and the DB is empty, a warning is logged and the
                rebuild is skipped (manual rebuild required).
        """
        # Use the configured indexer DB when available.  This keeps dispatch on
        # the same SQLite file as ``personalscraper library index`` and outbox
        # publishers even when paths.data_dir differs from indexer.db_path.
        configured_db_path = getattr(getattr(config, "indexer", None), "db_path", None)
        if isinstance(configured_db_path, Path):
            db_path = configured_db_path
        elif index_path.suffix == ".db":
            db_path = index_path
        else:
            db_path = index_path.parent / "library.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = open_db(db_path)
        apply_migrations(self._conn, _MIGRATIONS_DIR)

        # Surface the active indexer DB at INFO so a pipeline run can verify
        # the dispatcher is consulting the SQLite store and not a stale JSON.
        log.info("indexer.dispatch.opened", db_path=str(db_path))

        # Warn once if a legacy media_index.json is present alongside the DB.
        # The file is intentionally NOT read; users should run a full rebuild.
        legacy_json = index_path.parent / "media_index.json"
        if legacy_json.exists():
            log.warning(
                "indexer.legacy_json_found",
                message=(
                    "media_index.json found; it is no longer used — run "
                    "`personalscraper library index --mode full` to populate the indexer."
                ),
                path=str(legacy_json),
            )

        # First-run detection: trigger an automatic rebuild when the DB is empty.
        row_count = self._conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
        is_empty = (row_count[0] if row_count else 0) == 0

        if is_empty:
            if config is not None:
                log.info("indexer.config.no_index", message="Empty DB detected; triggering automatic rebuild.")
                self.rebuild(config.disks, categories=config.categories)
            else:
                log.warning(
                    "indexer.config.no_index",
                    message=("Empty DB detected but no Config provided to MediaIndex; manual rebuild required."),
                )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Safe to call multiple times: subsequent calls are no-ops.  After
        ``close()`` the instance must not be used for any further queries.
        """
        if not hasattr(self, "_conn"):
            return
        try:
            self._conn.close()
        except Exception as exc:  # noqa: BLE001 — defensive; log and swallow
            log.warning("media_index.close_error", error=str(exc), error_type=type(exc).__name__)

    def __enter__(self) -> "MediaIndex":
        """Enter the context manager.

        Returns:
            This ``MediaIndex`` instance.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the context manager and close the connection.

        Args:
            exc_type: Exception type, if any was raised inside the ``with`` block.
            exc_val: Exception instance, if any.
            exc_tb: Traceback object, if any.
        """
        self.close()

    def __del__(self) -> None:
        """Defensive finalizer: close the connection if the caller forgets.

        Called by the garbage collector when no more references exist.
        Should not be relied upon in production code — prefer the ``with``
        statement or an explicit ``close()`` call instead.
        """
        try:
            self.close()
        except Exception:  # noqa: BLE001 — __del__ must never raise
            pass

    # ------------------------------------------------------------------
    # No-op persistence shims (kept for backward compatibility)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """No-op: the SQLite DB has its own lifecycle; no explicit load needed."""

    def save(self) -> None:
        """No-op: writes are committed immediately; no explicit flush needed."""

    def find(
        self,
        name: str,
        media_type: str,
        fuzzy_config: FuzzyMatchConfig | None = None,
    ) -> IndexEntry | None:
        """Find a media entry by name.

        Strategy: exact normalized lookup first (via stored
        ``dispatch_normalized_title`` attribute), then fuzzy matching with
        anti-false-positive guards (year, length ratio, adaptive threshold
        via ``fuzzy_match_score``).

        Args:
            name: Media directory name to search.
            media_type: ``"movie"`` or ``"tvshow"`` to filter results.
            fuzzy_config: Optional thresholds from ``Config.fuzzy_match``.
                Defaults applied when None.

        Returns:
            Matching IndexEntry, or None if not found.
        """
        key = _normalize_key(name)
        kind = _media_type_to_kind(media_type)

        # Exact lookup via stored normalized-title attribute.
        result = item_repo.find_by_normalized_name(self._conn, key, kind)
        if result is not None:
            item_row, dispatch_disk, dispatch_path = result
            log.info(
                "indexer.dispatch.lookup_hit",
                name=name,
                media_type=media_type,
                match_type="exact",
                title=item_row.title,
                disk=dispatch_disk,
                category=item_row.category_id,
            )
            return IndexEntry(
                name=item_row.title,
                disk=dispatch_disk,
                category=item_row.category_id,
                path=dispatch_path,
                media_type=media_type,
                last_updated=datetime.fromtimestamp(item_row.date_modified, tz=timezone.utc).isoformat(),
            )

        # Fuzzy fallback with anti-false-positive guards.
        try:
            from personalscraper.text_utils import fuzzy_match_score

            name_year = _extract_year(name)
            best_score = 0.0
            best_entry: IndexEntry | None = None

            all_items = item_repo.list_all_dispatch_items(self._conn)
            for item_row, dispatch_disk, dispatch_path in all_items:
                if item_row.kind != kind:
                    continue
                entry_year = _extract_year(item_row.title)
                score = fuzzy_match_score(
                    name,
                    item_row.title,
                    query_year=name_year,
                    candidate_year=entry_year,
                    config=fuzzy_config,
                )
                if score is not None and score > best_score:
                    best_score = score
                    best_entry = IndexEntry(
                        name=item_row.title,
                        disk=dispatch_disk,
                        category=item_row.category_id,
                        path=dispatch_path,
                        media_type=_kind_to_media_type(item_row.kind),
                        last_updated=datetime.fromtimestamp(item_row.date_modified, tz=timezone.utc).isoformat(),
                    )

            if best_entry is not None:
                log.info(
                    "indexer.dispatch.lookup_hit",
                    name=name,
                    media_type=media_type,
                    match_type="fuzzy",
                    title=best_entry.name,
                    disk=best_entry.disk,
                    score=best_score,
                )
            else:
                log.info(
                    "indexer.dispatch.lookup_miss",
                    name=name,
                    media_type=media_type,
                    candidates_scanned=len(all_items),
                )
            return best_entry
        except ImportError:
            log.warning("fuzzy_match_disabled", reason="rapidfuzz_not_available")
            return None

    def add(self, entry: IndexEntry) -> None:
        """Add or update an entry in the index.

        First checks for an existing row with the same NFC-normalized name and
        kind via :func:`item_repo.find_by_normalized_name`.  If found, updates
        the existing ``media_item`` row in place (preserving its ``id``) so
        that NFC and NFD spellings of the same title converge to a single row.
        If not found, inserts a new row.

        Writes three ``item_attribute`` rows:
        ``dispatch_normalized_title``, ``dispatch_disk``, and ``dispatch_path``.

        Args:
            entry: Index entry to add (must use current canonical IDs).
        """
        now_ts = int(time.time())
        kind = _media_type_to_kind(entry.media_type)
        norm_key = _normalize_key(entry.name)

        # Check for an existing entry under the same normalized name to handle
        # NFC/NFD deduplication (e.g. storing NFD form then NFC form of the same
        # title must result in exactly one DB row).
        existing = item_repo.find_by_normalized_name(self._conn, norm_key, kind)
        if existing is not None:
            existing_row, _disk, _path = existing
            item_id = existing_row.id
            self._conn.execute(
                "UPDATE media_item SET category_id = ?, date_modified = ?, title = ? WHERE id = ?",
                (entry.category, now_ts, entry.name, item_id),
            )
        else:
            item_id = item_repo.upsert(
                self._conn,
                MediaItemRow(
                    id=0,
                    kind=kind,
                    title=entry.name,
                    title_sort=entry.name,
                    original_title=None,
                    year=_extract_year(entry.name),
                    category_id=entry.category,
                    tmdb_id=None,
                    imdb_id=None,
                    tvdb_id=None,
                    nfo_status=None,
                    artwork_json=None,
                    date_created=now_ts,
                    date_modified=now_ts,
                    date_metadata_refreshed=None,
                    is_locked=0,
                    preferred_lang="fr",
                ),
            )

        # Write dispatch-specific attributes (upsert replaces on conflict).
        for key, value in (
            (_ATTR_DISPATCH_NORM_TITLE, norm_key),
            (_ATTR_DISPATCH_DISK, entry.disk),
            (_ATTR_DISPATCH_PATH, entry.path),
        ):
            item_repo.upsert_attr(self._conn, ItemAttributeRow(item_id=item_id, key=key, value=value))

    def rebuild(
        self,
        disk_configs: list[DiskConfig],
        categories: dict[str, CategoryConfig] | None = None,
    ) -> int:
        """Rebuild the index by scanning all mounted disks.

        Deletes all dispatch-attributed items from the DB, then re-walks each
        disk directory and re-inserts entries via :meth:`add`.

        Resolves each on-disk category directory to a canonical category ID.
        When ``categories`` is supplied, the reverse map ``folder_name → id``
        is used first — required whenever the disk layout uses configurable
        French folder names (``series``, ``films``, ``emissions``) that differ
        from the canonical IDs.  Falls back to treating the directory name as
        the category ID for backward compatibility.

        Args:
            disk_configs: List of DiskConfig objects (Pydantic, from conf.models).
            categories: Optional categories dict (``id → CategoryConfig``)
                used to resolve on-disk ``folder_name`` back to the canonical
                category ID.

        Returns:
            Total number of entries indexed.
        """
        # Remove all previously dispatch-attributed items.
        for item_row, _disk, _path in item_repo.list_all_dispatch_items(self._conn):
            item_repo.remove_by_id(self._conn, item_row.id)

        # Build folder_name → category_id reverse map (one-shot per rebuild).
        folder_to_id: dict[str, str] = {}
        if categories:
            for cid, cat in categories.items():
                folder_to_id[cat.folder_name.lower()] = cid

        count = 0
        for config in disk_configs:
            if not config.path.exists():
                log.info("disk_not_mounted", disk=config.id)
                continue

            for category_dir in config.path.iterdir():
                if not category_dir.is_dir() or category_dir.name.startswith("."):
                    continue

                # Resolve dir name → canonical category ID.
                resolved_id = folder_to_id.get(category_dir.name.lower())
                if resolved_id is None and category_dir.name in config.categories:
                    resolved_id = category_dir.name
                if resolved_id is None:
                    continue

                if resolved_id not in config.categories:
                    continue

                media_type = "tvshow" if resolved_id in _SERIES_CATEGORY_IDS else "movie"

                for media_dir in category_dir.iterdir():
                    if not media_dir.is_dir() or media_dir.name.startswith("."):
                        continue

                    self.add(
                        IndexEntry(
                            name=media_dir.name,
                            disk=config.id,
                            category=resolved_id,
                            path=str(media_dir),
                            media_type=media_type,
                        )
                    )
                    count += 1

        log.info("index_rebuilt", entries=count)
        return count

    def remove_stale(self, disk_configs: list[DiskConfig]) -> int:
        """Remove entries for paths that no longer exist.

        Args:
            disk_configs: List of DiskConfig to check (unused; kept for API compat).

        Returns:
            Number of entries removed.
        """
        stale_count = 0
        for item_row, _disk, dispatch_path in item_repo.list_all_dispatch_items(self._conn):
            if dispatch_path and not Path(dispatch_path).exists():
                item_repo.remove_by_id(self._conn, item_row.id)
                stale_count += 1

        if stale_count:
            log.info("index_stale_removed", count=stale_count)
        return stale_count

    @property
    def count(self) -> int:
        """Number of dispatch-attributed entries in the index."""
        # Count via the DB: number of items with dispatch_normalized_title attribute.
        row = self._conn.execute(
            "SELECT COUNT(*) FROM item_attribute WHERE key = ?",
            (_ATTR_DISPATCH_NORM_TITLE,),
        ).fetchone()
        return int(row[0]) if row else 0
