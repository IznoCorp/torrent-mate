"""TMDB keywords cache with 30-day TTL and atomic writes.

Caches the results of TMDB /keywords API calls to avoid redundant network
requests. Entries expire after 30 days and are transparently refreshed by
the caller (TMDBClient + Scraper).

Cache file format:
    ``{data_dir}/tmdb_keywords_cache.json`` — JSON dict where each key is
    ``"movie_{tmdb_id}"`` or ``"tv_{tmdb_id}"`` and each value is::

        {"keywords": ["kw1", ...], "cached_at": "2024-01-15T10:30:00.123456"}

Corrupt-file protection (I8):
``_load`` backs up the corrupt file to ``tmdb_keywords_cache.corrupt-{ts}.json``
before returning ``{}`` so the data is preserved for forensic analysis.  The
pattern mirrors ``TrailerStateStore._backup_corrupt`` in ``trailers/state.py``.
"""

import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from personalscraper.conf.classifier import MediaType
from personalscraper.logger import get_logger
from personalscraper.scraper.json_ttl_cache import UTC, check_ttl

log = get_logger("keywords_cache")

# Time-to-live: entries older than this are treated as cache misses.
_TTL = timedelta(days=30)


def _cache_key(tmdb_id: int, media_type: MediaType) -> str:
    """Build a cache key string for a TMDB item.

    Args:
        tmdb_id: TMDB numeric identifier.
        media_type: Either ``"movie"`` or ``"tv"``.

    Returns:
        A string such as ``"movie_12345"`` or ``"tv_67890"``.
    """
    return f"{media_type}_{tmdb_id}"


class KeywordsCache:
    """File-backed keyword cache with 30-day TTL and atomic writes.

    Stores keyword lists fetched from the TMDB /keywords endpoint so that
    repeated pipeline runs do not re-query the API for items whose keywords
    are already known and fresh.

    Atomic writes are implemented via ``tempfile.NamedTemporaryFile`` +
    ``os.replace`` — the backing file is never left in a partially-written
    state, even if the process is interrupted.

    On parse error, ``_load`` backs up the corrupt file before returning
    ``{}`` so the next ``set()`` does not silently destroy prior entries.

    Attributes:
        _path: Path to the backing ``tmdb_keywords_cache.json`` file.
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialize the cache backed by ``data_dir/tmdb_keywords_cache.json``.

        The backing file and its parent directory are created automatically on
        the first ``set()`` call.

        Args:
            data_dir: Directory that holds pipeline state files.
        """
        self._path = data_dir / "tmdb_keywords_cache.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, tmdb_id: int, media_type: MediaType) -> list[str] | None:
        """Return cached keywords or ``None`` on miss/expiry.

        Reads the backing JSON file on every call (the file is small and
        pipeline calls are infrequent, so no in-memory map is maintained).
        Returns ``None`` if:

        - The key is absent from the cache.
        - The ``cached_at`` timestamp cannot be parsed.
        - The entry is older than ``_TTL`` (30 days).

        Args:
            tmdb_id: TMDB numeric identifier.
            media_type: Either ``"movie"`` or ``"tv"``.

        Returns:
            List of keyword strings, or ``None`` on cache miss / expiry.
        """
        data = self._load()
        key = _cache_key(tmdb_id, media_type)
        entry = data.get(key)
        if entry is None:
            return None

        try:
            cached_at = datetime.fromisoformat(str(entry["cached_at"]))
        except (KeyError, ValueError):
            log.warning("keywords_cache_parse_error", cache_key=key)
            return None

        # New entries are written tz-aware UTC by set(); legacy cache files
        # may still hold naive-local timestamps. For legacy entries, compute
        # the elapsed duration in naive-local arithmetic and project it onto
        # UTC. This is best-effort across DST boundaries (the elapsed delta
        # can be off by 1h during the transition itself); legacy entries age
        # out within the 30-day TTL after this code ships.
        now_utc = datetime.now(UTC)
        if cached_at.tzinfo is None:
            elapsed_naive = datetime.now() - cached_at
            cached_at = now_utc - elapsed_naive

        if not check_ttl(cached_at, int(_TTL.total_seconds()), now=now_utc):
            return None

        raw_kws = entry.get("keywords", [])
        if not isinstance(raw_kws, list):
            return []
        return [str(k) for k in raw_kws]

    def set(self, tmdb_id: int, media_type: MediaType, keywords: list[str]) -> None:
        """Write or overwrite a cache entry atomically.

        Reads the existing cache, updates the entry for ``(tmdb_id, media_type)``,
        then writes the whole dict back via a temp file + ``os.replace`` so the
        backing file is never partially written.

        Args:
            tmdb_id: TMDB numeric identifier.
            media_type: Either ``"movie"`` or ``"tv"``.
            keywords: List of keyword name strings to cache.
        """
        data = self._load()
        key = _cache_key(tmdb_id, media_type)
        # Always write tz-aware UTC: the legacy naive-local format on the read
        # side is preserved (see get()), but new entries no longer poison the
        # cache around DST transitions on local-tz machines.
        data[key] = {
            "keywords": list(keywords),
            "cached_at": datetime.now(UTC).isoformat(),
        }
        self._atomic_save(data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _backup_corrupt(self, reason: str) -> None:
        """Copy the backing file aside before it gets overwritten by a fresh save.

        Without this, a parse failure followed by ``set()`` silently destroys
        every prior entry. The backup keeps a forensic copy at
        ``<name>.corrupt-<unix_ts>.json`` (preserving the ``.json`` suffix).

        Mirrors the pattern from ``TrailerStateStore._backup_corrupt`` in
        ``trailers/state.py``.

        Args:
            reason: Short tag used in the log (e.g. ``parse_error:JSONDecodeError``).
        """
        try:
            ts = int(time.time())
            backup = self._path.with_name(f"{self._path.stem}.corrupt-{ts}{self._path.suffix}")
            shutil.copy(self._path, backup)
            log.warning(
                "keywords_cache_corrupt_backup",
                original=str(self._path),
                backup=str(backup),
                reason=reason,
            )
        except OSError as exc:
            log.error(
                "keywords_cache_corrupt_backup_failed",
                path=str(self._path),
                error=str(exc),
                reason=reason,
            )

    def _load(self) -> dict[str, dict[str, object]]:
        """Read the backing file and return its contents as a dict.

        Returns an empty dict if the file does not exist or cannot be parsed.
        On parse error the corrupt file is backed up to
        ``<name>.corrupt-<unix_ts>.json`` before returning ``{}``.

        Returns:
            Parsed JSON dict (may be empty on error or missing file).
        """
        if not self._path.exists():
            return {}
        try:
            with self._path.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                self._backup_corrupt(reason="root_not_object")
                return {}
            return {k: v for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self._backup_corrupt(reason=f"parse_error:{type(exc).__name__}")
            log.warning("keywords_cache_read_error", path=str(self._path), error=str(exc))
            return {}

    def _atomic_save(self, data: dict[str, dict[str, object]]) -> None:
        """Write ``data`` to the backing file via a temporary file + os.replace.

        The write is atomic on POSIX systems: the temp file is fully written
        and flushed before ``os.replace`` performs the rename, so no reader
        can observe a partial write.

        Args:
            data: Dict to serialise as JSON.

        Raises:
            OSError: If the temp file cannot be created or the replace fails.
        """
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True)
        # delete=False so we can explicitly rename after flushing
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
            # Clean up orphaned temp file before re-raising
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
