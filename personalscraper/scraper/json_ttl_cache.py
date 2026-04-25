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

Concurrent-write safety (I7):
``set``, ``invalidate``, and ``compact`` hold an exclusive advisory lock on a
sibling ``.lock`` file for the duration of their read-modify-write cycle via
``fcntl.flock(LOCK_EX | LOCK_NB)`` with a bounded retry loop.  The lock
prevents two concurrent processes (e.g. a cron pipeline and a manual CLI
invocation) from interleaving their read-modify-write cycles and silently
dropping each other's entries.  On non-Unix platforms (Windows) the ``fcntl``
module is absent and best-effort atomic writes are used instead.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

from personalscraper.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

UTC = timezone.utc

# ---------------------------------------------------------------------------
# fcntl import — optional, not available on Windows
# ---------------------------------------------------------------------------
try:
    import fcntl as _fcntl

    _FCNTL_AVAILABLE = True
except ImportError:  # pragma: no cover — Windows only
    _fcntl = None  # type: ignore[assignment]
    _FCNTL_AVAILABLE = False
    warnings.warn(
        "fcntl is unavailable on this platform — JsonTTLCache will use best-effort atomic writes without a file lock.",
        stacklevel=1,
    )

# Bounded lock-acquisition parameters — match state.py for consistency.
_LOCK_MAX_ATTEMPTS = 3
_LOCK_RETRY_SLEEP_SEC = 0.5


