"""Unit tests for the login rate limiter (tm-shell feature).

Pure unit tests for :class:`SlidingWindowRateLimiter` — no FastAPI, no
TestClient.  A deterministic injected clock replaces wall-clock time so the
window-expiry test needs no ``sleep`` and cannot flake.

See docs/features/tm-shell/DESIGN.md §4.4.
"""

from __future__ import annotations

from personalscraper.web.auth.ratelimit import SlidingWindowRateLimiter


class _FakeClock:
    """A manually-advanced monotonic clock for deterministic window tests."""

    def __init__(self, start: float = 1000.0) -> None:
        """Initialise the clock at *start* seconds.

        Args:
            start: The initial time value.
        """
        self.now = start

    def __call__(self) -> float:
        """Return the current fake time.

        Returns:
            The current clock value in seconds.
        """
        return self.now


class TestThreshold:
    """Allow/block behaviour around the failed-attempt threshold."""

    def test_allows_until_threshold_then_blocks(self) -> None:
        """Five failures are permitted; the limiter blocks once the fifth lands."""
        limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=60.0, clock=_FakeClock())
        key = "1.2.3.4"
        for _ in range(5):
            assert limiter.allow(key) is True
            limiter.record_failure(key)
        # Threshold reached → further attempts are blocked.
        assert limiter.allow(key) is False

    def test_reset_clears_key(self) -> None:
        """``reset`` restores a blocked key to allowed."""
        limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=60.0, clock=_FakeClock())
        key = "1.2.3.4"
        for _ in range(5):
            limiter.record_failure(key)
        assert limiter.allow(key) is False
        limiter.reset(key)
        assert limiter.allow(key) is True

    def test_clear_resets_all_keys(self) -> None:
        """``clear`` drops the failure history for every key."""
        limiter = SlidingWindowRateLimiter(max_attempts=2, window_seconds=60.0, clock=_FakeClock())
        for key in ("a", "b"):
            limiter.record_failure(key)
            limiter.record_failure(key)
            assert limiter.allow(key) is False
        limiter.clear()
        assert limiter.allow("a") is True
        assert limiter.allow("b") is True


class TestKeyIsolation:
    """One client's lockout must not affect another key."""

    def test_keys_are_independent(self) -> None:
        """Blocking one key leaves a different key fully allowed."""
        limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=60.0, clock=_FakeClock())
        blocked = "10.0.0.1"
        other = "10.0.0.2"
        for _ in range(5):
            limiter.record_failure(blocked)
        assert limiter.allow(blocked) is False
        # A different client is unaffected.
        assert limiter.allow(other) is True


class TestWindowExpiry:
    """Failures age out of the rolling window."""

    def test_window_expiry_reallows(self) -> None:
        """Once the window elapses, a previously blocked key is allowed again."""
        clock = _FakeClock(start=1000.0)
        limiter = SlidingWindowRateLimiter(max_attempts=5, window_seconds=60.0, clock=clock)
        key = "1.2.3.4"
        for _ in range(5):
            limiter.record_failure(key)
        assert limiter.allow(key) is False

        # Advance past the window — all recorded failures expire.
        clock.now += 61.0
        assert limiter.allow(key) is True
