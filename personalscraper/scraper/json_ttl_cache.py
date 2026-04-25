"""Generic file-backed JSON cache with per-entry TTL.

Extracted from ``keywords_cache.py`` to serve as a shared primitive for
TMDB video responses, YouTube search results, and any future cached data.

Cache file format: a JSON object where each key maps to::

    {
        "value":       <any JSON-serialisable value>,
        "cached_at":   "2026-04-23T03:12:04.123456",  # UTC ISO 8601
        "ttl_seconds": 86400
    }

Entries with ``cached_at`` older than ``ttl_seconds`` are treated as cache
misses. Writes are atomic: temp file + ``os.replace``.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

UTC = timezone.utc


def check_ttl(
    cached_at: datetime,
    ttl_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if ``cached_at`` is within ``ttl_seconds`` of ``now``.

    Shared helper used by both ``JsonTTLCache`` and
    ``scraper/keywords_cache.py`` so TTL arithmetic has a single source of
    truth. All datetimes must be timezone-aware (UTC recommended). A naive
    ``cached_at`` is promoted to UTC for backward compatibility with pre-UTC
    cache files written by earlier ``keywords_cache`` versions.

    Args:
        cached_at: Timestamp stored alongside the cached value. Naive values
            are treated as UTC.
        ttl_seconds: Entry lifetime in seconds (``0`` means always expired).
        now: Override for ``datetime.now(UTC)`` in tests. Must be aware if
            provided.

    Returns:
        ``True`` if the entry is still fresh (elapsed < ttl_seconds),
        ``False`` otherwise.
    """
    if cached_at.tzinfo is None:
        cached_at = cached_at.replace(tzinfo=UTC)
    current = now if now is not None else datetime.now(UTC)
    return (current - cached_at).total_seconds() < ttl_seconds


class JsonTTLCache:
    """Generic file-backed key/value cache with per-entry TTL.

    Stores arbitrary JSON-serialisable values. Each entry carries its own
    ``ttl_seconds`` so callers can mix short-lived and long-lived entries
    in the same backing file.

    Atomic writes are implemented via ``tempfile.NamedTemporaryFile`` +
    ``os.replace`` — the backing file is never left partially written.

    Attributes:
        _path: Absolute Path to the backing JSON file.
    """

    def __init__(self, path: Path) -> None:
        """Initialize the cache backed by ``path``.

        The file is created on the first ``set()`` call. The parent directory
        must exist; it is NOT created automatically.

        Args:
            path: Absolute path to the backing JSON file.
        """
        self._path = path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Return the cached value or ``None`` on miss / expiry.

        Args:
            key: Cache key string.

        Returns:
            The stored value, or ``None`` if the key is absent, the entry
            has expired, or the backing file cannot be parsed.
        """
        data = self._load()
        entry = data.get(key)
        if entry is None:
            return None

        try:
            cached_at = datetime.fromisoformat(str(entry["cached_at"]))
            ttl_seconds = int(entry["ttl_seconds"])
        except (KeyError, ValueError, TypeError):
            logger.warning("Cannot parse cache entry for key %r — treating as miss", key)
            return None

        if not check_ttl(cached_at, ttl_seconds):
            return None

        return entry.get("value")

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Write or overwrite a cache entry atomically.

        Args:
            key: Cache key string.
            value: JSON-serialisable value to store.
            ttl_seconds: Entry lifetime in seconds from now.
        """
        data = self._load()
        data[key] = {
            "value": value,
            "cached_at": datetime.now(UTC).isoformat(),
            "ttl_seconds": ttl_seconds,
        }
        self._atomic_save(data)

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache.

        A no-op if the key does not exist.

        Args:
            key: Cache key to remove.
        """
        data = self._load()
        if key in data:
            del data[key]
            self._atomic_save(data)

    def compact(self) -> None:
        """Remove all expired entries from the backing file.

        Reads the file, drops expired entries, and writes back. A no-op if
        the file does not exist.
        """
        data = self._load()
        now = datetime.now(UTC)
        fresh: dict[str, Any] = {}
        for key, entry in data.items():
            try:
                cached_at = datetime.fromisoformat(str(entry["cached_at"]))
                ttl_seconds = int(entry["ttl_seconds"])
                if check_ttl(cached_at, ttl_seconds, now=now):
                    fresh[key] = entry
            except (KeyError, ValueError, TypeError):
                # Malformed entry — drop it during compaction
                logger.debug("Dropping malformed cache entry during compact: %r", key)
        if len(fresh) != len(data):
            self._atomic_save(fresh)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        """Read the backing file and return its parsed contents.

        Returns an empty dict if the file does not exist or cannot be parsed.

        Returns:
            Parsed JSON dict; empty dict on any error.
        """
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                return {}
            return {k: v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Cannot read cache %s: %s — starting fresh", self._path, exc)
            return {}

    def _atomic_save(self, data: dict[str, Any]) -> None:
        """Write ``data`` to the backing file via temp file + os.replace.

        Args:
            data: Dict to serialise as JSON.

        Raises:
            OSError: If the temp file cannot be created or the replace fails.
        """
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name

        try:
            os.replace(tmp_path, self._path)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
