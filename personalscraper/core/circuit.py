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

Event-bus integration: every breaker carries a required ``EventBus``.
State transitions emit :class:`CircuitBreakerOpened` /
:class:`CircuitBreakerClosed` / :class:`CircuitBreakerHalfOpened` so
subscribers (Telegram alerts, debug log, future Web UI) can react. The
ContextVar ``current_correlation_id`` is captured at event construction
time, so trips inside a pipeline run carry that run's ``correlation_id``
even though the breaker itself is a long-lived singleton (DESIGN
§ContextVar capture semantics).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum

import requests

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.core.event_bus import Event, EventBus
from personalscraper.logger import get_logger

log = get_logger("circuit_breaker")


@dataclass(frozen=True, kw_only=True)
class CircuitBreakerOpened(Event):
    """Emitted when a breaker transitions from CLOSED / HALF_OPEN to OPEN.

    Attributes:
        breaker: Logical breaker name (e.g. ``"tmdb"``, ``"trailers_youtube"``).
        failure_count: Consecutive failure count that triggered the trip
            (always ``>= 1``; HALF_OPEN → OPEN reopens carry the threshold).
        last_error_class: ``type(exc).__name__`` of the failure that pushed
            the breaker over the threshold (or caused the reopen).
        last_error_message: ``str(exc)`` of that same failure.
    """

    breaker: str
    failure_count: int
    last_error_class: str
    last_error_message: str


@dataclass(frozen=True, kw_only=True)
class CircuitBreakerClosed(Event):
    """Emitted when a breaker transitions OPEN / HALF_OPEN → CLOSED.

    Attributes:
        breaker: Logical breaker name (matches the trip event's ``breaker``).
    """

    breaker: str


@dataclass(frozen=True, kw_only=True)
class CircuitBreakerHalfOpened(Event):
    """Emitted when a breaker transitions OPEN → HALF_OPEN after cooldown.

    Attributes:
        breaker: Logical breaker name (matches the trip event's ``breaker``).
    """

    breaker: str


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
        name: str = "anonymous",
        failure_threshold: int = 5,
        cooldown_seconds: float = 300.0,
        *,
        event_bus: EventBus,
    ) -> None:
        """Initialize the circuit breaker in CLOSED state.

        Args:
            name: Provider name (e.g. "TMDB", "TVDB"). Default ``"anonymous"``
                keeps lazy / test-only constructions valid; production sites
                pass a meaningful name so :class:`CircuitBreakerOpened` events
                carry an actionable ``breaker`` field for Telegram alerts.
            failure_threshold: Number of consecutive failures to trigger OPEN.
            cooldown_seconds: Seconds to wait before allowing a test call.
            event_bus: :class:`EventBus` used to publish state transitions
                (:class:`CircuitBreakerOpened` / :class:`CircuitBreakerClosed`
                / :class:`CircuitBreakerHalfOpened`). Required — every
                construction site, production or test, must thread an
                explicit bus. Tests that don't care about emit can pass
                a fresh ``EventBus()`` with no subscribers.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float = 0.0
        self._event_bus = event_bus
        # Guards state mutations + transition emits. Required because the
        # indexer scanner exercises shared breakers from a ThreadPoolExecutor
        # (DESIGN deviation): without the lock, two concurrent ``state``
        # reads after cooldown can both transition OPEN→HALF_OPEN and both
        # emit ``CircuitBreakerHalfOpened`` → duplicate Telegram alerts.
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Return the current circuit state.

        Side effect: when the cooldown has fully elapsed and the breaker is
        OPEN, this property transitions ``OPEN → HALF_OPEN`` and emits
        :class:`CircuitBreakerHalfOpened` on the bus before returning. The
        transition is performed atomically under ``self._lock`` so concurrent
        readers race to a single emit.

        Returns:
            Current CircuitState (CLOSED, OPEN, or HALF_OPEN).
        """
        emit_half_open = False
        with self._lock:
            # Auto-transition OPEN → HALF_OPEN when cooldown has elapsed.
            if self._state == CircuitState.OPEN and self._cooldown_elapsed():
                self._state = CircuitState.HALF_OPEN
                emit_half_open = True
            current = self._state
        if emit_half_open:
            log.info("circuit_half_open", provider=self.name)
            self._event_bus.emit(
                CircuitBreakerHalfOpened(
                    source=f"core.circuit.{self.name}",
                    breaker=self.name,
                ),
            )
        return current

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
        with self._lock:
            previous_state = self._state
            was_open = previous_state != CircuitState.CLOSED
            self._state = CircuitState.CLOSED
            self._failure_count = 0
        if was_open:
            log.info("circuit_closed", provider=self.name, previous_state=previous_state.value)
            # Emit only on actual transition: CLOSED → CLOSED is a no-op for
            # the bus (CircuitBreakerClosed is a transition event, not a
            # heartbeat). Long-lived breakers receive thousands of successes
            # per pipeline run; emitting on every one would flood subscribers.
            self._event_bus.emit(
                CircuitBreakerClosed(
                    source=f"core.circuit.{self.name}",
                    breaker=self.name,
                ),
            )

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

        # State transition under the lock; emit OUTSIDE the lock so the bus
        # fan-out doesn't serialize concurrent record_* callers.
        emit_failure_count: int | None = None
        is_reopen = False
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # HALF_OPEN: one failure → back to OPEN.
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                # Re-trip from the half-open probe — the canonical failure
                # count for this re-open is the configured threshold (the
                # probe call is the "one and only" attempted recovery, and
                # its failure constitutes a full trip regardless of
                # self._failure_count which is not decremented on enter).
                emit_failure_count = self.failure_threshold
                is_reopen = True
            else:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    self._opened_at = time.monotonic()
                    emit_failure_count = self._failure_count

        if emit_failure_count is None:
            return
        if is_reopen:
            log.warning("circuit_reopened", provider=self.name, error=str(exc))
        else:
            log.warning(
                "circuit_opened",
                provider=self.name,
                failure_count=emit_failure_count,
                cooldown_seconds=self.cooldown_seconds,
            )
        self._event_bus.emit(
            CircuitBreakerOpened(
                source=f"core.circuit.{self.name}",
                breaker=self.name,
                failure_count=emit_failure_count,
                last_error_class=type(exc).__name__,
                last_error_message=str(exc),
            ),
        )

    def reset(self) -> None:
        """Reset the circuit to CLOSED state.

        Intended for testing and manual recovery.
        """
        with self._lock:
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
