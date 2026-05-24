"""OMDB daily-quota tracker.

OMDB free tier = 1000 req/day, midnight UTC reset. Paid tiers configurable
via OMDB_DAILY_LIMIT env (Patreon $1 = 100k req/day).

Persisted state file: ``<indexer.db dir>/.omdb-quota.json``::

    {"date": "YYYY-MM-DD", "count": N, "limit": N, "exhausted": bool}

Concurrency: single-process by design (the backfill is sequential).
File is rewritten atomically via temp + os.replace.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal, TypedDict

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
        """Project to a JSON-serializable dict (same shape as the old status())."""
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
    rewritten atomically (temp file + :func:`os.replace`) on every mutation.
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

        Returns:
            ``"allowed"`` if the call may proceed, ``"skipped_safety_margin"``
            if the safety margin was reached, or ``"skipped_marked_exhausted"``
            if the day was explicitly marked exhausted.
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
                )
                return "skipped_safety_margin"
            return "allowed"

    def mark_exhausted(self, reason: str) -> None:
        """Force the day as exhausted.

        Call when the server returns a quota-exhaustion payload so
        remaining calls are skipped without wasting HTTP round-trips.

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
        """Load persisted state or return a fresh default for today."""
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
        except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
            log.warning(
                "omdb_quota_state_corrupted",
                path=str(self._state_path),
                error=str(exc),
            )
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

    def _persist(self) -> None:
        """Atomically write current state via temp + rename."""
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self._state, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, self._state_path)