def check_ttl(
    cached_at: datetime,
    ttl_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    """Return True if ``cached_at`` is within ``ttl_seconds`` of ``now``.

    Shared helper used by both ``JsonTTLCache`` and
    ``scraper/keywords_cache.py`` so TTL arithmetic has a single source of
    truth. All datetimes must be timezone-aware (UTC recommended).

    A naive ``cached_at`` is promoted to UTC via ``replace(tzinfo=UTC)``.
    **WARNING for legacy callers**: this works correctly only when the naive
    timestamp was *written* in UTC. ``keywords_cache.py`` historically wrote
    naive *local* timestamps via ``datetime.now().isoformat()``; on non-UTC
    machines, calling this helper directly with such timestamps would
    misrepresent them and produce a wrong elapsed duration (especially across
    DST boundaries). ``keywords_cache`` therefore converts local-naive
    timestamps to UTC-aware values *before* calling ``check_ttl()`` by
    preserving the naive-local elapsed duration explicitly. New caches should
    write UTC-aware timestamps natively (as ``JsonTTLCache.set()`` does).

    Args:
        cached_at: Timestamp stored alongside the cached value. Aware values
            recommended; naive values are treated as UTC (see warning above).
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

    Read-modify-write operations (``set``, ``invalidate``, ``compact``) hold
    an exclusive ``fcntl`` advisory lock on a sibling ``.lock`` file for the
    duration of the operation so concurrent processes cannot drop entries.

    Attributes:
        _path: Absolute Path to the backing JSON file.
        _lock_path: Path to the advisory lock file (sibling ``.lock``).
    """

    def __init__(self, path: Path) -> None:
        """Initialize the cache backed by ``path``.

        The file and its parent directory are created on the first ``set()``
        call.

        Args:
            path: Absolute path to the backing JSON file.
        """
        self._path = path
        self._lock_path = path.with_suffix(".lock")

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
        except (KeyError, ValueError, TypeError) as exc:
            logger.warning("json_ttl_cache_entry_malformed", key=key, error=str(exc))
            return None

        if not check_ttl(cached_at, ttl_seconds):
            return None

        return entry.get("value")

    def set(self, key: str, value: Any, ttl_seconds: int) -> None:
        """Write or overwrite a cache entry atomically.

        Acquires an exclusive advisory lock on the sibling ``.lock`` file for
        the duration of the read-modify-write cycle so concurrent processes do
        not drop each other's entries.

        Args:
            key: Cache key string.
            value: JSON-serialisable value to store.
            ttl_seconds: Entry lifetime in seconds from now.
        """
        self._locked_update(
            lambda data: data.__setitem__(
                key,
                {
                    "value": value,
                    "cached_at": datetime.now(UTC).isoformat(),
                    "ttl_seconds": ttl_seconds,
                },
            )
        )

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache.

        A no-op if the key does not exist.

        Args:
            key: Cache key to remove.
        """

        def _remove(data: dict[str, Any]) -> None:
            data.pop(key, None)

        self._locked_update(_remove)

    def compact(self) -> None:
        """Remove all expired entries from the backing file.

        Reads the file, drops expired entries, and writes back. A no-op if
        the file does not exist.
        """
        now = datetime.now(UTC)

        def _drop_expired(data: dict[str, Any]) -> None:
            expired_keys = []
            for k, entry in data.items():
                try:
                    cached_at = datetime.fromisoformat(str(entry["cached_at"]))
                    ttl_secs = int(entry["ttl_seconds"])
                    if not check_ttl(cached_at, ttl_secs, now=now):
                        expired_keys.append(k)
                except (KeyError, ValueError, TypeError) as exc:
                    # Malformed entry — drop during compaction.
                    logger.debug("json_ttl_cache_entry_dropped_during_compact", key=k, error=str(exc))
                    expired_keys.append(k)
            for k in expired_keys:
                del data[k]

        self._locked_update(_drop_expired)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _acquire_lock(self, lock_fh: Any) -> None:
        """Acquire an exclusive non-blocking flock with a bounded retry budget.

        Mirrors the pattern from ``TrailerStateStore._acquire_lock`` in
        ``trailers/state.py`` (C7 fix).  Attempts ``_LOCK_MAX_ATTEMPTS`` times
        with ``_LOCK_RETRY_SLEEP_SEC`` between each attempt.

        Args:
            lock_fh: Open file handle to the ``.lock`` sibling file.

        Raises:
            OSError: If the lock cannot be acquired within the retry budget.
        """
        assert _fcntl is not None  # caller gates on _FCNTL_AVAILABLE
        for attempt in range(_LOCK_MAX_ATTEMPTS):
            try:
                _fcntl.flock(lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                return  # Lock acquired.
            except OSError:
                # LOCK_NB raises BlockingIOError (OSError subclass) when the
                # lock is held by another process.
                if attempt < _LOCK_MAX_ATTEMPTS - 1:
                    time.sleep(_LOCK_RETRY_SLEEP_SEC)
        # Budget exhausted — surface as an OSError so the caller degrades
        # gracefully (skip locking, still write best-effort).
        raise OSError(
            f"json_ttl_cache: could not acquire lock on {self._lock_path} after {_LOCK_MAX_ATTEMPTS} attempts"
        )

    def _locked_update(self, mutate: Any) -> None:
        """Read the backing file, apply ``mutate(data)``, and write back.

        Acquires the exclusive advisory lock before reading so the full
        read-modify-write cycle is serialised against concurrent processes.
        Falls back to unlocked best-effort on non-Unix platforms or when the
        lock cannot be acquired.

        Args:
            mutate: Callable that mutates the ``data`` dict in place.  The
                return value is ignored; side effects on ``data`` are used.
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self._lock_path.open("a") as lock_fh:
                    try:
                        self._acquire_lock(lock_fh)
                    except OSError:
                        # Could not acquire lock — fall back to best-effort.
                        logger.warning(
                            "json_ttl_cache_lock_failed",
                            lock_path=str(self._lock_path),
                            hint="falling back to unlocked write",
                        )
                        data = self._load()
                        mutate(data)
                        self._atomic_save(data)
                        return
                    try:
                        data = self._load()
                        mutate(data)
                        self._atomic_save(data)
                    finally:
                        _fcntl.flock(lock_fh, _fcntl.LOCK_UN)
            except OSError as exc:
                # Lock-file open / UNLOCK failures — best-effort write.
                logger.warning(
                    "json_ttl_cache_lock_error",
                    lock_path=str(self._lock_path),
                    error=str(exc),
                    hint="falling back to unlocked write",
                )
                data = self._load()
                mutate(data)
                self._atomic_save(data)
        else:
            # Best-effort on non-Unix platforms.
            data = self._load()
            mutate(data)
            self._atomic_save(data)

    def _backup_corrupt(self, reason: str) -> None:
        """Copy the backing file aside before it gets overwritten by a fresh save.

        Without this, a parse failure followed by ``set()`` silently destroys
        every prior entry. The backup keeps a forensic copy at
        ``<path>.corrupt-<unix_ts>.json`` (preserving the ``.json`` suffix so
        the file remains recognisable as a JSON cache).

        Args:
            reason: Short tag used in the log (e.g. ``parse_error:JSONDecodeError``).
        """
        try:
            # Include the original suffix so the forensic copy is recognisable.
            ts = int(time.time())
            backup = self._path.with_name(f"{self._path.stem}.corrupt-{ts}{self._path.suffix}")
            shutil.copy(self._path, backup)
            logger.warning(
                "json_ttl_cache_corrupt_backup",
                original=str(self._path),
                backup=str(backup),
                reason=reason,
            )
        except OSError as exc:
            logger.error(
                "json_ttl_cache_corrupt_backup_failed",
                path=str(self._path),
                error=str(exc),
                reason=reason,
            )

    def _load(self) -> dict[str, Any]:
        """Read the backing file and return its parsed contents.

        Returns an empty dict if the file does not exist or cannot be parsed.
        On parse error, the corrupt file is backed up to a sibling
        ``<name>.corrupt-<ts>.json`` before returning ``{}``.

        Returns:
            Parsed JSON dict; empty dict on any error.
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
            logger.warning(
                "json_ttl_cache_load_failed",
                path=str(self._path),
                error=str(exc),
                hint="starting with empty cache",
            )
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
