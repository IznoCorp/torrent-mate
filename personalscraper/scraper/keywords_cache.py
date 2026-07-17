"""TMDB keywords cache with 30-day TTL and atomic writes.

Caches the results of TMDB /keywords API calls to avoid redundant network
requests. Entries expire after 30 days and are transparently refreshed by
the caller (TMDBClient + Scraper).

Cache file format:
    ``{data_dir}/tmdb_keywords_cache.json`` — JSON dict where each key is
    ``"movie_{tmdb_id}"`` or ``"tv_{tmdb_id}"`` and each value is::

        {"keywords": ["kw1", ...], "cached_at": "2024-01-15T10:30:00.123456"}

Persistence (load / corrupt-backup / atomic-save) is delegated to the shared
``core.json_ttl_cache`` primitives so the read-modify-write cycle has a single
source of truth (MECHANICAL-DUP-03). This cache keeps its own on-disk entry
shape (a bare ``keywords``/``cached_at`` pair, no ``ttl_seconds``) and its own
legacy naive-local timestamp compatibility, so it uses those primitives
directly rather than ``JsonTTLCache.get``/``.set``.

Corrupt-file protection (I8):
On a parse failure the corrupt file is backed up to
``tmdb_keywords_cache.corrupt-{ts}.json`` before ``{}`` is returned so the data
is preserved for forensic analysis.
"""

from datetime import datetime, timedelta
from pathlib import Path

from personalscraper.api._contracts import MediaType
from personalscraper.core.json_ttl_cache import (
    UTC,
    atomic_write_json,
    check_ttl,
    load_json_dict,
)
from personalscraper.logger import get_logger

log = get_logger("keywords_cache")

# Time-to-live: entries older than this are treated as cache misses.
_TTL = timedelta(days=30)

# Event-name prefix passed to the shared persistence primitives so log events
# stay namespaced to this cache (``keywords_cache_*``).
_EVENT_PREFIX = "keywords_cache"


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

    Load, corrupt-backup, and atomic-save are delegated to the shared
    ``core.json_ttl_cache`` primitives, so the backing file is never left in a
    partially-written state and a parse error backs up the corrupt file before
    the next ``set()`` overwrites prior entries.

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
        data = load_json_dict(self._path, logger=log, event_prefix=_EVENT_PREFIX)
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
        data = load_json_dict(self._path, logger=log, event_prefix=_EVENT_PREFIX)
        key = _cache_key(tmdb_id, media_type)
        # Always write tz-aware UTC: the legacy naive-local format on the read
        # side is preserved (see get()), but new entries no longer poison the
        # cache around DST transitions on local-tz machines.
        data[key] = {
            "keywords": list(keywords),
            "cached_at": datetime.now(UTC).isoformat(),
        }
        atomic_write_json(self._path, data)
