"""Tests for :class:`CircuitBreaker` event emits — Sub-phase 4.1 + Sub-phase 5.1.

Covers the three transition events (:class:`CircuitBreakerOpened`,
:class:`CircuitBreakerClosed`, :class:`CircuitBreakerHalfOpened`), the
required-``event_bus`` signature contract (Sub-phase 5.1), the ``source``
derivation, the ContextVar-capture invariant for long-lived breakers
(DESIGN §ContextVar capture semantics), and the registry/factory/envelope
round-trip plumbing required for the Phase 4 gate.
"""

from __future__ import annotations

import time

import pytest
import requests

from personalscraper.api._contracts import ApiError
from personalscraper.core.circuit import (
    CircuitBreaker,
    CircuitBreakerClosed,
    CircuitBreakerHalfOpened,
    CircuitBreakerOpened,
)
from personalscraper.core.event_bus import (
    EventBus,
    current_correlation_id,
    event_from_envelope,
    event_to_envelope,
)
from tests.fixtures.event_bus import CollectingSubscriber, assert_event_round_trip
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES


def _server_error_exc() -> ApiError:
    """Build a circuit-eligible 5xx ApiError instance."""
    return ApiError(provider="tmdb", http_status=503, message="Service Unavailable")


def test_circuit_breaker_emits_opened_on_trip() -> None:
    """Reaching the failure threshold emits exactly one ``CircuitBreakerOpened``."""
    bus = EventBus()
    collector: CollectingSubscriber[CircuitBreakerOpened] = CollectingSubscriber(bus, CircuitBreakerOpened)
    cb = CircuitBreaker(name="tmdb", failure_threshold=3, cooldown_seconds=300.0, event_bus=bus)

    for _ in range(3):
        cb.record_failure(_server_error_exc())

    assert len(collector.received) == 1
    event = collector.received[0]
    assert event.breaker == "tmdb"
    assert event.failure_count == 3
    assert event.last_error_class == "ApiError"
    assert "Service Unavailable" in event.last_error_message


def test_circuit_breaker_emits_closed_on_recovery() -> None:
    """A success after a trip emits exactly one ``CircuitBreakerClosed``."""
    bus = EventBus()
    closed_collector: CollectingSubscriber[CircuitBreakerClosed] = CollectingSubscriber(bus, CircuitBreakerClosed)
    cb = CircuitBreaker(name="tmdb", failure_threshold=2, cooldown_seconds=300.0, event_bus=bus)

    # Trip the circuit.
    cb.record_failure(_server_error_exc())
    cb.record_failure(_server_error_exc())
    # Force HALF_OPEN by accessing state after manually setting opened_at to past.
    cb._opened_at = time.monotonic() - 1.0  # noqa: SLF001
    cb.cooldown_seconds = 0.0
    assert cb.can_proceed()  # auto-transition to HALF_OPEN
    cb.record_success()  # HALF_OPEN → CLOSED

    assert len(closed_collector.received) == 1
    assert closed_collector.received[0].breaker == "tmdb"


def test_circuit_breaker_emits_half_opened_on_probe() -> None:
    """Cooldown elapse from OPEN emits exactly one ``CircuitBreakerHalfOpened``."""
    bus = EventBus()
    half_collector: CollectingSubscriber[CircuitBreakerHalfOpened] = CollectingSubscriber(bus, CircuitBreakerHalfOpened)
    cb = CircuitBreaker(name="tmdb", failure_threshold=1, cooldown_seconds=0.01, event_bus=bus)
    cb.record_failure(_server_error_exc())  # → OPEN
    time.sleep(0.02)
    assert cb.can_proceed()  # triggers OPEN → HALF_OPEN

    assert len(half_collector.received) == 1
    assert half_collector.received[0].breaker == "tmdb"


def test_circuit_breaker_reopen_from_half_open_emits_opened() -> None:
    """A failure in HALF_OPEN re-emits ``CircuitBreakerOpened`` with the threshold count."""
    bus = EventBus()
    opened_collector: CollectingSubscriber[CircuitBreakerOpened] = CollectingSubscriber(bus, CircuitBreakerOpened)
    cb = CircuitBreaker(name="tmdb", failure_threshold=2, cooldown_seconds=0.01, event_bus=bus)
    cb.record_failure(_server_error_exc())
    cb.record_failure(_server_error_exc())  # → OPEN, emit #1
    time.sleep(0.02)
    cb.can_proceed()  # → HALF_OPEN
    cb.record_failure(_server_error_exc())  # HALF_OPEN → OPEN, emit #2

    assert len(opened_collector.received) == 2
    assert opened_collector.received[1].failure_count == 2  # threshold value


