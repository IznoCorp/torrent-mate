# tests/subscribers/test_acquire_subscriber.py
"""Non-vacuous dispatch tests for AcquisitionTelegramSubscriber.

Tests verify:
1. enabled=False → notifier.send never called (muted mode).
2. enabled=True → notifier.send called exactly once per emit.
3. Each handler logs a structlog line at INFO level.
4. Fail-soft guards: _send handles False return / None notifier (synchronous),
   and _spawn worker-crashed WARNING (daemon thread, poll-based).
5. Regression: WantedEnqueued season=0 formats S00E05, not '?'.
6. close() unsubscribes all 11 subscriptions — emit post-close is a no-op.
"""

from __future__ import annotations

import re
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
    TrackerAuthFailed,
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
    TrackerAuthFailed,
]


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase event name to snake_case handler name."""
    s = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return s


def _wait_for(condition, timeout: float = 2.0) -> None:
    """Poll until *condition()* returns truthy or *timeout* expires.

    Replaces blind ``time.sleep(0.05)`` daemon-join waits with a
    deterministic poll that is immune to xdist/coverage-induced
    scheduling jitter.
    """
    import time

    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError(f"Condition not met within {timeout}s")
        time.sleep(0.01)


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
    # _spawn uses a daemon thread; poll until it fires
    _wait_for(lambda: notifier.send.call_count >= 1)
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
    """Each handler emits a structlog line at INFO level.

    Keyed as ``acquire.notify.event`` with an ``acquire_event`` discriminator field.
    """
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
# 4. Fail-soft: _send guards (synchronous — no daemon thread)
# ---------------------------------------------------------------------------


def test_fail_soft_notifier_send_returns_false_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When notifier.send returns False, _send logs send_failed (no raise).

    MUTATION-PROOF: deleting the ``if not … send(…)`` guard in _send
    suppresses the WARNING → this test fails.
    """
    caplog.set_level("WARNING")
    bus = EventBus()
    notifier = MagicMock()
    notifier.send.return_value = False
    sub = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=True)
    sub._send("test message", "test_event")
    assert "acquire_telegram_subscriber_send_failed" in caplog.text


def test_fail_soft_no_notifier_logs_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When notifier is None, _send logs no_notifier (no raise).

    MUTATION-PROOF: deleting the ``if self._notifier is None`` guard in
    _send causes an AttributeError on ``None.send()`` → this test fails
    (either via the missing WARNING or via the unhandled AttributeError).
    """
    caplog.set_level("WARNING")
    bus = EventBus()
    sub = AcquisitionTelegramSubscriber(bus, notifier=None, enabled=True)
    sub._send("test message", "test_event")
    assert "acquire_telegram_subscriber_no_notifier" in caplog.text


def test_fail_soft_worker_crashed_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """_spawn with a raising target logs worker_crashed (no raise).

    MUTATION-PROOF: deleting the try/except in _spawn's _runner
    suppresses the WARNING → this test fails.
    """
    caplog.set_level("WARNING")
    bus = EventBus()
    sub = AcquisitionTelegramSubscriber(bus, notifier=MagicMock(), enabled=True)

    def _raising_target() -> None:
        raise RuntimeError("boom")

    sub._spawn(_raising_target)
    _wait_for(lambda: "acquire_telegram_subscriber_worker_crashed" in caplog.text)
    assert "acquire_telegram_subscriber_worker_crashed" in caplog.text


# ---------------------------------------------------------------------------
# 4b. Regression: WantedEnqueued season=0/episode=0 must format correctly
# ---------------------------------------------------------------------------


def test_wanted_enqueued_specials_format_s00e05() -> None:
    """Season 0 / episode 5 (Plex Specials) renders S00E05, not '?'."""
    bus, sub, notifier = _make_bus_and_sub(enabled=True)
    from personalscraper.core.identity import MediaRef

    ref = MediaRef(tvdb_id=81189)
    event = WantedEnqueued(media_ref=ref, kind="episode", season=0, episode=5)
    bus.emit(event)
    _wait_for(lambda: notifier.send.call_count >= 1)
    msg = notifier.send.call_args[0][0]
    assert "S00E05" in msg, f"Expected S00E05 in message, got: {msg}"
    assert "?" not in msg, f"Expected no '?' in message, got: {msg}"
    sub.close()


def test_wanted_enqueued_movie_no_season_placeholder() -> None:
    """Movie kind does not include season/episode placeholder in message."""
    bus, sub, notifier = _make_bus_and_sub(enabled=True)
    from personalscraper.core.identity import MediaRef

    ref = MediaRef(tvdb_id=81189)
    event = WantedEnqueued(media_ref=ref, kind="movie", season=None, episode=None)
    bus.emit(event)
    _wait_for(lambda: notifier.send.call_count >= 1)
    msg = notifier.send.call_args[0][0]
    assert "Wanted movie" in msg


# ---------------------------------------------------------------------------
# 5. close() unsubscribes all
# ---------------------------------------------------------------------------


def test_close_unsubscribes_all() -> None:
    """close() unregisters all 11 subscriptions."""
    bus = EventBus()
    sub = AcquisitionTelegramSubscriber(bus, enabled=False)
    assert len(sub._tokens) == 11
    sub.close()
    assert len(sub._tokens) == 0
    # Emit after close — notifier.send must not be called (no subscriptions)
    notifier = MagicMock()
    sub2 = AcquisitionTelegramSubscriber(bus, notifier=notifier, enabled=True)
    sub2.close()
    event = EVENT_SAMPLE_FACTORIES[RatioMeasured]()
    bus.emit(event)
    # close() synchronously unsubscribes — emit post-close is a no-op,
    # no daemon thread is spawned, so notifier.send is never called.
    notifier.send.assert_not_called()
