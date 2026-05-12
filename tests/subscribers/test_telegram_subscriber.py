"""Tests for :class:`TelegramSubscriber` — Sub-phase 3.6 + 4.1 + 4.2b.

Covers subscription cardinality, payload composition for every subscribed
event, the fast-bus-thread contract (< 50 ms wall-clock even if the network
is slow), and clean unsubscribe on ``close()``.

A dedicated cassette test exercises the full notifier-transport stack via
the ``responses`` library — Phase 5.6 §14 falls back to this fixture when
live ``.env`` credentials are absent. Sub-phase 4.1 added
``CircuitBreakerOpened``; Sub-phase 4.2b adds ``DiskFullWarning`` so the
cassette now exercises all four production events.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from personalscraper.api.notify.telegram import TelegramNotifier
from personalscraper.api.transport._http import HttpTransport
from personalscraper.core.circuit import CircuitBreakerOpened
from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.events import DiskFullWarning
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


def test_telegram_subscriber_has_four_subscriptions_after_phase4() -> None:
    """``__init__`` registers exactly four subscription tokens after Sub-phase 4.2b.

    Phase 3.6 shipped two (``PipelineEnded``, ``StepErrored``); Phase 4.1 added
    ``CircuitBreakerOpened``; Phase 4.2b adds ``DiskFullWarning``. This is the
    Phase-4 gate-time invariant — any additional subscription must update the
    expected count here.
    """
    bus = EventBus()
    sub = TelegramSubscriber(bus, _FakeNotifier())  # type: ignore[arg-type]
    assert len(sub._tokens) == 4  # noqa: SLF001


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


def test_telegram_subscriber_alerts_on_circuit_opened() -> None:
    """``CircuitBreakerOpened`` triggers exactly one alert with breaker + failure data."""
    bus = EventBus()
    notifier = _FakeNotifier()
    TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    bus.emit(
        CircuitBreakerOpened(
            breaker="tmdb",
            failure_count=5,
            last_error_class="TimeoutError",
            last_error_message="connect timed out after 30s",
        ),
    )
    _wait_for_calls(notifier, 1)
    body, parse_mode = notifier.calls[0]
    assert parse_mode == "HTML"
    assert "tmdb" in body
    assert "5" in body
    assert "TimeoutError" in body


def test_telegram_subscriber_alerts_on_disk_full_warning() -> None:
    """``DiskFullWarning`` triggers exactly one alert with the disk path + GB-scale figures."""
    bus = EventBus()
    notifier = _FakeNotifier()
    TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    bus.emit(
        DiskFullWarning(
            disk_path=Path("/Volumes/Disk1"),
            free_bytes=1_000_000_000,
            threshold_bytes=10_000_000_000,
        ),
    )
    _wait_for_calls(notifier, 1)
    body, parse_mode = notifier.calls[0]
    assert parse_mode == "HTML"
    assert "/Volumes/Disk1" in body
    assert "1GB" in body
    assert "10GB" in body


def test_telegram_subscriber_close_unsubscribes() -> None:
    """After ``close()``, further emits never reach the notifier."""
    bus = EventBus()
    notifier = _FakeNotifier()
    sub = TelegramSubscriber(bus, notifier)  # type: ignore[arg-type]
    sub.close()
    bus.emit(PipelineEnded(report=_make_pipeline_report()))
    bus.emit(StepErrored(step="scrape", error_class="X", error_message="y"))
    bus.emit(
        CircuitBreakerOpened(breaker="tmdb", failure_count=1, last_error_class="X", last_error_message="y"),
    )
    bus.emit(
        DiskFullWarning(disk_path=Path("/Volumes/Disk1"), free_bytes=0, threshold_bytes=0),
    )
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
    """End-to-end cassette: real transport against responses-mocked HTTP endpoints.

    Phase 4.1 added ``CircuitBreakerOpened`` to the cassette; Phase 4.2b adds
    ``DiskFullWarning``. The cassette now exercises all four production
    events the subscriber listens to, so the Phase 5.6 §14 fallback
    (``pytest tests/subscribers/test_telegram_subscriber.py -v``) covers
    the full subscription surface.
    """
    responses = pytest.importorskip("responses")
    bot_token = "123:fake-token"
    chat_id = "@cassette-chat"
    transport = HttpTransport(TelegramNotifier.policy(bot_token))
    notifier = TelegramNotifier(transport, chat_id)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    with responses.RequestsMock() as rmock:
        for _ in range(4):
            rmock.add(responses.POST, url, json={"ok": True}, status=200)

        bus = EventBus()
        TelegramSubscriber(bus, notifier)

        # (a) PipelineEnded with errors → HTML summary
        bus.emit(PipelineEnded(report=_make_pipeline_report()))
        # (b) StepErrored → alert
        bus.emit(StepErrored(step="scrape", error_class="ValueError", error_message="boom"))
        # (c) CircuitBreakerOpened → circuit-trip alert (Sub-phase 4.1)
        bus.emit(
            CircuitBreakerOpened(
                breaker="tmdb",
                failure_count=5,
                last_error_class="TimeoutError",
                last_error_message="connect timed out after 30s",
            ),
        )
        # (d) DiskFullWarning → disk-full alert (Sub-phase 4.2b)
        bus.emit(
            DiskFullWarning(
                disk_path=Path("/Volumes/Disk1"),
                free_bytes=1_000_000_000,
                threshold_bytes=10_000_000_000,
            ),
        )

        # Wait for all four daemon threads to land their POSTs. Telegram's
        # policy rate-limits at 1 req/s, so the four serialized sends need
        # ≥ 4 seconds plus scheduling slack — use a 8 s ceiling.
        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline and len(rmock.calls) < 4:
            time.sleep(0.01)

        assert len(rmock.calls) == 4
        bodies = [call.request.body for call in rmock.calls]
        joined = " ".join(b.decode() if isinstance(b, bytes) else (b or "") for b in bodies)
        assert "scrape" in joined
        assert "ValueError" in joined
        assert "boom" in joined
        # Circuit-trip alert content
        assert "tmdb" in joined
        assert "TimeoutError" in joined
        # Disk-full alert content (Sub-phase 4.2b)
        assert "Disk1" in joined
        assert "10GB" in joined
