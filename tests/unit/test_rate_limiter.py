"""Tests for RateLimiter token-bucket."""

import time

from personalscraper.api.transport._rate import RateLimiter


def test_zero_rate_is_noop() -> None:
    """rate=0 — acquire() returns immediately."""
    limiter = RateLimiter(0.0)
    start = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - start < 0.01


def test_rate_limited_10rps() -> None:
    """20 calls at 10 rps should take at least ~1.9s."""
    limiter = RateLimiter(10.0)
    start = time.monotonic()
    for _ in range(20):
        limiter.acquire()
    elapsed = time.monotonic() - start
    assert elapsed >= 1.9, f"Expected >=1.9s, got {elapsed:.3f}s"


def test_single_acquire_is_fast() -> None:
    """First acquire at any rate is immediate (token bucket has initial capacity)."""
    limiter = RateLimiter(100.0)
    start = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - start < 0.01


def test_negative_rate_treated_as_noop() -> None:
    """Negative rate treated as no-op."""
    limiter = RateLimiter(-5.0)
    start = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - start < 0.01
