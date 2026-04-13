"""JSON-based media index for cross-disk media tracking.

Maintains an index of all media items across the 4 storage disks.
Supports exact lookup, fuzzy matching (via fuzzy_match_score), atomic
save, and full rebuild from disk scans.

Index file: data_dir/media_index.json (configurable via DATA_DIR_NAME in .env).
"""

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_index_path() -> Path:
    """Return the default index file path from settings.

    Returns:
        Path to media_index.json inside the configured data directory.
    """
    from personalscraper.config import get_settings

    return get_settings().data_dir / "media_index.json"


_YEAR_PATTERN = re.compile(r"\b((?:19|20)\d{2})\b")

# Categories that represent TV-like content (episodic/serialized)
_SERIES_CATEGORIES = frozenset({
    "series", "series animations", "series documentaires",
    "series animes", "emissions",
})


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

    Lowercases and strips leading/trailing whitespace.

    Args:
        name: Media directory name.

    Returns:
        Normalized key string.
    """
    return name.lower().strip()


@dataclass
class IndexEntry:
    """A single media entry in the index.

    Attributes:
        name: Original directory name.
        disk: Disk identifier (e.g. "Disk1").
        category: Dispatch category (e.g. "films").
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
    """

    def __init__(self, index_path: Path | None = None):
        """Initialize the index.

        Args:
            index_path: Path to the JSON index file.
                Defaults to settings.data_dir/media_index.json.
        """
        self._path = index_path or _default_index_path()
        self._entries: dict[str, IndexEntry] = {}

    def load(self) -> None:
        """Load the index from disk.

        Creates an empty index if the file doesn't exist.
        Rebuilds if the file is corrupted.
        """
        if not self._path.exists():
            self._entries = {}
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._entries = {
                k: IndexEntry(**v) for k, v in data.items()
            }
        except (json.JSONDecodeError, TypeError, KeyError) as exc:
            logger.error(
                "Corrupted index %s: %s — starting fresh (risk of duplicates on disks)",
                self._path, exc,
            )
            self._entries = {}

    def save(self) -> None:
        """Save the index to disk with atomic write.

        Writes to a .tmp file first, then renames to avoid corruption.
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        data = {k: asdict(v) for k, v in self._entries.items()}
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, self._path)

    def find(self, name: str, media_type: str) -> IndexEntry | None:
        """Find a media entry by name.

        Strategy: exact normalized lookup first, then fuzzy matching
        with anti-false-positive guards (year, length ratio, adaptive
        threshold via fuzzy_match_score).

        Args:
            name: Media directory name to search.
            media_type: "movie" or "tvshow" to filter results.

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
                    name, entry.name,
                    query_year=name_year,
                    candidate_year=entry_year,
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
            entry: Index entry to add.
        """
        key = _normalize_key(entry.name)
        entry.last_updated = datetime.now(timezone.utc).isoformat()
        self._entries[key] = entry

    def rebuild(self, disk_configs: list) -> int:
        """Rebuild the index by scanning all mounted disks.

        Scans each disk's media directory for subdirectories and
        indexes them with their category (inferred from parent dir name).

        Args:
            disk_configs: List of DiskConfig objects.

        Returns:
            Total number of entries indexed.
        """
        self._entries = {}

        for config in disk_configs:
            if not config.path.exists():
                logger.info("Disk not mounted, skipping: %s", config.name)
                continue

            for category_dir in config.path.iterdir():
                if not category_dir.is_dir() or category_dir.name.startswith("."):
                    continue

                category = category_dir.name
                if category not in config.categories:
                    continue

                for media_dir in category_dir.iterdir():
                    if not media_dir.is_dir() or media_dir.name.startswith("."):
                        continue

                    # Infer media_type from category
                    media_type = "tvshow" if category in _SERIES_CATEGORIES else "movie"

                    entry = IndexEntry(
                        name=media_dir.name,
                        disk=config.name,
                        category=category,
                        path=str(media_dir),
                        media_type=media_type,
                    )
                    self.add(entry)

        logger.info("Index rebuilt: %d entries", len(self._entries))
        return len(self._entries)

    def remove_stale(self, disk_configs: list) -> int:
        """Remove entries for paths that no longer exist.

        Args:
            disk_configs: List of DiskConfig to check.

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
