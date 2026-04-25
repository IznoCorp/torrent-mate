"""Trailer state tracking — persistent JSON store with composite keys and retry policy.

Implements DESIGN §7 (State tracking), §8 (lifecycle GC and orphan purge), and
§12 (concurrency with fcntl.flock). The state file lives at
``.data/trailers_state.json`` relative to the project root; callers pass the
absolute path to ``TrailerStateStore.__init__``.

Key design decisions:
- Atomic writes via ``tempfile.NamedTemporaryFile`` + ``os.replace``.
- ``fcntl.flock(LOCK_EX)`` on a sibling ``.lock`` file prevents torn writes
  when multiple ``personalscraper trailers download`` processes run concurrently.
  Falls back to best-effort write on non-Unix platforms where ``fcntl`` is absent.
- All timestamps are stored as UTC ISO 8601 strings.
- ``BOT_DETECTED`` status is exempt from retry-after (always retried on next run).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

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


@dataclass
class TrailerState:
    """Persisted state for a single media item's trailer download lifecycle.

    All timestamps are UTC ISO 8601 strings. ``media_path`` and
    ``trailer_path`` are absolute filesystem paths.

    Attributes:
        last_attempt: UTC ISO 8601 timestamp of the most recent download attempt.
        attempts: Total number of download attempts (incremented on each try).
        status: Current lifecycle status (see ``TrailerStatus``).
        media_path: Absolute path to the media directory on disk. Used by GC to
            detect orphaned entries when the media has been deleted or moved.
        next_retry_at: UTC ISO 8601 timestamp after which a retry is allowed.
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

    last_attempt: str
    attempts: int
    status: TrailerStatus
    media_path: str
    next_retry_at: str | None = None
    trailer_path: str | None = None
    source: str | None = None
    youtube_url: str | None = None
    notes: str | None = None
    # DESIGN §5 "Counter semantics": incremented on each consecutive bot_detected,
    # reset on any non-bot_detected outcome BEFORE the new status is written.
    bot_detected_consecutive_attempts: int = 0
    # DESIGN §4 "Season trailers" extension. None for movies and show-level TV
    # trailers; positive integer for season-level entries (1-indexed).
    season_number: int | None = None


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
    external IDs are out of scope for v0.7.0.

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

    Writes are atomic: a temporary file is written, then ``os.replace()``
    swaps it onto the real path. Under Unix, ``fcntl.flock(LOCK_EX)`` on a
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

    def set(self, key: str, state: TrailerState) -> None:
        """Write or overwrite the ``TrailerState`` for ``key`` atomically.

        The full read-modify-write cycle is protected by ``fcntl.flock`` so
        that concurrent writes do not lose each other's entries.

        Args:
            key: Composite state key.
            state: ``TrailerState`` to persist.
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_file.open("a") as lock_fh:
                _fcntl.flock(lock_fh, _fcntl.LOCK_EX)
                try:
                    entries = self._load()
                    entries[key] = self._serialize(state)
                    self._save(entries)
                finally:
                    _fcntl.flock(lock_fh, _fcntl.LOCK_UN)
        else:
            # Best-effort on non-Unix platforms
            entries = self._load()
            entries[key] = self._serialize(state)
            self._save(entries)

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
        try:
            retry_at = datetime.fromisoformat(state.next_retry_at)
        except ValueError:
            log.warning("trailer_state.invalid_next_retry_at", key=key, value=state.next_retry_at)
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
        for k, v in raw.items():
            try:
                result[k] = self._deserialize(v)
            except (KeyError, ValueError, TypeError) as exc:
                log.warning("trailer_state.malformed_entry", key=k, error=str(exc))
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
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_file.open("a") as lock_fh:
                _fcntl.flock(lock_fh, _fcntl.LOCK_EX)
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
        """
        if _FCNTL_AVAILABLE and _fcntl is not None:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            with self._lock_file.open("a") as lock_fh:
                _fcntl.flock(lock_fh, _fcntl.LOCK_EX)
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
                return {}
            entries = raw.get("entries", {})
            if not isinstance(entries, dict):
                return {}
            return {k: v for k, v in entries.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            log.warning("trailer_state.load_failed", path=str(self._state_file), error=str(exc))
            return {}

    def _save(self, entries: dict[str, Any]) -> None:
        """Write ``entries`` to the state file atomically via temp + os.replace.

        Args:
            entries: Dict mapping state keys to serialised entry dicts.
        """
        parent = self._state_file.parent
        parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"version": _STATE_VERSION, "entries": entries}
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            suffix=".tmp",
            delete=False,
        ) as tmp:
            json.dump(payload, tmp, ensure_ascii=False, indent=2)
            tmp_path = tmp.name
        try:
            os.replace(tmp_path, self._state_file)
        except OSError:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

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
    "make_state_key",
    "compute_next_retry_at",
]

# Expose the field annotation used by TrailerState for external type-checkers
_TRAILER_STATE_FIELDS = field  # keep field in module scope to satisfy dataclasses import
