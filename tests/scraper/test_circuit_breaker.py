"""Tests for the CircuitBreaker state machine.

Covers all state transitions: CLOSED → OPEN → HALF_OPEN → CLOSED,
error classification (5xx vs 429 vs 4xx), and reset behavior.
"""

import time
from unittest.mock import patch

import requests

from personalscraper.scraper.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from personalscraper.scraper.tmdb_client import TMDBError
from personalscraper.scraper.tvdb_client import TVDBError


class TestCircuitBreakerStates:
    """Test circuit breaker state machine transitions."""

    def test_initial_state_closed(self):
        """Circuit starts in CLOSED state with zero failures."""
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_proceed() is True

    def test_below_threshold_stays_closed(self):
        """4 failures (below threshold=5) keep the circuit CLOSED."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        error = TMDBError(500, 0, "Internal Server Error")

        for _ in range(4):
            cb.record_failure(error)

        assert cb.state == CircuitState.CLOSED
        assert cb.can_proceed() is True

    def test_threshold_reached_opens_circuit(self):
        """5 consecutive failures open the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        error = TMDBError(500, 0, "Internal Server Error")

        for _ in range(5):
            cb.record_failure(error)

        assert cb.state == CircuitState.OPEN
        assert cb.can_proceed() is False

    def test_open_blocks_calls(self):
        """OPEN circuit reports can_proceed() = False."""
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=300)
        error = TMDBError(502, 0, "Bad Gateway")

        cb.record_failure(error)
        cb.record_failure(error)

        assert cb.state == CircuitState.OPEN
        assert cb.can_proceed() is False

    def test_open_to_half_open_after_cooldown(self):
        """Circuit transitions to HALF_OPEN after cooldown elapsed."""
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=1.0)
        error = TMDBError(503, 0, "Service Unavailable")

        cb.record_failure(error)
        cb.record_failure(error)
        assert cb.state == CircuitState.OPEN

        # Simulate cooldown elapsed by patching monotonic
        with patch("personalscraper.scraper.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2.0
            assert cb.state == CircuitState.HALF_OPEN
            assert cb.can_proceed() is True

    def test_half_open_success_closes_circuit(self):
        """Successful call in HALF_OPEN state closes the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.01)
        error = TMDBError(500, 0, "Internal Server Error")

        cb.record_failure(error)
        cb.record_failure(error)
        assert cb.state == CircuitState.OPEN

        # Wait for very short cooldown
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_proceed() is True

    def test_half_open_failure_reopens_circuit(self):
        """Failed call in HALF_OPEN state reopens the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.01)
        error = TMDBError(500, 0, "Internal Server Error")

        cb.record_failure(error)
        cb.record_failure(error)
        assert cb.state == CircuitState.OPEN

        # Wait for cooldown
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        # One failure in HALF_OPEN → back to OPEN immediately
        cb.record_failure(error)
        assert cb.state == CircuitState.OPEN
        assert cb.can_proceed() is False


class TestCircuitBreakerErrorClassification:
    """Test which errors count toward the circuit vs are ignored."""

    def test_429_not_counted(self):
        """429 rate limit errors do NOT count (tenacity handles them)."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        rate_limit = TMDBError(429, 25, "Rate limit exceeded")

        for _ in range(10):
            cb.record_failure(rate_limit)

        # Circuit should still be CLOSED — 429 is not a circuit error
        assert cb.state == CircuitState.CLOSED

    def test_4xx_not_counted(self):
        """4xx client errors do NOT count (won't fix by retrying)."""
        cb = CircuitBreaker(name="test", failure_threshold=2)

        errors_4xx = [
            TMDBError(401, 7, "Invalid API key"),
            TMDBError(404, 34, "Not found"),
            TVDBError(400, "Bad request"),
        ]

        for err in errors_4xx:
            for _ in range(5):
                cb.record_failure(err)

        assert cb.state == CircuitState.CLOSED

    def test_5xx_tmdb_counted(self):
        """TMDB 5xx errors count toward the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        error = TMDBError(503, 0, "Service Unavailable")

        for _ in range(3):
            cb.record_failure(error)

        assert cb.state == CircuitState.OPEN

    def test_5xx_tvdb_counted(self):
        """TVDB 5xx errors count toward the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        error = TVDBError(502, "Bad Gateway")

        for _ in range(3):
            cb.record_failure(error)

        assert cb.state == CircuitState.OPEN

    def test_connection_error_counted(self):
        """Connection errors count toward the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        error = requests.exceptions.ConnectionError("Connection refused")

        cb.record_failure(error)
        cb.record_failure(error)

        assert cb.state == CircuitState.OPEN

    def test_timeout_error_counted(self):
        """Timeout errors count toward the circuit."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        error = requests.exceptions.Timeout("Read timed out")

        cb.record_failure(error)
        cb.record_failure(error)

        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """A success after partial failures resets the counter."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        error = TMDBError(500, 0, "Internal Server Error")

        # 4 failures, then a success
        for _ in range(4):
            cb.record_failure(error)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

        # Need 5 more failures to open (not 1)
        for _ in range(4):
            cb.record_failure(error)
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerReset:
    """Test manual reset behavior."""

    def test_reset_from_open(self):
        """reset() returns to CLOSED from OPEN state."""
        cb = CircuitBreaker(name="test", failure_threshold=2)
        error = TMDBError(500, 0, "Internal Server Error")

        cb.record_failure(error)
        cb.record_failure(error)
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_proceed() is True

    def test_reset_from_half_open(self):
        """reset() returns to CLOSED from HALF_OPEN state."""
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=0.01)
        error = TMDBError(500, 0, "Internal Server Error")

        cb.record_failure(error)
        cb.record_failure(error)
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestCircuitOpenError:
    """Test CircuitOpenError exception."""

    def test_attributes(self):
        """CircuitOpenError carries provider name and remaining time."""
        err = CircuitOpenError("TMDB", 42.5)
        assert err.provider == "TMDB"
        assert err.remaining_seconds == 42.5
        assert "TMDB" in str(err)
        assert "42" in str(err)

    def test_remaining_cooldown_calculation(self):
        """_remaining_cooldown() reports correct time left."""
        cb = CircuitBreaker(name="test", failure_threshold=2, cooldown_seconds=10.0)
        error = TMDBError(500, 0, "Internal Server Error")

        cb.record_failure(error)
        cb.record_failure(error)

        remaining = cb._remaining_cooldown()
        # Should be close to 10s (just opened)
        assert 9.0 <= remaining <= 10.0
