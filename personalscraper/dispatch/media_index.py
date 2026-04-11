"""JSON-based media index for cross-disk media tracking.

Maintains an index of all media items across the 4 storage disks.
Supports exact lookup, fuzzy matching (via rapidfuzz), atomic save,
and full rebuild from disk scans.

Index file: ~/.personalscraper/media_index.json
"""

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

INDEX_PATH = Path("~/.personalscraper/media_index.json").expanduser()


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
                Defaults to ~/.personalscraper/media_index.json.
        """
        self._path = index_path or INDEX_PATH
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
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.warning("Corrupted index, starting fresh: %s", self._path)
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
        with rapidfuzz WRatio (threshold >= 85).

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

        # Fuzzy fallback
        try:
            from rapidfuzz import fuzz

            from personalscraper.text_utils import media_processor

            best_score = 0.0
            best_entry = None

            for entry_key, entry in self._entries.items():
                if entry.media_type != media_type:
                    continue
                score = fuzz.WRatio(
                    key, entry_key, processor=media_processor,
                )
                if score >= 85 and score > best_score:
                    best_score = score
                    best_entry = entry

            return best_entry
        except ImportError:
            logger.debug("rapidfuzz not available, skipping fuzzy matching")
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
                    media_type = "tvshow" if category.startswith("series") else "movie"

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
