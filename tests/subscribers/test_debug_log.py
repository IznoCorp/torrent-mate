"""Tests for :class:`DebugLogSubscriber` — Sub-phase 5.3.

Verifies the subscriber:
- subscribes to :class:`Event` (single MRO-routed subscription).
- logs every emit at DEBUG with the right envelope payload.
- works for every concrete event in the v1 catalog.
- stops receiving events after ``close()`` unsubscribes.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from personalscraper.core.event_bus import Event, EventBus
from personalscraper.subscribers.debug_log import DebugLogSubscriber
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES


def _capture_structlog(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    """Return parsed structlog records captured at DEBUG level.

    Structlog passes the ``event_dict`` as the standard-logging record's
    ``msg`` attribute (when the project's renderer is not configured to
    render it to a string in the test environment). Each entry returned
    has ``event``, ``event_type``, ``event_id``, ``correlation_id``,
    ``source``, and ``payload`` keys lifted from the underlying dict.
    """
    out: list[dict[str, Any]] = []
    for record in caplog.records:
        if record.levelno != logging.DEBUG:
            continue
        msg = record.msg
        if not isinstance(msg, dict):
            continue
        out.append(
            {
                "event": msg.get("event"),
                "event_type": msg.get("event_type"),
                "event_id": msg.get("event_id"),
                "correlation_id": msg.get("correlation_id"),
                "source": msg.get("source"),
                "payload": msg.get("payload"),
            }
        )
    return out


def test_debug_log_subscriber_subscribes_to_event_base() -> None:
    """Instantiating the subscriber adds one subscription for :class:`Event`."""
    bus = EventBus()
    sub = DebugLogSubscriber(bus)

    # The subscription token's event_type is exactly Event (MRO walk does the rest).
    assert sub._token.event_type is Event  # noqa: SLF001


def test_debug_log_subscriber_logs_at_debug_for_any_event(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Emitting any event yields exactly one DEBUG log entry with payload metadata."""
    bus = EventBus()
    DebugLogSubscriber(bus)
    # Pick a concrete event with a factory so we get a real instance.
    factory = next(iter(EVENT_SAMPLE_FACTORIES.values()))
    event = factory()

    with caplog.at_level(logging.DEBUG, logger="debug_log_subscriber"):
        bus.emit(event)

    records = _capture_structlog(caplog)
    matching = [r for r in records if r["event"] == "event_emitted"]
    assert len(matching) == 1, f"expected 1 event_emitted log, got {len(matching)}: {records}"
    rec = matching[0]
    assert rec["event_type"] == type(event).__name__
    assert rec["event_id"] == str(event.event_id)
    assert rec["source"] == event.source
    assert isinstance(rec["payload"], dict)


@pytest.mark.parametrize(
    "event_cls,factory",
    list(EVENT_SAMPLE_FACTORIES.items()),
    ids=[cls.__name__ for cls in EVENT_SAMPLE_FACTORIES],
)
def test_debug_log_subscriber_logs_for_every_event_type(
    caplog: pytest.LogCaptureFixture,
    event_cls: type[Event],
    factory: Any,
) -> None:
    """Every event in the v1 catalog produces a DEBUG log with the right type."""
    bus = EventBus()
    DebugLogSubscriber(bus)
    event = factory()

    with caplog.at_level(logging.DEBUG, logger="debug_log_subscriber"):
        bus.emit(event)

    records = _capture_structlog(caplog)
    matching = [r for r in records if r["event"] == "event_emitted" and r["event_type"] == event_cls.__name__]
    assert len(matching) == 1, f"{event_cls.__name__}: expected 1 log, got {len(matching)}"


def test_debug_log_subscriber_close_unsubscribes(caplog: pytest.LogCaptureFixture) -> None:
    """After ``close()``, the subscriber no longer receives events."""
    bus = EventBus()
    sub = DebugLogSubscriber(bus)
    sub.close()
    factory = next(iter(EVENT_SAMPLE_FACTORIES.values()))

    with caplog.at_level(logging.DEBUG, logger="debug_log_subscriber"):
        bus.emit(factory())

    records = _capture_structlog(caplog)
    matching = [r for r in records if r["event"] == "event_emitted"]
    assert matching == [], f"unsubscribed subscriber still received: {matching}"
