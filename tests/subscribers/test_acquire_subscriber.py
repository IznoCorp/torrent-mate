# tests/subscribers/test_acquire_subscriber.py
"""Non-vacuous dispatch tests for AcquisitionTelegramSubscriber.

Tests verify:
1. Every handler fires when its event is emitted.
2. Each handler formats a non-empty string message and logs a structlog line.
3. With enabled=True + a mocked notifier: notifier.send called exactly once.
4. With enabled=False (default): notifier.send never called.
5. A notifier that raises does not propagate (fail-soft contract).
6. close() unsubscribes — after close, emitting does not call the handler.
"""

from __future__ import annotations

import re
import time
from unittest.mock import MagicMock

import pytest

import personalscraper.events  # noqa: F401 — eager-import acquire events
from personalscraper.acquire.events import (
    GrabFailed,
    GrabSucceeded,
    RatioMeasured,
    SeedObligationBreached,
    SeedObligationRecorded,
    SeedObligationSatisfied,
    SeriesFollowed,
    SeriesUnfollowed,
    WantedAbandoned,
    WantedEnqueued,
)
from personalscraper.core.event_bus import EventBus
from personalscraper.core.identity import MediaRef
from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES

_REF = MediaRef(tvdb_id=81189)

_ALL_ACQUIRE_EVENT_CLASSES = [
    SeriesFollowed,
    SeriesUnfollowed,
    WantedEnqueued,
    WantedAbandoned,
    GrabSucceeded,
    GrabFailed,
    SeedObligationRecorded,
    SeedObligationBreached,
    SeedObligationSatisfied,
    RatioMeasured,
]


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase event name to snake_case handler name."""
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return s


def _make_bus_and_sub(
    enabled: bool = False,
) -> tuple[EventBus, AcquisitionTelegramSubscriber, MagicMock]:
    """Return a fresh bus + subscriber + mock notifier triple."""
    bus = EventBus()
    notifier = MagicMock()
    notifier.send.return_value = True
    sub = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=enabled)
    return bus, sub, notifier


# ---------------------------------------------------------------------------
# 1. enabled=False → notifier.send NEVER called (muted mode)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_cls", _ALL_ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_handler_disabled_does_not_send(event_cls: type) -> None:
    """With enabled=False, notifier.send is never called (muted mode)."""
    bus, sub, notifier = _make_bus_and_sub(enabled=False)
    event = EVENT_SAMPLE_FACTORIES[event_cls]()
    bus.emit(event)
    notifier.send.assert_not_called()
    sub.close()


# ---------------------------------------------------------------------------
# 2. enabled=True → notifier.send called once
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_cls", _ALL_ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_handler_enabled_sends_once(event_cls: type) -> None:
    """With enabled=True + mocked notifier, notifier.send is called exactly once per emit."""
    bus, sub, notifier = _make_bus_and_sub(enabled=True)
    event = EVENT_SAMPLE_FACTORIES[event_cls]()
    bus.emit(event)
    # _spawn uses a daemon thread; give it a moment to fire
    time.sleep(0.05)
    assert notifier.send.call_count == 1, (
        f"Expected notifier.send called once for {event_cls.__name__}, got {notifier.send.call_count}"
    )
    msg = notifier.send.call_args[0][0]
    assert msg, f"send called with empty message for {event_cls.__name__}"
    sub.close()


# ---------------------------------------------------------------------------
# 3. Structlog line emitted for each event
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_cls", _ALL_ACQUIRE_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_handler_logs_structlog_line(event_cls: type, caplog: pytest.LogCaptureFixture) -> None:
    """Each handler emits a structlog line at INFO level (acquire.notify.<event>)."""
    caplog.set_level("INFO")
    bus, sub, notifier = _make_bus_and_sub(enabled=False)
    event = EVENT_SAMPLE_FACTORIES[event_cls]()
    bus.emit(event)

    expected_acquire_event = _camel_to_snake(event_cls.__name__)
    assert f"'acquire_event': '{expected_acquire_event}'" in caplog.text, (
        f"Expected structlog line with acquire_event='{expected_acquire_event}' not found in logs."
    )
    sub.close()


# ---------------------------------------------------------------------------
# 4. Fail-soft: notifier error does not propagate
# ---------------------------------------------------------------------------


def test_fail_soft_notifier_error_does_not_propagate() -> None:
    """A raising notifier must not propagate out of the subscriber."""
    bus = EventBus()
    notifier = MagicMock()
    notifier.send.side_effect = RuntimeError("telegram down")
    sub = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=True)
    event = EVENT_SAMPLE_FACTORIES[SeriesFollowed]()
    # Must not raise
    bus.emit(event)
    time.sleep(0.05)  # let daemon thread run
    sub.close()


# ---------------------------------------------------------------------------
# 5. close() unsubscribes all
# ---------------------------------------------------------------------------


def test_close_unsubscribes_all() -> None:
    """close() unregisters all 10 subscriptions."""
    bus = EventBus()
    sub = AcquisitionTelegramSubscriber(bus, enabled=False)
    assert len(sub._tokens) == 10
    sub.close()
    assert len(sub._tokens) == 0
    # Emit after close — notifier.send must not be called (no subscriptions)
    notifier = MagicMock()
    sub2 = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=True)
    sub2.close()
    event = EVENT_SAMPLE_FACTORIES[RatioMeasured]()
    bus.emit(event)
    time.sleep(0.05)
    notifier.send.assert_not_called()
