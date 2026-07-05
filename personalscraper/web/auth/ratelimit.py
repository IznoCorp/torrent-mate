"""In-process sliding-window rate limiter for login attempts (tm-shell feature).

Dependency-free brute-force mitigation: caps the number of *failed* login
attempts per client key within a rolling time window.  This replaces the former
blocking ``time.sleep`` throttle inside the synchronous login handler — that
sleep both weakened brute-force protection and exhausted the sync threadpool
under load (a trivial DoS).  See docs/features/tm-shell/DESIGN.md §4.4.

The limiter is intentionally process-local and dependency-free: a single-user
self-hosted deployment needs brute-force friction, not a distributed quota
store.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

#: Maximum number of failed attempts allowed within the window before lockout.
MAX_FAILED_ATTEMPTS = 5

#: Rolling window length in seconds over which failed attempts are counted.
WINDOW_SECONDS = 60.0


class SlidingWindowRateLimiter:
    """Thread-safe sliding-window counter of failed attempts, keyed per client.

    Each key (typically a client IP) maps to a list of failure timestamps.
    Timestamps older than the window are pruned on every access, so memory stays
    bounded to the active window.  All mutating operations hold an internal
    ``threading.Lock`` because the FastAPI login handler runs in a threadpool.
    """

    def __init__(
        self,
        max_attempts: int = MAX_FAILED_ATTEMPTS,
        window_seconds: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialise an empty limiter.

        Args:
            max_attempts: Failures permitted per key within the window before
                :meth:`allow` starts returning ``False``.
            window_seconds: Length of the rolling window in seconds.
            clock: Monotonic time source (injected for deterministic testing).
        """
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune_locked(self, key: str, now: float) -> list[float]:
        """Drop expired timestamps for *key* and return the survivors.

        The caller MUST hold ``self._lock``.

        Args:
            key: The client key to prune.
            now: The current time from :attr:`_clock`.

        Returns:
            The remaining (in-window) failure timestamps for *key*.
        """
        cutoff = now - self._window_seconds
        kept = [ts for ts in self._failures.get(key, ()) if ts > cutoff]
        if kept:
            self._failures[key] = kept
        else:
            self._failures.pop(key, None)
        return kept

    def allow(self, key: str) -> bool:
        """Return whether another attempt is permitted for *key* right now.

        Args:
            key: The client identity (e.g. IP address).

        Returns:
            ``True`` while *key* has fewer than ``max_attempts`` failures in the
            current window; ``False`` once the threshold is reached.
        """
        now = self._clock()
        with self._lock:
            return len(self._prune_locked(key, now)) < self._max_attempts

    def record_failure(self, key: str) -> None:
        """Record one failed attempt for *key* at the current time.

        Args:
            key: The client identity to penalise.
        """
        now = self._clock()
        with self._lock:
            kept = self._prune_locked(key, now)
            kept.append(now)
            self._failures[key] = kept

    def reset(self, key: str) -> None:
        """Clear all recorded failures for *key* (e.g. after a success).

        Args:
            key: The client identity to clear.
        """
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        """Drop all recorded failures for every key (test/reset helper)."""
        with self._lock:
            self._failures.clear()
