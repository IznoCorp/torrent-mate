"""Trailer state tracking — persistent JSON store with composite keys and retry policy.

Implements DESIGN §7 (State tracking), §8 (lifecycle GC and orphan purge), and
§12 (concurrency with fcntl.flock). The state file lives at
``.data/trailers_state.json`` relative to the project root (default; configurable
via ``config.trailers.state_file``); callers pass the absolute path to
``TrailerStateStore.__init__``.

Key design decisions:
- Atomic writes with fsync durability via :func:`atomic_write_json`.
- ``fcntl.flock(LOCK_EX)`` on a sibling ``.lock`` file prevents torn writes
  when multiple ``personalscraper trailers download`` processes run concurrently.
  Falls back to best-effort write on non-Unix platforms where ``fcntl`` is absent.
  The Windows fallback warning fires at *import time*, not on first call —
  callers wrapping the import in try/except should be aware.
- All timestamps are stored as UTC ISO 8601 strings; ``TrailerState`` is frozen
  and validates tz-aware datetimes at construction.
- ``BOT_DETECTED`` status is exempt from retry-after (always retried on next run).
"""

from __future__ import annotations

import errno as _errno_mod
import hashlib
import json
import shutil
import subprocess
import time
import unicodedata
import warnings
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from personalscraper.io_utils import atomic_write_json
from personalscraper.logger import get_logger

log = get_logger(__name__)

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
        "fcntl is unavailable on this platform — TrailerStateStore will use "
        "best-effort atomic writes without a file lock.",
        stacklevel=1,
    )

UTC = timezone.utc

_STATE_VERSION = 1

# Bounded lock-acquisition parameters (C7).
_LOCK_MAX_ATTEMPTS = 3
_LOCK_RETRY_SLEEP_SEC = 0.5


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TrailerStepFailed(Exception):
    """Raised by the pipeline when the trailers step returns status=error.

    Only raised when ``continue_on_trailer_error`` is False (the default).
    Caught by the CLI's ``run`` command handler, which exits with code 2 so
    the caller (e.g. a launchd job or CI script) can distinguish a
    trailers-specific abort from the generic exit-1 for partial pipeline errors.
    """


class TrailerStateLocked(Exception):
    """Raised when the state-file lock cannot be acquired within the retry budget.

    Two concurrent ``personalscraper trailers`` processes contend on the same
    ``.lock`` file.  After ``_LOCK_MAX_ATTEMPTS`` non-blocking attempts (each
    separated by ``_LOCK_RETRY_SLEEP_SEC`` seconds), the caller gives up and
    raises this exception rather than blocking indefinitely.

    Attributes:
        lock_path: Path to the advisory lock file.
        holder_pid: PID of the process currently holding the lock, or ``None``
            if ``lsof`` is unavailable or returns no output.
    """

    def __init__(self, lock_path: Path, holder_pid: int | None = None) -> None:
        """Initialise with the lock path and optional holder PID.

        Args:
            lock_path: Path to the advisory lock file.
            holder_pid: PID of the lock holder, or ``None`` if unresolvable.
        """
        self.lock_path = lock_path
        self.holder_pid = holder_pid
        pid_hint = f" (held by PID {holder_pid})" if holder_pid is not None else ""
        super().__init__(f"Trailer state lock unavailable: {lock_path}{pid_hint}")


