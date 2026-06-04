"""Thin SQLite-backed wrapper for cross-disk media tracking.

Wraps ``personalscraper.indexer`` repositories for dispatcher lookups and
updates. The SQLite DB is the only persistence layer used by dispatch.

On first run (empty DB), ``__init__`` triggers an automatic full rebuild
when a ``Config`` is supplied and auto-rebuild is enabled.  Subsequent
``__init__`` calls that find existing ``media_item`` rows skip the rebuild.

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

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations, open_db
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.repos.item_repo import (
    _ATTR_DISPATCH_DISK,
    _ATTR_DISPATCH_NORM_TITLE,
    _ATTR_DISPATCH_PATH,
)
from personalscraper.indexer.scanner._modes._item_stage import (
    _nfo_metadata_for_dir,
    build_item_row,
    scan_and_stage_dir,
)
from personalscraper.indexer.schema import ItemAttributeRow, MediaItemKind, MediaItemRow
from personalscraper.logger import get_logger
from personalscraper.nfo_utils import parse_title_year

if TYPE_CHECKING:
    from personalscraper.conf.models.categories import CategoryConfig
    from personalscraper.conf.models.config import Config
    from personalscraper.conf.models.disks import DiskConfig
    from personalscraper.conf.models.fuzzy import FuzzyMatchConfig

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


def _target_year_matches(dispatch_path: str, item_year: int | None) -> bool:
    """Whether a stored dispatch target's folder year is compatible with the item.

    Defense-in-depth for the dispatch_path collision: a stale ``dispatch_path``
    attribute may point at a *different-year* folder than the matched item
    (e.g. a ``Scrubs (2026)`` row whose stored path is ``.../Scrubs (2001)``).
    Returns ``False`` only when BOTH the folder name and the item carry an
    *explicit* year and they differ — year-less targets / items pass through
    unchanged, mirroring the year-compatible dedup rule so a legitimate
    year-unknown folder is never rejected.

    Args:
        dispatch_path: Stored dispatch target path (may be empty).
        item_year: Release year of the matched media item, or ``None``.

    Returns:
        ``True`` when the target is acceptable; ``False`` when its folder year
        contradicts ``item_year``.
    """
    if not dispatch_path:
        return True
    _title, path_year = parse_title_year(Path(dispatch_path).name)
    return not (path_year is not None and item_year is not None and path_year != item_year)


def _media_type_to_kind(media_type: str) -> MediaItemKind:
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
    (e.g. "drive_a" or "disk_1").

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

    def __init__(
        self,
        db_path: Path,
        *,
        config: Config | None = None,
        auto_rebuild: bool = True,
        event_bus: EventBus,
    ) -> None:
        """Open the configured indexer database.

        When *config* is supplied, ``config.indexer.db_path`` is the source of
        truth. Without *config*, *db_path* is used directly.

        If the DB is empty (no ``media_item`` rows) and ``config`` is
        supplied, a full rebuild is triggered automatically so that
        dispatch decisions are accurate from the very first run.

        Args:
            db_path: Path to the SQLite indexer database.
            config: Optional Config used for the automatic first-run rebuild.
                If None and the DB is empty, a warning is logged and the
                rebuild is skipped (manual rebuild required).
            auto_rebuild: Whether to rebuild an empty DB during construction.
                Dry-run callers disable this and wrap any preview rebuild in a
                rollbackable savepoint.
            event_bus: Required :class:`EventBus` forwarded to ``open_db`` so
                its pre-open free-space guard emits ``DiskFullWarning`` on
                the run's subscriber-wired bus.
        """
        configured_db_path = getattr(getattr(config, "indexer", None), "db_path", None)
        if isinstance(configured_db_path, Path):
            db_path = configured_db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._conn = open_db(db_path, event_bus=event_bus)
        apply_migrations(self._conn, _MIGRATIONS_DIR)

        log.info("indexer.dispatch.opened", db_path=str(db_path))

        # First-run detection: trigger an automatic rebuild when the DB is empty.
        row_count = self._conn.execute("SELECT COUNT(*) FROM media_item").fetchone()
        is_empty = (row_count[0] if row_count else 0) == 0

        if is_empty and auto_rebuild:
            if config is not None:
                log.info("indexer.config.no_index", message="Empty DB detected; triggering automatic rebuild.")
                self.rebuild(config.disks, categories=config.categories)
            else:
                log.warning(
                    "indexer.config.no_index",
                    message=("Empty DB detected but no Config provided to MediaIndex; manual rebuild required."),
                )
        elif is_empty:
            log.info("indexer.config.no_index", message="Empty DB detected; automatic rebuild disabled.")

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

    def begin_preview(self) -> None:
        """Start a rollbackable preview transaction for dry-run index writes."""
        self._conn.execute("SAVEPOINT media_index_preview")

    def rollback_preview(self) -> None:
        """Rollback and release the dry-run preview transaction if active."""
        self._conn.execute("ROLLBACK TO SAVEPOINT media_index_preview")
        self._conn.execute("RELEASE SAVEPOINT media_index_preview")

    def find(
        self,
        name: str,
        media_type: str,
        fuzzy_config: FuzzyMatchConfig | None = None,
        media_dir: Path | None = None,
    ) -> IndexEntry | None:
        """Find a media entry by name, then by canonical provider id.

        Strategy, in order: (1) exact normalized lookup via the stored
        ``dispatch_normalized_title`` attribute; (2) **provider-id** lookup —
        when ``media_dir`` is supplied and the name missed, match an existing
        on-disk entry by the staging item's canonical provider id (parsed from
        ``media_dir``'s NFO), which recognises a show/movie already on disk
        under a different folder name (localized title, wrong year) as the same
        item; (3) fuzzy name matching with anti-false-positive guards (year,
        length ratio, adaptive threshold via ``fuzzy_match_score``). The
        provider-id pass sits between exact and fuzzy so it rescues a name miss
        with the reliable canonical identity before resorting to fuzzy guessing,
        and never overrides an exact-name hit.

        Args:
            name: Media directory name to search.
            media_type: ``"movie"`` or ``"tvshow"`` to filter results.
            fuzzy_config: Optional thresholds from ``Config.fuzzy_match``.
                Defaults applied when None.
            media_dir: Optional staging directory of the item being dispatched.
                When provided, its NFO is parsed for provider ids to enable the
                provider-id pass. ``None`` (or a folder with no usable id) skips
                that pass and behaves exactly as the prior name-only lookup.

        Returns:
            Matching IndexEntry, or None if not found.
        """
        key = _normalize_key(name)
        kind = _media_type_to_kind(media_type)

        # Exact lookup via stored normalized-title attribute.
        result = item_repo.find_by_normalized_name(self._conn, key, kind)
        if result is not None:
            item_row, dispatch_disk, dispatch_path = result
            if _target_year_matches(dispatch_path, item_row.year):
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
            # Stale denormalized target: the stored path's folder year
            # contradicts the matched item's year. Reject and fall through to
            # the provider-id / fuzzy passes (or a fresh placement) rather than
            # merge into a different-year folder (dispatch_path collision guard).
            log.warning(
                "indexer.dispatch.stale_target_rejected",
                name=name,
                media_type=media_type,
                match_type="exact",
                title=item_row.title,
                dispatch_path=dispatch_path,
                item_year=item_row.year,
            )

        # Provider-id fallback: a staging item already on disk under a
        # different folder name (localized title, wrong year) shares its
        # canonical provider id with the on-disk entry. Match on that id before
        # fuzzy guessing to avoid splitting the same show across two folders.
        if media_dir is not None:
            id_entry = self._find_by_provider_id(media_dir, kind, media_type)
            if id_entry is not None:
                return id_entry

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
                if not _target_year_matches(dispatch_path, item_row.year):
                    # Skip rows whose stored target folder year contradicts the
                    # row's own year (stale dispatch_path collision guard).
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

    def _find_by_provider_id(
        self,
        media_dir: Path,
        kind: MediaItemKind,
        media_type: str,
    ) -> IndexEntry | None:
        """Resolve an existing entry by the staging item's canonical provider id.

        Parses ``media_dir``'s NFO with the same primitive :meth:`add` uses
        (``_nfo_metadata_for_dir``) to obtain the item's provider ids, then
        queries :func:`item_repo.find_by_external_id` for an on-disk entry of
        the same ``kind`` sharing one of them. The canonical provider is tried
        first (TVDB for shows, TMDB for movies — the strict provider-family
        separation), then any other present id as a fallback. Each query keys a
        provider id against that *same* provider's column, so families never
        cross-contaminate.

        Args:
            media_dir: Staging directory of the item being dispatched.
            kind: Indexer kind (``"movie"`` or ``"show"``).
            media_type: Dispatch media_type (``"movie"`` or ``"tvshow"``) for
                the returned entry and the lookup log.

        Returns:
            The matching IndexEntry, or ``None`` when the staging folder carries
            no usable id or no on-disk entry shares one.
        """
        if not media_dir.is_dir():
            return None
        nfo_title, _year = parse_title_year(media_dir.name)
        meta, _status = _nfo_metadata_for_dir(media_dir, nfo_title, kind == "show")

        # Build provider→id candidates, canonical provider first then the rest.
        ordered = ["tvdb", "tmdb", "imdb"]
        canonical = meta.get("canonical_provider")
        if canonical in ordered:
            ordered.remove(canonical)
            ordered.insert(0, canonical)
        candidates = [(p, str(meta[f"{p}_id"])) for p in ordered if meta.get(f"{p}_id")]

        for provider, series_id in candidates:
            result = item_repo.find_by_external_id(self._conn, provider, series_id, kind)
            if result is None:
                continue
            item_row, dispatch_disk, dispatch_path = result
            if not _target_year_matches(dispatch_path, item_row.year):
                # Identity matched by provider id, but the row's stored target
                # folder is a different-year show — a stale attribute from the
                # year-blind dedup era. Skip it (dispatch_path collision guard).
                log.warning(
                    "indexer.dispatch.stale_target_rejected",
                    name=media_dir.name,
                    media_type=media_type,
                    match_type="external_id",
                    provider=provider,
                    title=item_row.title,
                    dispatch_path=dispatch_path,
                    item_year=item_row.year,
                )
                continue
            log.info(
                "indexer.dispatch.lookup_hit",
                name=media_dir.name,
                media_type=media_type,
                match_type="external_id",
                provider=provider,
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
            # Insert a *rich* row via the shared :mod:`_item_stage` primitives
            # so dispatch never re-introduces the NULL-canonical-provider
            # degradation (lib-fold Phase 3, single-creator decision #4): the
            # provider is derived deterministically from the on-disk NFO's
            # provider IDs, not hard-coded NULL. When the destination directory
            # exists (the production run path, where ``entry.path`` is a real
            # post-move folder) its NFO is read; otherwise blank metadata yields
            # a deterministic ``canonical_provider`` of ``None`` *only when no ID
            # is present* — the correct rich-row result, not the prior bug.
            media_dir = Path(entry.path)
            is_tvshow = kind == "show"
            if media_dir.is_dir():
                # Resolve the NFO basename the same way ``scan_and_stage_dir``
                # does: the movie NFO is ``<year-stripped-title>.nfo``, so the
                # lookup title must be the parsed folder title (``parse_title_year``)
                # — NOT ``entry.name`` (which still carries the `` (YYYY)`` suffix
                # and would miss the on-disk ``The Godfather.nfo`` file, yielding a
                # spurious ``nfo_status="missing"`` + NULL canonical_provider).
                # (lib-fold PR#31 review M5.)
                nfo_title, _nfo_year = parse_title_year(media_dir.name)
                meta, nfo_status = _nfo_metadata_for_dir(media_dir, nfo_title, is_tvshow)
            else:
                meta = {"tmdb_id": None, "imdb_id": None, "tvdb_id": None, "canonical_provider": None, "ratings": []}
                nfo_status = "missing"
            row = build_item_row(
                title=entry.name,
                kind=kind,
                # Parse the trailing ``(YYYY)`` (matching the scanner's
                # ``scan_and_stage_dir``) rather than ``_extract_year``'s
                # first-4-digit-anywhere: a title with a year in its body (e.g.
                # "Blade Runner 2049 (2017)") must store the release year 2017,
                # not 2049, so ``media_item.year`` stays consistent with the year
                # the dispatch guard parses from the folder name.
                year=parse_title_year(entry.name)[1],
                category_id=entry.category,
                tvdb_id=meta["tvdb_id"],
                tmdb_id=meta["tmdb_id"],
                imdb_id=meta["imdb_id"],
                nfo_default=meta["canonical_provider"],
                nfo_status=nfo_status,
                ratings=meta["ratings"],
            )
            row["date_created"] = now_ts
            row["date_modified"] = now_ts
            item_id = item_repo.upsert(self._conn, MediaItemRow(**row))

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
        disk directory and re-stages each media dir via the shared
        ``_item_stage.scan_and_stage_dir`` (full rich rows — seasons, episodes,
        ``item_issue``).

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

        now_ts = int(time.time())
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

                kind: MediaItemKind = "show" if resolved_id in _SERIES_CATEGORY_IDS else "movie"

                for media_dir in category_dir.iterdir():
                    if not media_dir.is_dir() or media_dir.name.startswith("."):
                        continue

                    # Per-directory OSError guard: a single unreadable dir
                    # (documented macFUSE/NTFS ghost-inode hazard) must NOT
                    # abort the whole dispatch index build. Mirrors the sibling
                    # ``_item_stage.stage_library_items`` try/except → warn →
                    # continue (lib-fold PR#31 review M1).
                    try:
                        # Delegate to the shared item stage — produces rich rows
                        # (canonical_provider derived from the NFO, seasons,
                        # issues and the three dispatch_* flex attributes)
                        # identical to ``library-index --mode full`` (lib-fold
                        # single-creator cutover). Prior to this, the
                        # per-directory write went through ``add()`` and
                        # persisted a NULL canonical provider.
                        item_id = scan_and_stage_dir(
                            self._conn,
                            media_dir,
                            disk_cfg=config,
                            category_id=resolved_id,
                            kind=kind,
                            now_s=now_ts,
                        )
                        # Dispatch rows key on the FULL folder name (incl. year)
                        # so the dispatch exact-match lookup (``find`` →
                        # ``_normalize_key``) and ``add()`` dedup find them.
                        # ``scan_and_stage_dir`` stores the YEAR-STRIPPED indexer
                        # norm_title (golden/library-index parity); dispatch
                        # overrides it here to its own full-name convention so a
                        # later ``add()`` of the same item dedups instead of
                        # inserting a duplicate ``media_item`` (lib-fold PR#31
                        # review M2).
                        item_repo.upsert_attr(
                            self._conn,
                            ItemAttributeRow(
                                item_id=item_id,
                                key=_ATTR_DISPATCH_NORM_TITLE,
                                value=_normalize_key(media_dir.name),
                            ),
                        )
                        count += 1
                    except OSError:
                        log.warning("dispatch_rebuild_item_error", media_dir=str(media_dir), exc_info=True)
                        continue

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
