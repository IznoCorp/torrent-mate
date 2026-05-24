"""OMDB daily-quota tracker.

OMDB free tier = 1000 req/day, midnight UTC reset. Paid tiers configurable
via OMDB_DAILY_LIMIT env (Patreon $1 = 100k req/day).

Persisted state file: ``<indexer.db dir>/.omdb-quota.json``::

    {"date": "YYYY-MM-DD", "count": N, "limit": N, "exhausted": bool}

Concurrency: single-process by design (the backfill is sequential).
File is written with fsync durability via :func:`atomic_write_json`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal, TypedDict

from personalscraper.io_utils import atomic_write_json
from personalscraper.logger import get_logger

log = get_logger("api.omdb.quota")

_DEFAULT_LIMIT = 1000
_SAFETY_MARGIN = 50

ReservationOutcome = Literal["allowed", "skipped_safety_margin", "skipped_marked_exhausted"]


@dataclass(frozen=True)
class QuotaStatus:
    """Immutable snapshot of the current quota state."""

    date: str
    count: int
    limit: int
    safety_margin: int
    remaining_before_margin: int
    exhausted: bool

    def to_json_dict(self) -> dict[str, str | int | bool]:
        """Project to a JSON-serializable dict consumed by CLI / structlog stats."""
        return {
            "date": self.date,
            "count": self.count,
            "limit": self.limit,
            "safety_margin": self.safety_margin,
            "remaining_before_margin": self.remaining_before_margin,
            "exhausted": self.exhausted,
        }


class _QuotaState(TypedDict):
    date: str
    count: int
    limit: int
    exhausted: bool


class OmdbQuotaTracker:
    """Persistent daily-quota tracker for OMDB (1000 req/day free tier).

    Configurable for paid tiers via ``OMDB_DAILY_LIMIT`` env (Patreon $1
    = 100k req/day).  State file: ``<indexer.db dir>/.omdb-quota.json``,
    rewritten with directory fsync (via :func:`atomic_write_json`) on every mutation.
    The counter resets at midnight UTC — any persisted ``date`` not matching
    today is replaced with a fresh day.  Concurrency is single-process by
    design (the backfill pipeline is sequential); a :class:`Lock` ensures
    single-writer safety within that process.

    The *safety margin* (default 50) stops reserving calls before the
    hard limit is reached. This avoids actually hitting the HTTP 401 —
    runtime exhaustion detection is a safety net for the edge case where
    an external process or previous run consumed the remaining budget.
    """

    def __init__(
        self,
        state_path: Path,
        limit: int = _DEFAULT_LIMIT,
        safety_margin: int = _SAFETY_MARGIN,
    ) -> None:
        """Initialize the tracker, loading persisted state or a fresh day.

        Args:
            state_path: Filesystem path for the JSON state file.
            limit: Daily request limit (default 1000, overridable via env).
            safety_margin: Number of calls to reserve BEFORE the hard limit.

        Raises:
            ValueError: If *safety_margin* is not in ``[0, limit)``.
        """
        if not 0 <= safety_margin < limit:
            raise ValueError(f"safety_margin ({safety_margin}) must be >= 0 and < limit ({limit})")
        self._state_path = state_path
        self._limit = limit
        self._safety_margin = safety_margin
        self._lock = Lock()
        self._state: _QuotaState = self._load_state()

    # -- Public API ----------------------------------------------------------

    def reserve_call(self) -> ReservationOutcome:
        """Try to reserve a quota slot.

        On persistence failure (OS error during the atomic file write)
        the in-memory state is rolled back and the call is reported as
        ``"skipped_safety_margin"`` — fail-soft, the upstream request is
        NOT sent. The next reservation attempt will retry.

        Returns:
            ``"allowed"`` if the call may proceed, ``"skipped_safety_margin"``
            if the safety margin was reached OR persistence failed, or
            ``"skipped_marked_exhausted"`` if the day was explicitly
            marked exhausted.
        """
        with self._lock:
            self._maybe_reset_day()
            if self._state["exhausted"]:
                return "skipped_marked_exhausted"
            if self._state["count"] >= self._limit - self._safety_margin:
                self._state["exhausted"] = True
                try:
                    self._persist()
                except OSError:
                    self._state["exhausted"] = False
                    log.error(
                        "omdb_quota_persist_failed",
                        path=str(self._state_path),
                        operation="mark_exhausted",
                        exc_info=True,
                    )
                    return "skipped_safety_margin"
                log.warning(
                    "omdb_quota_safety_margin_reached",
                    count=self._state["count"],
                    limit=self._limit,
                    safety_margin=self._safety_margin,
                )
                return "skipped_safety_margin"
            self._state["count"] += 1
            try:
                self._persist()
            except OSError:
                self._state["count"] -= 1
                log.error(
                    "omdb_quota_persist_failed",
                    path=str(self._state_path),
                    operation="increment_count",
                    exc_info=True,
                )
                return "skipped_safety_margin"
            return "allowed"

    def mark_exhausted(self, reason: str) -> None:
        """Force the day as exhausted.

        Call when the server returns a quota-exhaustion payload so
        remaining calls are skipped without wasting HTTP round-trips.

        If persistence fails the in-memory ``exhausted`` flag is rolled
        back so the tracker's invariant (in-memory matches what was
        durably written) is preserved. The trade-off is real: a known-
        exhausted day will allow another upstream call until the next
        runtime detection re-trips this branch.

        Args:
            reason: Human-readable reason logged for diagnostics.
        """
        with self._lock:
            self._maybe_reset_day()
            self._state["exhausted"] = True
            try:
                self._persist()
            except OSError:
                self._state["exhausted"] = False
                log.error(
                    "omdb_quota_persist_failed",
                    path=str(self._state_path),
                    operation="mark_exhausted",
                    exc_info=True,
                )
                return
            log.warning(
                "omdb_quota_marked_exhausted",
                reason=reason,
                count=self._state["count"],
                limit=self._limit,
            )

    def status(self) -> QuotaStatus:
        """Read-only snapshot of the current quota state."""
        with self._lock:
            remaining = max(0, self._limit - self._safety_margin - self._state["count"])
            return QuotaStatus(
                date=self._state["date"],
                count=self._state["count"],
                limit=self._limit,
                safety_margin=self._safety_margin,
                remaining_before_margin=remaining,
                exhausted=self._state["exhausted"],
            )

    # -- Internal ------------------------------------------------------------

    @staticmethod
    def _today_utc() -> str:
        """Return today's date as ``YYYY-MM-DD`` in UTC."""
        return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    def _maybe_reset_day(self) -> None:
        """Reset the count if the persisted date is not today (UTC)."""
        today = self._today_utc()
        if self._state["date"] != today:
            self._state = {
                "date": today,
                "count": 0,
                "limit": self._limit,
                "exhausted": False,
            }
            log.info("omdb_quota_day_reset", date=today)

    def _load_state(self) -> _QuotaState:
        """Load persisted state or return a fresh default for today.

        On a corrupted state file (invalid JSON, missing keys, type
        errors) the corrupt file is renamed to
        ``<path>.corrupt-<YYYYMMDD-HHMMSS>`` before the in-memory
        state falls back to a fresh day. Preserving the original lets
        operators inspect a quota anomaly post-hoc — otherwise the next
        :meth:`_persist` would overwrite the only evidence.
        """
        today = self._today_utc()
        try:
            if self._state_path.exists():
                raw = json.loads(self._state_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and all(k in raw for k in ("date", "count", "limit", "exhausted")):
                    return {
                        "date": str(raw["date"]),
                        "count": int(raw["count"]),
                        "limit": int(raw.get("limit", self._limit)),
                        "exhausted": bool(raw["exhausted"]),
                    }
                self._archive_corrupt_state("schema_mismatch")
        # OSError covers the TOCTOU window between exists() and read_text()
        # (an external process — `mkdir -p`, cleanup cron, operator
        # rm — could delete the file mid-load). Treat a vanished or
        # unreadable file the same as invalid JSON: fall back to today's
        # default state.
        except (json.JSONDecodeError, ValueError, TypeError, KeyError, OSError) as exc:
            log.warning(
                "omdb_quota_state_corrupted",
                path=str(self._state_path),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            self._archive_corrupt_state(type(exc).__name__)
            log.warning(
                "omdb_quota_using_default_limit",
                path=str(self._state_path),
                limit=self._limit,
            )
        return {
            "date": today,
            "count": 0,
            "limit": self._limit,
            "exhausted": False,
        }

    def _archive_corrupt_state(self, reason: str) -> None:
        """Rename the corrupt state file so it survives the next ``_persist``.

        ``os.replace`` is atomic but only on the SAME filesystem — if
        ``self._state_path`` and the suffixed target end up on different
        mounts (rare, but possible when the data dir is a bind-mount), the
        rename raises ``OSError`` and the corrupt file stays where it is.
        The next ``_persist`` will then overwrite it, losing the forensic
        evidence. The log carries that warning explicitly so operators
        investigating quota anomalies know to check the archive immediately.
        """
        if not self._state_path.exists():
            log.info("omdb_quota_corrupt_already_removed", path=str(self._state_path), reason=reason)
            return
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
        corrupt_path = self._state_path.with_suffix(self._state_path.suffix + f".corrupt-{ts}")
        try:
            os.replace(self._state_path, corrupt_path)
        except OSError as exc:
            log.warning(
                "omdb_quota_corrupt_archive_failed",
                path=str(self._state_path),
                target=str(corrupt_path),
                error=str(exc),
                error_type=type(exc).__name__,
                hint="rename failed (cross-mount?) — corrupt file NOT archived, may be overwritten by next persist",
            )
            return
        log.warning(
            "omdb_quota_corrupt_archived",
            original=str(self._state_path),
            archived=str(corrupt_path),
            reason=reason,
        )

    def _persist(self) -> None:
        """Persist state with fsync durability via :func:`atomic_write_json`.

        The atomic-write helper fsyncs the file *and* the parent directory
        so the rename survives a machine crash (ext4 / macFUSE-mounted NTFS
        safety).
        """
        atomic_write_json(self._state_path, dict(self._state))
