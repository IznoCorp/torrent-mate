"""Per-disk circuit breaker for the media indexer.

Wraps :class:`~personalscraper.core.circuit.CircuitBreaker` with a
dict-keyed-by-disk-UUID interface so the scanner can guard individual disks
against repeated I/O failures (``EIO``, vanishing mounts) without blocking
access to healthy disks.

State machine per disk (delegated to the underlying CircuitBreaker):
    CLOSED  -(N failures)->  OPEN  -(cooldown elapsed)->  HALF_OPEN
    HALF_OPEN -(success)-> CLOSED
    HALF_OPEN -(failure)-> OPEN

A module-level singleton :data:`_GLOBAL_DISK_BREAKER` is created at import
time so callers can import and use :func:`get_global_disk_breaker` without
dependency injection.  Tests that need isolation should instantiate
:class:`DiskCircuitBreaker` directly.
"""

from __future__ import annotations

import time

from personalscraper.logger import get_logger
from personalscraper.core.circuit import CircuitBreaker, CircuitState

log = get_logger("indexer.breaker")


class DiskCircuitBreaker:
    """A per-disk circuit breaker registry backed by :class:`CircuitBreaker`.

    Lazily creates one :class:`~personalscraper.core.circuit.CircuitBreaker`
    instance per disk UUID on first access.  All breakers share the same
    ``failure_threshold`` and ``cooldown_seconds`` configuration.

    Attributes:
        failure_threshold: Number of consecutive I/O failures before a disk's
            circuit opens.
        cooldown_seconds: Seconds to wait in OPEN state before the circuit
            transitions to HALF_OPEN and allows a test scan.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        cooldown_seconds: float = 300.0,
    ) -> None:
        """Initialise a DiskCircuitBreaker registry.

        Args:
            failure_threshold: Consecutive failures before opening the circuit
                for a given disk.  Defaults to 3 (lower than the API default of
                5 because a single EIO is already serious for disk I/O).
            cooldown_seconds: Seconds in OPEN state before allowing a retry.
                Defaults to 300 (5 minutes).
        """
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        # Lazily created per-disk CircuitBreaker instances.
        self._breakers: dict[str, CircuitBreaker] = {}
        # Per-disk consecutive I/O failure counter (separate from HTTP circuit).
        self._failure_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_breaker(self, disk_uuid: str) -> CircuitBreaker:
        """Return (creating if necessary) the CircuitBreaker for *disk_uuid*.

        Breakers are created lazily on first access so there is no need to
        pre-register disks.

        Args:
            disk_uuid: Volume UUID string that identifies the disk uniquely.

        Returns:
            The :class:`CircuitBreaker` instance for this disk.
        """
        if disk_uuid not in self._breakers:
            self._breakers[disk_uuid] = CircuitBreaker(
                name=f"disk:{disk_uuid}",
                failure_threshold=self.failure_threshold,
                cooldown_seconds=self.cooldown_seconds,
            )
        return self._breakers[disk_uuid]

    def is_open(self, disk_uuid: str) -> bool:
        """Return ``True`` if the circuit for *disk_uuid* is currently OPEN.

        A newly-seen disk UUID always returns ``False`` (no failures recorded
        yet -- circuit starts CLOSED).

        Args:
            disk_uuid: Volume UUID string identifying the disk.

        Returns:
            ``True`` when the circuit is OPEN (disk should be skipped);
            ``False`` when CLOSED or HALF_OPEN (disk may be attempted).
        """
        # Avoid lazy-creating a breaker just to check if it's open.
        if disk_uuid not in self._breakers:
            return False
        breaker = self._breakers[disk_uuid]
        # Access .state to trigger OPEN->HALF_OPEN auto-transition on cooldown.
        return breaker.state == CircuitState.OPEN

    def record_failure(self, disk_uuid: str) -> None:
        """Record a disk I/O failure; may open the circuit for *disk_uuid*.

        Implementation note: the underlying ``CircuitBreaker._is_circuit_error``
        only counts HTTP/provider errors, not ``OSError``.  For disk breakers we
        therefore maintain a parallel failure counter here and open the circuit
        manually when the threshold is reached, writing directly to the
        ``CircuitBreaker`` private state (``_state``, ``_opened_at``).  This is
        intentional -- the breaker state machine is correct; only the error
        classification differs for disk I/O vs. HTTP providers.

        Args:
            disk_uuid: Volume UUID string identifying the disk.
        """
        breaker = self.get_breaker(disk_uuid)
        count = self._failure_counts.get(disk_uuid, 0) + 1
        self._failure_counts[disk_uuid] = count
        log.debug("indexer.disk.breaker_failure", disk_uuid=disk_uuid, failure_count=count)

        if count >= self.failure_threshold:
            # Directly open the circuit -- bypass _is_circuit_error which only
            # handles HTTP provider errors.
            breaker._state = CircuitState.OPEN  # pyright: ignore[reportPrivateUsage]
            breaker._opened_at = time.monotonic()  # pyright: ignore[reportPrivateUsage]
            log.warning(
                "indexer.disk.breaker_open",
                disk_uuid=disk_uuid,
                failure_count=count,
                cooldown_seconds=self.cooldown_seconds,
            )

    def record_success(self, disk_uuid: str) -> None:
        """Record a successful disk scan; closes the circuit for *disk_uuid*.

        Resets the internal failure counter and delegates to
        :meth:`CircuitBreaker.record_success` which transitions OPEN/HALF_OPEN
        to CLOSED.

        Args:
            disk_uuid: Volume UUID string identifying the disk.
        """
        breaker = self.get_breaker(disk_uuid)
        breaker.record_success()
        self._failure_counts[disk_uuid] = 0
        log.debug("indexer.disk.breaker_success", disk_uuid=disk_uuid)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Global singleton used by the scanner.  Tests that need isolation should
#: instantiate :class:`DiskCircuitBreaker` directly and pass it to ``scan()``.
_GLOBAL_DISK_BREAKER: DiskCircuitBreaker = DiskCircuitBreaker()


def get_global_disk_breaker() -> DiskCircuitBreaker:
    """Return the module-level :class:`DiskCircuitBreaker` singleton.

    Returns:
        The global :data:`_GLOBAL_DISK_BREAKER` instance.
    """
    return _GLOBAL_DISK_BREAKER
