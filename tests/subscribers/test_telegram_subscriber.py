"""Tests for :class:`TelegramSubscriber` — Sub-phase 3.6.

Covers subscription cardinality, payload composition for both events, the
fast-bus-thread contract (< 50 ms wall-clock even if the network is slow),
and clean unsubscribe on ``close()``.

A dedicated cassette test exercises the full notifier-transport stack via
the ``responses`` library — Phase 5.6 falls back to this fixture when live
``.env`` credentials are absent.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from personalscraper.api.notify.telegram import TelegramNotifier
from personalscraper.api.transport._http import HttpTransport
from personalscraper.core.event_bus import EventBus
from personalscraper.models import PipelineReport, StepReport
from personalscraper.pipeline_events import PipelineEnded, StepErrored
from personalscraper.subscribers.telegram import TelegramSubscriber

UTC = timezone.utc


def _make_pipeline_report() -> PipelineReport:
    """Build a representative end-of-pipeline report for the HTML send."""
    started = datetime(2026, 5, 12, 10, 0, 0, tzinfo=UTC)
    return PipelineReport(
        started_at=started,
        finished_at=started + timedelta(minutes=2, seconds=15),
        steps={"scrape": StepReport(name="scrape", success_count=4, skip_count=1, error_count=2)},
    )


class _FakeNotifier:
    """Stand-in for :class:`TelegramNotifier` that records every send."""

    def __init__(self, *, succeed: bool = True, delay: float = 0.0) -> None:
        self.calls: list[tuple[str, str]] = []
        self._succeed = succeed
        self._delay = delay

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        if self._delay:
            time.sleep(self._delay)
        self.calls.append((message, parse_mode))
        return self._succeed


def _wait_for_calls(notifier: _FakeNotifier, expected: int, timeout: float = 1.0) -> None:
    """Poll until ``len(notifier.calls) >= expected`` or ``timeout`` elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(notifier.calls) >= expected:
            return
        time.sleep(0.005)
    raise AssertionError(f"expected {expected} send call(s), got {len(notifier.calls)} after {timeout}s")


def test_telegram_subscriber_subscribes_to_pipeline_ended_and_step_errored() -> None:
    """``__init__`` registers exactly two subscription tokens."""
    bus = EventBus()
    sub = TelegramSubscriber(bus, _FakeNotifier())  # type: ignore[arg-type]
    assert len(sub._tokens) == 2  # noqa: SLF001


def test_telegram_subscriber_sends_html_on_pipeline_ended() -> None:
    """``PipelineEnded`` triggers exactly one ``send`` call with HTML parse_mode."""
    bus = EventBus()
    notifier = _FakeNotifier()
    TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    report = _make_pipeline_report()
    bus.emit(PipelineEnded(report=report))
    _wait_for_calls(notifier, 1)
    assert len(notifier.calls) == 1
    body, parse_mode = notifier.calls[0]
    assert parse_mode == "HTML"
    assert body == report.to_html()


def test_telegram_subscriber_alerts_on_step_errored() -> None:
    """``StepErrored`` triggers exactly one alert mentioning step, class, and message."""
    bus = EventBus()
    notifier = _FakeNotifier()
    TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    bus.emit(StepErrored(step="scrape", error_class="ValueError", error_message="boom"))
    _wait_for_calls(notifier, 1)
    body, parse_mode = notifier.calls[0]
    assert parse_mode == "HTML"
    assert "scrape" in body
    assert "ValueError" in body
    assert "boom" in body


def test_telegram_subscriber_close_unsubscribes() -> None:
    """After ``close()``, further emits never reach the notifier."""
    bus = EventBus()
    notifier = _FakeNotifier()
    sub = TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    sub.close()
    bus.emit(PipelineEnded(report=_make_pipeline_report()))
    bus.emit(StepErrored(step="scrape", error_class="X", error_message="y"))
    # Give the scheduler a chance — no spawn should have happened.
    time.sleep(0.05)
    assert notifier.calls == []
    assert sub._tokens == []  # noqa: SLF001


def test_telegram_subscriber_returns_synchronously_under_threshold() -> None:
    """Bus dispatch must return in < 50 ms even with a 2-second-slow Telegram."""
    bus = EventBus()
    notifier = _FakeNotifier(delay=2.0)
    TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    t0 = time.monotonic()
    bus.emit(PipelineEnded(report=_make_pipeline_report()))
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    assert elapsed_ms < 50.0, (
        f"bus dispatch took {elapsed_ms:.1f}ms — TelegramSubscriber must offload HTTP I/O off-thread"
    )


def test_telegram_subscriber_cassette() -> None:
    """End-to-end cassette: real transport against responses-mocked HTTP endpoints."""
    responses = pytest.importorskip("responses")
    bot_token = "123:fake-token"
    chat_id = "@cassette-chat"
    transport = HttpTransport(TelegramNotifier.policy(bot_token))
    notifier = TelegramNotifier(transport, chat_id)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    with responses.RequestsMock() as rmock:
        rmock.add(responses.POST, url, json={"ok": True}, status=200)
        rmock.add(responses.POST, url, json={"ok": True}, status=200)

        bus = EventBus()
        TelegramSubscriber(bus, notifier)

        # (a) PipelineEnded with errors → HTML summary
        bus.emit(PipelineEnded(report=_make_pipeline_report()))
        # (b) StepErrored → alert
        bus.emit(StepErrored(step="scrape", error_class="ValueError", error_message="boom"))

        # Wait for both daemon threads to land their POSTs.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and len(rmock.calls) < 2:
            time.sleep(0.01)

        assert len(rmock.calls) == 2
        bodies = [call.request.body for call in rmock.calls]
        joined = " ".join(b.decode() if isinstance(b, bytes) else (b or "") for b in bodies)
        assert "scrape" in joined
        assert "ValueError" in joined
        assert "boom" in joined
