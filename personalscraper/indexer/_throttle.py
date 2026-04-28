"""Read-rate throttling for the indexer scanner.

DESIGN §11.6: an optional ``indexer.scan.read_rate_mb_per_sec`` setting caps
the bandwidth used by fingerprint and mediainfo reads to avoid starving
co-resident processes (Plex, Time Machine, etc.) on shared spinning disks.

The throttle is implemented as a classic token bucket:

* Tokens are bytes; the bucket fills at ``rate_mb_per_sec * 1_000_000``
  bytes per second (decimal MB, matching how disk vendors quote bandwidth).
* Bucket capacity = one second of tokens, so a single ``acquire`` for the
  configured rate's worth of bytes never blocks the first time it is called.
* :meth:`TokenBucket.acquire` blocks (sleeps) until enough tokens are
  available, using ``threading.Lock`` for cross-thread safety.

A single :class:`TokenBucket` instance is shared across every scanner
worker thread (see :func:`personalscraper.indexer.scanner.__init__.scan`).
When the configured rate is ``None``, ``acquire`` is a near-zero-cost
passthrough — no lock is taken on the fast path.

Active-bucket lookup
--------------------

Read sites in :mod:`personalscraper.indexer.fingerprint` and
:mod:`personalscraper.indexer.mediainfo` cannot easily receive a bucket
parameter without a sweeping signature change across the scanner package.
Instead, ``scan()`` calls :func:`set_active_bucket` once before spawning
workers, and the read sites call :func:`acquire` which dereferences the
process-global bucket.  Workers spawned by ``ThreadPoolExecutor`` share the
same module reference, so the bucket is implicitly shared.

Tests use the same API: instantiate a :class:`TokenBucket` (optionally with
a fake clock and sleep injection), call :func:`set_active_bucket`, exercise
the read site, then :func:`set_active_bucket(None)` to reset.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

# A megabyte in this throttle is 10^6 bytes (decimal), matching how disk
# manufacturers and most rate-limiting tools quote bandwidth.  This is the
# convention used in DESIGN §11.6.
_BYTES_PER_MB: int = 1_000_000


class TokenBucket:
    """Thread-safe token bucket for byte-level read throttling.

    When ``rate_mb_per_sec`` is ``None`` the bucket is in *passthrough*
    mode: :meth:`acquire` returns immediately with no lock contention.
    This is the default and incurs virtually no overhead on read sites.

    When a rate is configured, ``acquire(n)`` blocks until ``n`` tokens are
    available.  Tokens replenish continuously at the configured rate; the
    bucket caps at one second of tokens to bound burst behaviour.

    Args:
        rate_mb_per_sec: Maximum sustained read bandwidth in megabytes per
            second (1 MB = 1_000_000 bytes).  ``None`` disables throttling.
        clock: Monotonic time source returning seconds.  Injectable so
            tests can advance a fake clock without using real
            ``time.sleep``.  Defaults to :func:`time.monotonic`.
        sleep: Sleep function taking seconds.  Injectable for the same
            reason.  Defaults to :func:`time.sleep`.

    Raises:
        ValueError: If ``rate_mb_per_sec`` is not strictly positive (and
            not ``None``).
    """

    def __init__(
        self,
        rate_mb_per_sec: float | None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Initialise the bucket and start its refill clock at ``clock()``."""
        if rate_mb_per_sec is not None and rate_mb_per_sec <= 0.0:
            raise ValueError("rate_mb_per_sec must be positive or None")
        self._rate_bytes_per_sec: float | None = (
            None if rate_mb_per_sec is None else float(rate_mb_per_sec) * _BYTES_PER_MB
        )
        # Capacity = one second of tokens.  Bounding the burst this way
        # means an idle bucket cannot accumulate enough credit to release a
        # huge backlog read without throttling — the worst-case burst is
        # exactly the configured rate.
        self._capacity: float = 0.0 if self._rate_bytes_per_sec is None else self._rate_bytes_per_sec
        self._tokens: float = self._capacity
        self._last_refill: float = clock()
        self._lock = threading.Lock()
        self._clock = clock
        self._sleep = sleep

    def acquire(self, n_bytes: int) -> None:
        """Block until ``n_bytes`` tokens are available, then deduct them.

        In passthrough mode (rate ``None``) this is a near-zero-cost no-op
        — no lock is taken and no clock read is performed.

        When a request exceeds the bucket capacity, the bucket drains
        whatever is available and sleeps for the remaining shortfall.  The
        sleep is performed *under the lock* so that concurrent callers
        serialise their bandwidth consumption — the configured rate is the
        aggregate ceiling across all workers.

        Args:
            n_bytes: Number of bytes the caller is about to read.  Must be
                non-negative.

        Raises:
            ValueError: If ``n_bytes`` is negative.
        """
        if n_bytes < 0:
            raise ValueError("n_bytes must be non-negative")
        # Fast passthrough path — no lock, no clock read.
        if self._rate_bytes_per_sec is None or n_bytes == 0:
            return

        with self._lock:
            self._refill_locked()
            needed = float(n_bytes)
            # First spend whatever tokens are already available.
            spent = min(self._tokens, needed)
            self._tokens -= spent
            needed -= spent
            if needed > 0:
                # Wait the exact time required to "earn" the deficit at the
                # configured rate.  After the sleep we treat the deficit as
                # consumed (tokens = 0); the next refill resumes from there.
                wait_seconds = needed / self._rate_bytes_per_sec
                self._sleep(wait_seconds)
                self._last_refill = self._clock()
                self._tokens = 0.0

    def _refill_locked(self) -> None:
        """Recompute the token count from elapsed wall-clock time.

        Must be called with ``self._lock`` held.  Caps the bucket at
        ``self._capacity`` to bound burst behaviour to one second of
        tokens regardless of how long the bucket has been idle.
        """
        if self._rate_bytes_per_sec is None:
            return
        now = self._clock()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        self._tokens = min(
            self._capacity,
            self._tokens + elapsed * self._rate_bytes_per_sec,
        )
        self._last_refill = now


# ---------------------------------------------------------------------------
# Process-wide active bucket
# ---------------------------------------------------------------------------

_active_bucket: TokenBucket | None = None
_active_bucket_lock = threading.Lock()


def set_active_bucket(bucket: TokenBucket | None) -> None:
    """Install the bucket consulted by :func:`acquire`.

    ``scan()`` calls this once at the start of a scan run (before spawning
    worker threads) and again with ``None`` at the end to clear state.
    Tests use the same hook to install a deterministic bucket and to
    restore the default ``None`` state after each test.

    Args:
        bucket: The bucket to install, or ``None`` to disable throttling.
    """
    global _active_bucket
    with _active_bucket_lock:
        _active_bucket = bucket


def get_active_bucket() -> TokenBucket | None:
    """Return the currently installed bucket, or ``None`` if none is set."""
    with _active_bucket_lock:
        return _active_bucket


def acquire(n_bytes: int) -> None:
    """Acquire ``n_bytes`` tokens from the active bucket if one is set.

    No-op when no bucket is installed (the common case in production runs
    where ``read_rate_mb_per_sec`` is ``None`` and in any test that does
    not exercise the throttle path).

    Args:
        n_bytes: Number of bytes the caller is about to read.
    """
    bucket = _active_bucket  # snapshot — avoids holding the install-lock
    if bucket is None:
        return
    bucket.acquire(n_bytes)
