"""Circuit breaker pattern for API providers.

Protects the pipeline against sustained API outages by tracking
consecutive failures and short-circuiting calls when a provider is down.

Works above tenacity (which handles transient errors like 429/timeouts):
- tenacity retries individual calls with exponential backoff
- CircuitBreaker detects when a provider is durably down (N consecutive
  failures) and prevents further calls for a cooldown period

State machine:
    CLOSED  →(N failures)→  OPEN  →(cooldown elapsed)→  HALF_OPEN
    HALF_OPEN →(success)→ CLOSED
    HALF_OPEN →(failure)→ OPEN
"""

import time
from enum import Enum

import requests

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.logger import get_logger

log = get_logger("circuit_breaker")


class CircuitState(Enum):
    """Circuit breaker states.

    Attributes:
        CLOSED: Normal operation — calls go through, failures are counted.
        OPEN: Provider considered down — all calls raise CircuitOpenError.
        HALF_OPEN: After cooldown — one test call is allowed.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Generic circuit breaker for API providers.

    Tracks consecutive errors and opens the circuit when the threshold
    is reached. After a cooldown period, allows one test call (HALF_OPEN).
    A successful test call closes the circuit; a failure reopens it.

    Only counts server errors (5xx), timeouts, and connection errors.
    Does NOT count 429 (rate limit — handled by tenacity) or 4xx (client
    errors that won't resolve by retrying later).

    Attributes:
        name: Provider name (for logging and error messages).
        failure_threshold: Consecutive errors before opening the circuit.
        cooldown_seconds: Wait time in OPEN state before transitioning
            to HALF_OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        cooldown_seconds: float = 300.0,
    ) -> None:
        """Initialize the circuit breaker in CLOSED state.

        Args:
            name: Provider name (e.g. "TMDB", "TVDB").
            failure_threshold: Number of consecutive failures to trigger OPEN.
            cooldown_seconds: Seconds to wait before allowing a test call.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0

    @property
    def state(self) -> CircuitState:
        """Return the current circuit state.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN).
        """
        # Auto-transition OPEN → HALF_OPEN when cooldown has elapsed
        if self._state == CircuitState.OPEN and self._cooldown_elapsed():
            self._state = CircuitState.HALF_OPEN
            log.info("circuit_half_open", provider=self.name)
        return self._state

    def can_proceed(self) -> bool:
        """Check if a call is allowed through the circuit.

        Returns:
            True if the circuit is CLOSED or HALF_OPEN (cooldown elapsed).
            False if OPEN and cooldown has not elapsed.
        """
        return self.state != CircuitState.OPEN

    def guard(self) -> None:
        """Raise CircuitOpenError if the circuit is OPEN.

        Centralizes the check-then-raise pattern so callers don't need
        to access _remaining_cooldown() directly.

        Raises:
            CircuitOpenError: If the circuit is OPEN.
        """
        if not self.can_proceed():
            raise CircuitOpenError(self.name, self._remaining_cooldown())

    def record_success(self) -> None:
        """Record a successful API call.

        Resets the failure counter and closes the circuit.
        In HALF_OPEN state, this confirms the provider is back up.
        """
        if self._state != CircuitState.CLOSED:
            log.info("circuit_closed", provider=self.name, previous_state=self._state.value)
        self._state = CircuitState.CLOSED
        self._failure_count = 0

    def record_failure(self, exc: Exception) -> None:
        """Record a failed API call.

        Only counts circuit-eligible errors (5xx, timeout, connection).
        Ignores 429 (rate limit) and 4xx (client errors).

        In HALF_OPEN state, any circuit error reopens the circuit
        immediately (no threshold — one failure is enough).

        Args:
            exc: The exception from the failed call.
        """
        if not self._is_circuit_error(exc):
            return

        # HALF_OPEN: one failure → back to OPEN
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            log.warning("circuit_reopened", provider=self.name, error=str(exc))
            return

        self._failure_count += 1
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()
            log.warning(
                "circuit_opened",
                provider=self.name,
                failure_count=self._failure_count,
                cooldown_seconds=self.cooldown_seconds,
            )

    def reset(self) -> None:
        """Reset the circuit to CLOSED state.

        Intended for testing and manual recovery.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at = 0.0

    def _remaining_cooldown(self) -> float:
        """Calculate remaining cooldown time in seconds.

        Returns:
            Seconds remaining until the circuit can transition to
            HALF_OPEN. Returns 0.0 if cooldown has already elapsed.
        """
        if self._opened_at == 0.0:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        remaining = self.cooldown_seconds - elapsed
        return max(0.0, remaining)

    def _cooldown_elapsed(self) -> bool:
        """Check if the cooldown period has fully elapsed.

        Returns:
            True if enough time has passed since the circuit opened.
        """
        return self._remaining_cooldown() == 0.0

    @staticmethod
    def _is_circuit_error(exc: Exception) -> bool:
        """Determine if an exception should count toward the circuit.

        Counts: 5xx server errors, timeouts, connection errors.
        Ignores: 429 (rate limit — tenacity handles these),
                 4xx client errors (won't fix themselves).

        Args:
            exc: The exception to classify.

        Returns:
            True if the error indicates a provider outage.
        """
        from personalscraper.api._contracts import ApiError

        if isinstance(exc, ApiError):
            return exc.http_status >= 500

        # requests HTTP errors
        if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
            status = exc.response.status_code
            return status >= 500

        # Network-level failures → always circuit errors
        if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
            return True

        return False
