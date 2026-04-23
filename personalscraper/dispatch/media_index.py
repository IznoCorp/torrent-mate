"""JSON-based media index for cross-disk media tracking.

Maintains an index of all media items across storage disks.
Supports exact lookup, fuzzy matching (via fuzzy_match_score), atomic
save, and full rebuild from disk scans.

IndexEntry.category and IndexEntry.disk store canonical IDs
(e.g. "movies", "drive_a") rather than legacy French labels ("films",
"Disk1"). MediaIndex.load() detects legacy format (FR labels) and
migrates in-memory via V14_LABEL_TO_ID from conf.migration. Disk names
(Disk1..Disk4) are migrated to lowercase IDs (disk_1..disk_4) for
indexes that predate the Config-driven disk IDs.

Index file path must be supplied explicitly; the old ``settings.data_dir``
default is no longer supported.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from personalscraper.io_utils import atomic_write_json

if TYPE_CHECKING:
    from personalscraper.conf.models import CategoryConfig, DiskConfig, FuzzyMatchConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Legacy label detection helpers (imported lazily to avoid circular imports)
# ---------------------------------------------------------------------------

# Legacy disk name → current disk ID mapping.
# The old disk_scanner used "Disk1".."Disk4" as names; the current config uses
# free-form IDs. This mapping covers the canonical legacy setup only.
_V14_DISK_NAME_TO_ID: dict[str, str] = {
    "Disk1": "disk_1",
    "Disk2": "disk_2",
    "Disk3": "disk_3",
    "Disk4": "disk_4",
}

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


def _is_v14_format(entries: dict[str, Any]) -> bool:
    """Detect whether raw index data is in legacy format (FR category labels).

    Samples up to 10 entries and checks whether any ``category`` value
    appears in the V14_LABEL_TO_ID keys (French labels like "films", "series").

    Args:
        entries: Raw dict loaded from JSON, before IndexEntry construction.

    Returns:
        True if the data looks like legacy format.
    """
    from personalscraper.conf.migration import V14_LABEL_TO_ID

    for _i, entry_data in enumerate(entries.values()):
        if _i >= 10:
            break
        cat = entry_data.get("category", "")
        if cat in V14_LABEL_TO_ID:
            return True
    return False


def _migrate_v14_entry(entry_data: dict[str, Any]) -> dict[str, Any]:
    """Migrate a single legacy index entry to current IDs in-place.

    Converts:
    - category: legacy FR label → category ID via V14_LABEL_TO_ID
    - disk: "Disk1".."Disk4" → "disk_1".."disk_4" (canonical legacy mapping)

    Unknown labels/names are kept as-is with a warning.

    Args:
        entry_data: Raw dict for one index entry (as read from JSON).

    Returns:
        Updated dict with current IDs.
    """
    from personalscraper.conf.migration import V14_LABEL_TO_ID

    data = dict(entry_data)

    # Migrate category label → ID
    cat = data.get("category", "")
    if cat in V14_LABEL_TO_ID:
        data["category"] = V14_LABEL_TO_ID[cat]
    else:
        logger.warning("media_index legacy migration: unknown category label %r — keeping as-is", cat)

    # Migrate disk name → ID (best-effort, canonical legacy names only)
    disk = data.get("disk", "")
    if disk in _V14_DISK_NAME_TO_ID:
        data["disk"] = _V14_DISK_NAME_TO_ID[disk]
    elif disk:
        # Already an ID (e.g. "drive_a") or unknown — keep as-is
        pass

    return data


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
    """JSON-based index of all media across storage disks.

    Provides exact and fuzzy lookups, atomic saves, and full rebuilds.
    Always works with canonical IDs; legacy-format files are migrated in-memory
    on first load and saved back in the current format.
    """

    def __init__(self, index_path: Path):
        """Initialize the index.

        Args:
            index_path: Path to the JSON index file. Must be supplied
                explicitly — the old ``settings.data_dir`` default is gone.
        """
        self._path = index_path
        self._entries: dict[str, IndexEntry] = {}

    def load(self) -> None:
        """Load the index from disk.

        Creates an empty index if the file doesn't exist.
        Rebuilds if the file is corrupted.
        Detects legacy format (FR labels) and migrates in-memory;
        the next ``save()`` call will persist the current format.
        """
        if not self._path.exists():
            self._entries = {}
            return

        try:
            raw: dict[str, Any] = json.loads(self._path.read_text(encoding="utf-8"))

            # Detect legacy format and migrate in-memory
            if _is_v14_format(raw):
                logger.info(
                    "media_index: detected legacy format in %s — migrating to current IDs in-memory",
                    self._path,
                )
                raw = {k: _migrate_v14_entry(v) for k, v in raw.items()}

            self._entries = {k: IndexEntry(**v) for k, v in raw.items()}
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.error(
                "Corrupted index %s: %s — starting fresh (risk of duplicates on disks)",
                self._path,
                exc,
            )
            self._entries = {}

    def save(self) -> None:
        """Save the index to disk atomically and durably.

        Always writes current format (category IDs, disk IDs). Uses
        ``atomic_write_json`` (tmp + fsync + rename + parent dir fsync)
        so the result survives a crash mid-write.
        """
        data = {k: asdict(v) for k, v in self._entries.items()}
        atomic_write_json(self._path, data)

    def find(
        self,
        name: str,
        media_type: str,
        fuzzy_config: FuzzyMatchConfig | None = None,
    ) -> IndexEntry | None:
        """Find a media entry by name.

        Strategy: exact normalized lookup first, then fuzzy matching
        with anti-false-positive guards (year, length ratio, adaptive
        threshold via fuzzy_match_score).

        Args:
            name: Media directory name to search.
            media_type: "movie" or "tvshow" to filter results.
            fuzzy_config: Optional thresholds from ``Config.fuzzy_match``.
                Defaults applied when None.

        Returns:
            Matching IndexEntry, or None if not found.
        """
        key = _normalize_key(name)

        # Exact lookup
        if key in self._entries:
            entry = self._entries[key]
            if entry.media_type == media_type:
                return entry

        # Fuzzy fallback with anti-false-positive guards
        try:
            from personalscraper.text_utils import fuzzy_match_score

            name_year = _extract_year(name)
            best_score = 0.0
            best_entry = None

            for _entry_key, entry in self._entries.items():
                if entry.media_type != media_type:
                    continue
                entry_year = _extract_year(entry.name)
                score = fuzzy_match_score(
                    name,
                    entry.name,
                    query_year=name_year,
                    candidate_year=entry_year,
                    config=fuzzy_config,
                )
                if score is not None and score > best_score:
                    best_score = score
                    best_entry = entry

            return best_entry
        except ImportError:
            logger.warning("rapidfuzz not available — fuzzy matching disabled, exact match only")
            return None

    def add(self, entry: IndexEntry) -> None:
        """Add or update an entry in the index.

        Args:
            entry: Index entry to add (must use current IDs).
        """
        key = _normalize_key(entry.name)
        entry.last_updated = datetime.now(timezone.utc).isoformat()
        self._entries[key] = entry

    def rebuild(
        self,
        disk_configs: list[DiskConfig],
        categories: dict[str, CategoryConfig] | None = None,
    ) -> int:
        """Rebuild the index by scanning all mounted disks.

        Resolves each on-disk category directory to a canonical category ID. When
        ``categories`` is supplied, the reverse map ``folder_name → id`` is
        used first — this is required whenever the disk layout uses configurable
        French folder names (``series``, ``films``, ``emissions``) that differ
        from the canonical IDs (``tv_shows``, ``movies``, ``tv_programs``).
        Falls back to treating the directory name as the category ID for
        backward compatibility with setups where ``folder_name == category_id``.

        Args:
            disk_configs: List of DiskConfig objects (Pydantic, from conf.models).
            categories: Optional categories dict (``id → CategoryConfig``)
                used to resolve on-disk ``folder_name`` back to the canonical
                category ID. Without it, only directories whose names already
                match a canonical category ID are indexed.

        Returns:
            Total number of entries indexed.
        """
        self._entries = {}

        # Build folder_name → category_id reverse map (one-shot per rebuild).
        # Folder names are normalised for a case-insensitive filesystem match.
        folder_to_id: dict[str, str] = {}
        if categories:
            for cid, cat in categories.items():
                folder_to_id[cat.folder_name.lower()] = cid

        for config in disk_configs:
            if not config.path.exists():
                logger.info("Disk not mounted, skipping: %s", config.id)
                continue

            for category_dir in config.path.iterdir():
                if not category_dir.is_dir() or category_dir.name.startswith("."):
                    continue

                # Resolve dir name → canonical category ID.
                # Preference order: (1) configured folder_name reverse map,
                # (2) dir name already being a category ID (legacy fallback).
                resolved_id = folder_to_id.get(category_dir.name.lower())
                if resolved_id is None and category_dir.name in config.categories:
                    resolved_id = category_dir.name
                if resolved_id is None:
                    continue

                # Disk must accept this category (guard against cross-disk
                # scans that pick up categories not declared for that disk).
                if resolved_id not in config.categories:
                    continue

                # Infer media_type from category ID
                media_type = "tvshow" if resolved_id in _SERIES_CATEGORY_IDS else "movie"

                for media_dir in category_dir.iterdir():
                    if not media_dir.is_dir() or media_dir.name.startswith("."):
                        continue

                    entry = IndexEntry(
                        name=media_dir.name,
                        disk=config.id,
                        category=resolved_id,
                        path=str(media_dir),
                        media_type=media_type,
                    )
                    self.add(entry)

        logger.info("Index rebuilt: %d entries", len(self._entries))
        return len(self._entries)

    def remove_stale(self, disk_configs: list["DiskConfig"]) -> int:
        """Remove entries for paths that no longer exist.

        Args:
            disk_configs: List of DiskConfig to check (unused; kept for API compat).

        Returns:
            Number of entries removed.
        """
        stale_keys = []
        for key, entry in self._entries.items():
            if not Path(entry.path).exists():
                stale_keys.append(key)

        for key in stale_keys:
            del self._entries[key]

        if stale_keys:
            logger.info("Removed %d stale index entries", len(stale_keys))
        return len(stale_keys)

    @property
    def count(self) -> int:
        """Number of entries in the index."""
        return len(self._entries)