def test_circuit_breaker_requires_event_bus() -> None:
    """``CircuitBreaker.__init__`` requires ``event_bus`` (no default).

    Sub-phase 5.1 tightens the migration-time ``event_bus: EventBus | None = None``
    to ``event_bus: EventBus`` (required, no default). Every production and test
    construction site must now pass an explicit bus — the absence-of-bus path
    is no longer a supported contract.
    """
    import inspect

    sig = inspect.signature(CircuitBreaker.__init__)
    assert sig.parameters["event_bus"].default is inspect.Parameter.empty, (
        "event_bus must have no default — make construction sites explicit"
    )


def test_circuit_breaker_event_bus_annotation_excludes_none() -> None:
    """``CircuitBreaker.__init__`` annotates ``event_bus`` as ``EventBus``, not ``EventBus | None``.

    Annotation-level guarantee that the ``| None`` migration contract has been
    removed — mypy strict, tests, and the audit grep all rely on this shape.
    """
    import inspect

    sig = inspect.signature(CircuitBreaker.__init__)
    annotation = sig.parameters["event_bus"].annotation
    annotation_str = str(annotation)
    assert "None" not in annotation_str, f"event_bus annotation must not allow None; got {annotation_str!r}"


def test_circuit_breaker_event_source_includes_name() -> None:
    """Emitted events derive ``source`` from the breaker name."""
    bus = EventBus()
    collector: CollectingSubscriber[CircuitBreakerOpened] = CollectingSubscriber(bus, CircuitBreakerOpened)
    cb = CircuitBreaker(name="tmdb", failure_threshold=1, cooldown_seconds=300.0, event_bus=bus)
    cb.record_failure(_server_error_exc())

    assert len(collector.received) == 1
    assert collector.received[0].source == "core.circuit.tmdb"


def test_circuit_breaker_long_lived_singleton_captures_correlation_id() -> None:
    """A breaker constructed once, tripped inside a ContextVar-bound region, carries the run's correlation_id.

    Proves the DESIGN ContextVar capture semantics for long-lived emitters
    that pre-exist any pipeline run.
    """
    bus = EventBus()
    collector: CollectingSubscriber[CircuitBreakerOpened] = CollectingSubscriber(bus, CircuitBreakerOpened)
    cb = CircuitBreaker(name="tmdb", failure_threshold=1, cooldown_seconds=300.0, event_bus=bus)

    token = current_correlation_id.set("run-xyz")
    try:
        cb.record_failure(_server_error_exc())
    finally:
        current_correlation_id.reset(token)

    assert len(collector.received) == 1
    assert collector.received[0].correlation_id == "run-xyz"


def test_circuit_breaker_events_have_factories() -> None:
    """All three transition events are registered in ``EVENT_SAMPLE_FACTORIES``."""
    for cls in (CircuitBreakerOpened, CircuitBreakerClosed, CircuitBreakerHalfOpened):
        assert cls in EVENT_SAMPLE_FACTORIES, f"{cls.__name__} missing from EVENT_SAMPLE_FACTORIES"


@pytest.mark.parametrize(
    "event_cls",
    [CircuitBreakerOpened, CircuitBreakerClosed, CircuitBreakerHalfOpened],
)
def test_circuit_breaker_events_envelope_roundtrip(event_cls: type) -> None:
    """Each transition event survives ``event_to_envelope`` / ``event_from_envelope``."""
    original = EVENT_SAMPLE_FACTORIES[event_cls]()
    envelope = event_to_envelope(original)
    assert envelope["_type"] == event_cls.__name__
    reconstructed = event_from_envelope(envelope)
    assert type(reconstructed) is event_cls
    assert_event_round_trip(original, reconstructed)


def test_circuit_breaker_success_when_already_closed_does_not_emit() -> None:
    """``record_success`` from CLOSED is a no-op for the bus (heartbeat suppression)."""
    bus = EventBus()
    collector: CollectingSubscriber[CircuitBreakerClosed] = CollectingSubscriber(bus, CircuitBreakerClosed)
    cb = CircuitBreaker(name="tmdb", failure_threshold=5, cooldown_seconds=300.0, event_bus=bus)
    for _ in range(10):
        cb.record_success()
    assert collector.received == []


def test_circuit_breaker_non_eligible_error_does_not_emit() -> None:
    """A non-circuit-eligible failure (4xx, non-network) does not emit anything."""
    bus = EventBus()
    collector: CollectingSubscriber = CollectingSubscriber(bus)
    cb = CircuitBreaker(name="tmdb", failure_threshold=1, cooldown_seconds=300.0, event_bus=bus)
    # 404 is not a circuit error per ``_is_circuit_error``.
    cb.record_failure(ApiError(provider="tmdb", http_status=404, message="not found"))
    cb.record_failure(requests.exceptions.HTTPError(response=type("R", (), {"status_code": 400})()))
    assert collector.received == []