def _resolve_lock_holder_pid(lock_path: Path) -> int | None:
    """Best-effort: return the PID of the process holding ``lock_path``.

    Calls ``lsof -t`` and parses the first non-empty line. Returns ``None``
    if ``lsof`` is missing, returns no output, or its exit code is non-zero.

    Args:
        lock_path: Path to the advisory lock file.

    Returns:
        Integer PID, or ``None`` if unresolvable.
    """
    try:
        result = subprocess.run(
            ["lsof", "-t", str(lock_path)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        return int(first_line) if first_line.isdigit() else None
    except Exception:  # noqa: BLE001 — degrade gracefully (lsof absent, timeout, parse error)
        return None


def _validate_season_number(value: int | None, owner: str) -> None:
    """Raise ValueError when a season_number is non-None and negative.

    Shared by ``TrailerState.__post_init__`` and ``ScanItem.__post_init__``
    so both types accept the same domain (None for movies/show-level, ``0``
    for TMDB specials, ``>=1`` for regular seasons).

    Args:
        value: The season number to validate.
        owner: Class name used in the error message ("TrailerState" or
            "ScanItem").

    Raises:
        ValueError: If ``value`` is not None and is negative.
    """
    if value is not None and value < 0:
        raise ValueError(f"{owner}.season_number must be >= 0 (got {value})")


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


class TrailerStatus(Enum):
    """Lifecycle status of a trailer download attempt.

    Values are persisted as strings in the JSON state file. Do NOT rename
    members without a migration step.
    """

    DOWNLOADED = "downloaded"
    NO_TRAILER_AVAILABLE = "no_trailer_available"
    BOT_DETECTED = "bot_detected"
    HTTP_ERROR = "http_error"
    YTDLP_ERROR = "ytdlp_error"
    SKIPPED_BY_FILTER = "skipped_by_filter"
    ORPHAN = "orphan"
    # NEW (DESIGN §8 extension — library-aware SOT recheck):
    # the trailer was found on one of the storage disks before any network
    # call. Distinct from the staging-only "already_present" runtime counter.
    ALREADY_PRESENT_ON_DISK = "already_present_on_disk"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrailerState:
    """Persisted state for a single media item's trailer download lifecycle.

    Frozen and slotted: state mutations create a new instance via
    ``dataclasses.replace`` rather than in-place modification, which prevents
    accidental drift when references are passed around.

    Timestamps accept either UTC ISO 8601 strings (legacy callers) or
    tz-aware ``datetime`` objects. Naive datetimes are rejected at
    construction so DST/timezone bugs surface immediately rather than at
    serialisation time. ``media_path`` and ``trailer_path`` are absolute
    filesystem paths.

    Attributes:
        last_attempt: UTC ISO 8601 string of the most recent download attempt.
            A tz-aware ``datetime`` is converted to ISO 8601 at construction.
        attempts: Total number of download attempts (incremented on each try).
        status: Current lifecycle status (see ``TrailerStatus``).
        media_path: Absolute path to the media directory on disk. Used by GC to
            detect orphaned entries when the media has been deleted or moved.
        next_retry_at: UTC ISO 8601 string after which a retry is allowed.
            ``None`` means retry immediately (e.g. status ``DOWNLOADED``).
        trailer_path: Absolute path to the downloaded trailer file, or ``None``
            if the trailer has not been successfully downloaded yet.
        source: Originating source of the trailer URL — ``"tmdb"`` or
            ``"youtube"`` — or ``None`` when not applicable.
        youtube_url: Full YouTube watch URL used for the download, or ``None``.
        notes: Free-form human-readable note (e.g. error message summary).
        bot_detected_consecutive_attempts: Counter for consecutive
            ``BOT_DETECTED`` outcomes. Incremented before writing a
            ``BOT_DETECTED`` state; reset to ``0`` before writing any other
            status (DESIGN §5 counter semantics).
        season_number: ``None`` for movies and show-level TV trailers;
            positive 1-indexed integer for season-level entries (DESIGN §4).
    """

    last_attempt: str | datetime
    attempts: int
    status: TrailerStatus
    media_path: str
    next_retry_at: str | datetime | None = None
    trailer_path: str | None = None
    source: str | None = None
    youtube_url: str | None = None
    notes: str | None = None
    bot_detected_consecutive_attempts: int = 0
    season_number: int | None = None

    def __post_init__(self) -> None:
        """Validate timestamps and coerce datetime inputs to ISO 8601.

        Naive datetimes are silently corrupted across DST transitions, so we
        reject them at construction. tz-aware datetimes are coerced to ISO
        strings (frozen dataclass — coercion via ``object.__setattr__``).

        Raises:
            ValueError: If a timestamp string is naive, malformed, or a
                datetime is naive.
            TypeError: If a timestamp is neither str nor datetime.
        """
        for attr in ("last_attempt", "next_retry_at"):
            raw = getattr(self, attr)
            if raw is None:
                continue
            if isinstance(raw, datetime):
                if raw.tzinfo is None:
                    raise ValueError(f"TrailerState.{attr} datetime must be tz-aware (got naive: {raw!r})")
                # Coerce to ISO string in-place (frozen dataclass — use object.__setattr__).
                object.__setattr__(self, attr, raw.isoformat())
                continue
            if not isinstance(raw, str):
                raise TypeError(f"TrailerState.{attr} must be str or datetime, got {type(raw).__name__}")
            try:
                parsed = datetime.fromisoformat(raw)
            except ValueError as exc:
                raise ValueError(f"TrailerState.{attr} is not valid ISO 8601: {raw!r}") from exc
            if parsed.tzinfo is None:
                raise ValueError(f"TrailerState.{attr} ISO string must include timezone offset (got naive: {raw!r})")
        _validate_season_number(self.season_number, "TrailerState")


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def _normalize_title(title: str) -> str:
    """Apply NFC normalization, casefold, and whitespace collapse to a title.

    This stable normalization ensures that ``"Fight Club"`` and
    ``"fight  club"`` (extra space + case) produce the same manual key.

    Args:
        title: Raw title string from any source.

    Returns:
        NFC-normalized, casefolded, and whitespace-collapsed title.
    """
    nfc = unicodedata.normalize("NFC", title)
    return " ".join(nfc.casefold().split())


def make_state_key(
    media_type: str,
    ids: dict[str, int | str | None],
    title: str | None = None,
    year: int | None = None,
    season_number: int | None = None,
) -> str:
    """Build a composite state key for a media item.

    Precedence:
        1. ``ids["tmdb"]``  → ``"{media_type}:tmdb:{id}"``
        2. ``ids["tvdb"]``  → ``"{media_type}:tvdb:{id}"``
        3. Fallback         → ``"manual:{sha256(NFC+casefold(title)|year|media_type)}"``

    When ``season_number`` is provided **and** a TMDB/TVDB id is present, the
    season suffix is appended::

        "tv:tmdb:{id}:season:{N}"
        "tv:tvdb:{id}:season:{N}"

    Manual keys do NOT receive a season suffix — season-level trailers without
    external IDs are out of scope in this initial trailer feature release.

    The manual key hashes the NORMALIZED title (NFC + casefold + collapsed
    whitespace) concatenated with year and media_type, separated by ``|``.
    This makes the key stable across re-scrape runs that correct the folder
    name capitalisation.

    Args:
        media_type: ``"movie"`` or ``"tv"``.
        ids: Dict with optional ``"tmdb"`` and/or ``"tvdb"`` integer IDs.
            Values that are ``None`` or ``0`` are treated as absent.
        title: Human-readable title used only for the manual fallback.
        year: Release year (integer) used only for the manual fallback.
        season_number: When not ``None``, appends a ``:season:{N}`` suffix
            to TMDB/TVDB keys (1-indexed, per TMDB convention).

    Returns:
        A stable string key such as ``"movie:tmdb:550"``,
        ``"tv:tmdb:1399:season:3"``, or ``"manual:{hex-digest}"``.

    Raises:
        ValueError: If no external ID is present and ``title`` is ``None``.
    """
    # Primary: TMDB id
    tmdb_id = ids.get("tmdb")
    if tmdb_id is not None and tmdb_id != 0:
        base = f"{media_type}:tmdb:{tmdb_id}"
        if season_number is not None:
            return f"{base}:season:{season_number}"
        return base

    # Secondary: TVDB id
    tvdb_id = ids.get("tvdb")
    if tvdb_id is not None and tvdb_id != 0:
        base = f"{media_type}:tvdb:{tvdb_id}"
        if season_number is not None:
            return f"{base}:season:{season_number}"
        return base

    # Fallback: manual hash of normalized title + year + media_type
    if title is None:
        raise ValueError("Cannot build manual state key: title is required when no external ID is present.")
    normalized = _normalize_title(title)
    payload = f"{normalized}|{year}|{media_type}"
    digest = hashlib.sha256(payload.encode(), usedforsecurity=False).hexdigest()
    return f"manual:{digest}"


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------


def compute_next_retry_at(
    attempts: int,
    policy: list[int],
    *,
    last_attempt: datetime,
) -> datetime:
    """Return the next retry datetime using the configured policy.

    Clock reference is always ``last_attempt`` (DESIGN §7) — NOT the time of
    the first failure. This means a stuck entry keeps pushing the retry window
    forward; a recovered entry resets ``attempts = 1`` on its next successful
    result.

    Args:
        attempts: Number of attempts made so far (1-indexed).
        policy: List of retry intervals in days
            (e.g. ``[1, 7, 30]``). The last element repeats for all
            subsequent attempts.
        last_attempt: UTC-aware datetime of the most recent attempt.

    Returns:
        A UTC-aware datetime representing the earliest acceptable next retry.
    """
    days = policy[min(attempts - 1, len(policy) - 1)]
    return last_attempt + timedelta(days=days)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class TrailerStateStore:
    """JSON-backed persistent store for trailer download lifecycle state.

    The state file is a JSON object with the structure::

        {"version": 1, "entries": {"movie:tmdb:550": {...}}}

    Writes use :func:`atomic_write_json` with directory fsync for crash
    durability. Under Unix, ``fcntl.flock(LOCK_EX)`` on a
    sibling ``.lock`` file serialises concurrent read-modify-write cycles so
    that two simultaneous ``personalscraper trailers`` processes cannot corrupt
    the state file.

    Attributes:
        _state_file: Absolute path to the JSON state file.
        _lock_file: Path to the advisory lock file (sibling ``.lock``).
    """

    def __init__(self, state_file: Path) -> None:
        """Initialize the store backed by ``state_file``.

        The file and its parent directory are created lazily on the first
        ``set()`` call.

        Args:
            state_file: Absolute path to the JSON state file (e.g.
                ``.data/trailers_state.json``).
        """
        self._state_file = state_file
        self._lock_file = state_file.with_suffix(".lock")
        # Set to True by _load() when a corrupt file is detected and backed up.
        # Cleared after the first post-corruption set() emits the recovery log
        # so the WARNING fires exactly once per corruption event.
        self._recovering_from_corrupt: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> TrailerState | None:
        """Return the ``TrailerState`` for ``key``, or ``None`` on miss.

        Args:
            key: Composite state key (see ``make_state_key``).

        Returns:
            Deserialized ``TrailerState``, or ``None`` if the key is absent
            or the state file does not exist.
        """
        entries = self._load()
        raw = entries.get(key)
        if raw is None:
            return None
        return self._deserialize(raw)

    def _acquire_lock(self, lock_fh: Any) -> None:
        """Acquire an exclusive non-blocking flock with a bounded retry budget.

        Attempts ``_LOCK_MAX_ATTEMPTS`` times with ``_LOCK_RETRY_SLEEP_SEC``
        between each attempt.  Uses ``LOCK_EX | LOCK_NB`` so each attempt
        returns immediately instead of blocking forever (C7 fix: prevents
        deadlock when two concurrent processes contend on the same lock file).

        Args:
            lock_fh: Open file handle to the ``.lock`` sibling file.

        Raises:
            TrailerStateLocked: If the lock cannot be acquired within the
                configured retry budget (only ``EAGAIN``/``EWOULDBLOCK`` are
                treated as contention and retried).
            OSError: Re-raised immediately for any errno other than
                ``EAGAIN``/``EWOULDBLOCK`` (e.g. ``EBADF``, ``EINVAL``,
                NFS ``EOPNOTSUPP``). These indicate a real fd or filesystem
                error rather than normal lock contention.
        """
        assert _fcntl is not None  # caller (set()) gates on _FCNTL_AVAILABLE
        for attempt in range(_LOCK_MAX_ATTEMPTS):
            try:
                _fcntl.flock(lock_fh, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                return  # Lock acquired.
            except OSError as exc:
                # LOCK_NB raises BlockingIOError (a subclass of OSError, errno
                # EAGAIN or EWOULDBLOCK) when the lock is held by another process.
                # Any other errno (EBADF, EINVAL, NFS EOPNOTSUPP, …) is a real
                # filesystem or fd error — not a contention event — so we must
                # not silently retry but re-raise immediately so the caller can
                # surface the true cause.
                if exc.errno not in (_errno_mod.EAGAIN, _errno_mod.EWOULDBLOCK):
                    log.error(
                        "trailer_state_lock_unexpected_oserror",
                        errno=exc.errno,
                        error=str(exc),
                        lock_path=str(self._lock_file),
                        exc_info=True,
                    )
                    raise
                if attempt < _LOCK_MAX_ATTEMPTS - 1:
                    time.sleep(_LOCK_RETRY_SLEEP_SEC)
        # Budget exhausted — resolve holder PID for diagnostics.
        holder_pid = _resolve_lock_holder_pid(self._lock_file)
        log.warning(
            "trailers_state_lock_contention",
            lock_path=str(self._lock_file),
            attempts=_LOCK_MAX_ATTEMPTS,
            holder_pid=holder_pid,
        )
        raise TrailerStateLocked(self._lock_file, holder_pid)

    def set(self, key: str, state: TrailerState) -> None:
        """Write or overwrite the ``TrailerState`` for ``key`` atomically.

        The full read-modify-write cycle is protected by ``fcntl.flock`` so
        that concurrent writes do not lose each other's entries.

        On the first call after a corrupt-file recovery, emits a WARNING log
        ``trailer_state.recovering_from_corrupt`` so operators know the store
        has been reset and the new entry-count is the current size.

        Args:
            key: Composite state key.
            state: ``TrailerState`` to persist.

        Raises:
            TrailerStateLocked: If the advisory lock cannot be acquired within
                the retry budget (Unix only).
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_file.open("a") as lock_fh:
                self._acquire_lock(lock_fh)
                try:
                    entries = self._load()
                    entries[key] = self._serialize(state)
                    self._save(entries)
                    self._maybe_log_recovery(len(entries))
                finally:
                    _fcntl.flock(lock_fh, _fcntl.LOCK_UN)
        else:
            # Best-effort on non-Unix platforms
            entries = self._load()
            entries[key] = self._serialize(state)
            self._save(entries)
            self._maybe_log_recovery(len(entries))

    def should_skip(self, key: str) -> bool:
        """Return ``True`` if the entry for ``key`` should be skipped.

        Skip logic (DESIGN §7):
        - Missing key → do NOT skip (first run).
        - ``BOT_DETECTED`` → never skip (always retry on next run).
        - ``DOWNLOADED`` / ``ALREADY_PRESENT_ON_DISK`` → skip (no retry needed).
        - Any other status with ``next_retry_at`` in the future → skip.
        - Any other status with ``next_retry_at`` in the past or absent → do NOT skip.

        Args:
            key: Composite state key.

        Returns:
            ``True`` if the caller should skip this media item, ``False``
            if a download attempt should proceed.
        """
        state = self.get(key)
        if state is None:
            return False
        if state.status == TrailerStatus.BOT_DETECTED:
            return False
        if state.status in (TrailerStatus.DOWNLOADED, TrailerStatus.ALREADY_PRESENT_ON_DISK):
            return True
        if state.next_retry_at is None:
            return False
        # Type is `str | datetime` for ergonomic construction; __post_init__
        # always coerces to `str`, so the isinstance branch is dead in practice
        # but kept for type-checker satisfaction and as belt-and-suspenders.
        retry_iso = state.next_retry_at if isinstance(state.next_retry_at, str) else state.next_retry_at.isoformat()
        try:
            retry_at = datetime.fromisoformat(retry_iso)
        except ValueError:
            log.warning("trailer_state.invalid_next_retry_at", key=key, value=retry_iso)
            return False
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return datetime.now(UTC) < retry_at

    def all_entries(self) -> dict[str, TrailerState]:
        """Return all entries as a dict keyed by state key.

        Used by CLI scan/purge subcommands that need to iterate over the full
        store without knowing individual keys in advance.

        Returns:
            Dict mapping each composite state key to its ``TrailerState``.
        """
        raw = self._load()
        result: dict[str, TrailerState] = {}
        dropped = 0
        for k, v in raw.items():
            try:
                result[k] = self._deserialize(v)
            except (KeyError, ValueError, TypeError) as exc:
                log.warning("trailer_state.malformed_entry", key=k, error=str(exc), exc_info=True)
                dropped += 1
        # Surface an aggregate so CLI scan/purge users can spot when their state
        # has degraded entries that won't appear in their iteration result.
        if dropped:
            log.warning(
                "trailer_state_malformed_entries_dropped",
                dropped=dropped,
                total=len(raw),
                surviving=len(result),
            )
        return result

    def auto_gc(self) -> None:
        """Run lifecycle garbage collection on all ``DOWNLOADED`` entries.

        GC rules (evaluated in order):
        1. ``media_path`` does not exist on disk → flip status to ``ORPHAN``.
        2. ``trailer_path`` is set but the file is gone → remove the entry
           entirely so the trailer can be re-downloaded.
        3. Both paths exist → entry is healthy, leave it untouched.

        Should be called at the start of every ``trailers`` command/step so
        stale entries from deleted or moved media are caught promptly.

        Raises:
            TrailerStateLocked: If the advisory lock cannot be acquired within
                the retry budget (Unix only).
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_file.open("a") as lock_fh:
                self._acquire_lock(lock_fh)
                try:
                    self._run_gc()
                finally:
                    _fcntl.flock(lock_fh, _fcntl.LOCK_UN)
        else:
            self._run_gc()

    def purge_orphans(self) -> int:
        """Remove all entries whose status is ``ORPHAN``.

        Intended for the ``--include-state`` cleanup flag (DESIGN §8 extension)
        to wipe stale records for deleted media.

        Returns:
            Number of entries removed.

        Raises:
            TrailerStateLocked: If the advisory lock cannot be acquired within
                the retry budget (Unix only).
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_file.open("a") as lock_fh:
                self._acquire_lock(lock_fh)
                try:
                    return self._do_purge_orphans()
                finally:
                    _fcntl.flock(lock_fh, _fcntl.LOCK_UN)
        else:
            return self._do_purge_orphans()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        """Read and parse the state file; return the ``entries`` dict.

        Returns an empty dict if the file does not exist, is empty, or
        cannot be parsed (log a WARNING in that case).

        Returns:
            Dict mapping state keys to raw serialised entry dicts.
        """
        if not self._state_file.exists():
            return {}
        try:
            with self._state_file.open("r", encoding="utf-8") as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                self._backup_corrupt_with_data_loss(reason="root_not_object", min_entries_lost=0)
                return {}
            entries = raw.get("entries", {})
            if not isinstance(entries, dict):
                self._backup_corrupt_with_data_loss(reason="entries_not_object", min_entries_lost=0)
                return {}
            return {k: v for k, v in entries.items() if isinstance(v, dict)}
        except (json.JSONDecodeError, ValueError) as exc:
            # Parse error — preserve the bad file before the next set() overwrites it.
            # Use the heuristic lower-bound count so operators know data was not simply
            # empty (min_entries_lost=0 from a truncated 1000-entry file would be misleading).
            min_entries_lost = self._count_entries_lost()
            self._backup_corrupt_with_data_loss(
                reason=f"parse_error:{type(exc).__name__}",
                min_entries_lost=min_entries_lost,
            )
            log.error(
                "trailer_state_load_failed",
                path=str(self._state_file),
                error=str(exc),
                exc_info=True,
            )
            return {}
        except OSError as exc:
            # Read failure (permissions, broken mount). Do NOT backup — the file is
            # likely intact but inaccessible; return empty so the run continues.
            log.warning(
                "trailer_state_read_failed",
                path=str(self._state_file),
                error=str(exc),
                exc_info=True,
            )
            return {}

    def _count_entries_lost(self) -> int:
        """Best-effort lower-bound count of entries in the (possibly corrupt) state file.

        First attempts a full JSON parse to get an exact count.  When that fails
        (i.e. the file is corrupt), falls back to counting occurrences of the
        ``"status":`` substring in the raw text.  Every well-formed entry in the
        state file has exactly one ``status`` field, so this gives a reliable
        lower bound even when the JSON is truncated or partially overwritten.

        The result is best-effort: callers should treat it as a minimum, not an
        exact figure.  The caller is responsible for labelling the log field
        ``min_entries_lost`` to make that contract visible to operators.

        Returns:
            Lower-bound count of entries, or ``0`` if the file cannot be read.
        """
        try:
            raw_text = self._state_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0

        # Fast path: try a full parse first — exact count, no heuristic needed.
        try:
            partial = json.loads(raw_text)
            entries = partial.get("entries", {})
            if isinstance(entries, dict):
                return len(entries)
        except (json.JSONDecodeError, ValueError, AttributeError):
            pass  # Fall through to the string-scan heuristic below.

        # Heuristic fallback: count ``"status":`` occurrences.  Each well-formed
        # entry contains exactly one ``"status"`` field, so this is a lower bound
        # even for truncated or interleaved writes.
        return raw_text.count('"status":')

    def _backup_corrupt_with_data_loss(self, reason: str, min_entries_lost: int) -> None:
        """Copy the state file aside and emit a loud ERROR for the data loss.

        Without this backup, a parse failure followed by ``set()`` silently
        destroys every prior entry. The backup keeps a forensic copy at
        ``<state_file>.corrupt-<unix_ts>``.

        After calling this method the instance transitions to
        ``_recovering_from_corrupt = True`` so that the next ``set()`` emits
        an additional WARNING confirming the store is rebuilding.

        Args:
            reason: Short tag used in the log (e.g. ``parse_error:JSONDecodeError``).
            min_entries_lost: Lower-bound count of entries that could not be
                recovered (best-effort heuristic — treat as a minimum, not exact).
        """
        # Guard: if we are already in recovery mode, the backup + ERROR log were
        # already emitted for this corruption event — skip the duplicate.
        # (set() calls _load() which would re-detect the still-corrupt file.)
        if self._recovering_from_corrupt:
            return
        backup_path: str = ""
        try:
            # Preserve the original full filename (incl. .json suffix) so the
            # forensic copy remains recognisable as the parsed-format file.
            backup = self._state_file.with_name(f"{self._state_file.name}.corrupt-{int(time.time())}")
            shutil.copy(self._state_file, backup)
            backup_path = str(backup)
            log.error(
                "trailer_state.data_loss_started",
                original=str(self._state_file),
                backup_path=backup_path,
                reason=reason,
                min_entries_lost=min_entries_lost,
            )
            self._recovering_from_corrupt = True
        except OSError as exc:
            log.error(
                "trailer_state_corrupt_backup_failed",
                path=str(self._state_file),
                error=str(exc),
                reason=reason,
                exc_info=True,
            )

    def _maybe_log_recovery(self, new_entry_count: int) -> None:
        """Emit a WARNING log once after recovering from a corrupt state file.

        Called by ``set()`` after the new entry has been persisted. Fires
        exactly once per corruption event and then resets the flag.

        Args:
            new_entry_count: Total number of entries now in the store.
        """
        if self._recovering_from_corrupt:
            log.warning(
                "trailer_state.recovering_from_corrupt",
                new_entry_count=new_entry_count,
                hint="state store rebuilt from scratch after corruption; prior entries lost",
            )
            self._recovering_from_corrupt = False

    def _save(self, entries: dict[str, Any]) -> None:
        """Persist entries with fsync durability via :func:`atomic_write_json`.

        The atomic-write helper creates the parent directory, fsyncs the file
        *and* the parent directory so the save survives a machine crash (ext4 /
        macFUSE-mounted NTFS safety).

        Args:
            entries: Dict mapping state keys to serialised entry dicts.
        """
        payload: dict[str, Any] = {"version": _STATE_VERSION, "entries": entries}
        atomic_write_json(self._state_file, payload, indent=2)

    @staticmethod
    def _serialize(state: TrailerState) -> dict[str, Any]:
        """Convert a ``TrailerState`` to a JSON-serialisable dict.

        The ``status`` enum is converted to its string value.

        Args:
            state: The ``TrailerState`` to serialise.

        Returns:
            A plain dict ready for ``json.dump``.
        """
        d = asdict(state)
        d["status"] = state.status.value
        return d

    @staticmethod
    def _deserialize(raw: dict[str, Any]) -> TrailerState:
        """Reconstruct a ``TrailerState`` from a raw JSON dict.

        Args:
            raw: Plain dict loaded from the JSON state file.

        Returns:
            A fully populated ``TrailerState`` instance.

        Raises:
            KeyError: If a required field is missing.
            ValueError: If the ``status`` value is not a valid ``TrailerStatus``.
        """
        d = dict(raw)
        d["status"] = TrailerStatus(d["status"])
        return TrailerState(**d)

    def _run_gc(self) -> None:
        """Core GC logic — called under lock (or directly on non-Unix).

        Mutates entries in memory and flushes to disk only when changes occur.
        """
        entries = self._load()
        changed = False
        to_delete: list[str] = []

        for key, raw in entries.items():
            try:
                state = self._deserialize(raw)
            except (KeyError, ValueError, TypeError) as exc:
                log.warning("trailer_state.gc_skip_malformed", key=key, error=str(exc))
                continue

            if state.status != TrailerStatus.DOWNLOADED:
                # Only GC downloaded entries — other statuses are managed explicitly
                continue

            media_exists = Path(state.media_path).exists()
            if not media_exists:
                # Media directory gone → mark as orphan
                log.info("trailer_state.gc_orphan", key=key, media_path=state.media_path)
                raw["status"] = TrailerStatus.ORPHAN.value
                changed = True
                continue

            if state.trailer_path is not None and not Path(state.trailer_path).is_file():
                # Trailer file deleted while media still exists → remove entry
                # so it can be re-downloaded on next run.
                log.info("trailer_state.gc_remove_missing_trailer", key=key, trailer_path=state.trailer_path)
                to_delete.append(key)
                changed = True

        for key in to_delete:
            del entries[key]

        if changed:
            self._save(entries)

    def _do_purge_orphans(self) -> int:
        """Inner purge logic — called under lock (or directly on non-Unix).

        Returns:
            Number of orphan entries removed.
        """
        entries = self._load()
        before = len(entries)
        entries = {
            k: v
            for k, v in entries.items()
            if not (isinstance(v, dict) and v.get("status") == TrailerStatus.ORPHAN.value)
        }
        removed = before - len(entries)
        if removed:
            self._save(entries)
        return removed


# Convenience re-export so callers can do:
#   from personalscraper.trailers.state import TrailerStateStore, TrailerStatus, TrailerState
__all__ = [
    "TrailerStatus",
    "TrailerState",
    "TrailerStateStore",
    "TrailerStateLocked",
    "make_state_key",
    "compute_next_retry_at",
]
