# tests/subscribers/test_acquire_download_events.py
"""Download-event tests for AcquisitionTelegramSubscriber (seed-caps 4.1).

Tests verify:
1. _on_download_completed formats the French message (« Téléchargement
   terminé » + title) and dispatches under the name "download_completed".
2. D8 anti-spam guard: the subscriber has NO handler for DownloadStarted
   or DownloadProgressed — Telegram only ever gets DownloadCompleted.
3. The DownloadCompleted subscription is actually registered in __init__
   (asserted against a mock bus's subscribe calls).
4. Fallback provider "unknown" (reconcile fallback) renders sensibly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import personalscraper.events  # noqa: F401 — eager-import acquire events
from personalscraper.acquire.events import DownloadCompleted
from personalscraper.core.event_bus import EventBus
from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber


def _wait_for(condition, timeout: float = 2.0) -> None:
    """Poll until *condition()* returns truthy or *timeout* expires.

    Deterministic replacement for blind sleeps around the subscriber's
    fire-and-forget daemon threads (immune to xdist/coverage jitter).
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


def _make_event(**overrides: object) -> DownloadCompleted:
    """Build a realistic DownloadCompleted, allowing per-test field overrides."""
    fields: dict[str, object] = {
        "info_hash": "f" * 40,
        "title": "Breaking Bad S05E01",
        "provider": "c411",
        "kind": "episode",
    }
    fields.update(overrides)
    return DownloadCompleted(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. Message formatting + dispatch name
# ---------------------------------------------------------------------------


def test_handler_formats_french_message() -> None:
    """The notifier receives « Téléchargement terminé » + title + provider + kind."""
    bus, sub, notifier = _make_bus_and_sub(enabled=True)
    bus.emit(_make_event())
    _wait_for(lambda: notifier.send.call_count >= 1)
    msg = notifier.send.call_args[0][0]
    assert "Téléchargement terminé" in msg, f"Expected French wording in message, got: {msg}"
    assert "Breaking Bad S05E01" in msg, f"Expected title in message, got: {msg}"
    assert "c411" in msg, f"Expected provider in message, got: {msg}"
    assert "episode" in msg, f"Expected kind in message, got: {msg}"
    sub.close()


def test_handler_dispatches_with_snake_name(caplog: pytest.LogCaptureFixture) -> None:
    """The handler dispatches under the structlog name "download_completed"."""
    caplog.set_level("INFO")
    bus, sub, _notifier = _make_bus_and_sub(enabled=False)
    bus.emit(_make_event())
    assert "'acquire_event': 'download_completed'" in caplog.text, (
        "Expected structlog line with acquire_event='download_completed' not found in logs."
    )
    sub.close()


def test_handler_unknown_provider_stays_sensible() -> None:
    """Reconcile fallback provider "unknown" renders without crashing."""
    bus, sub, notifier = _make_bus_and_sub(enabled=True)
    bus.emit(_make_event(provider="unknown"))
    _wait_for(lambda: notifier.send.call_count >= 1)
    msg = notifier.send.call_args[0][0]
    assert "Téléchargement terminé" in msg, f"Expected French wording in message, got: {msg}"
    assert "unknown" in msg, f"Expected fallback provider in message, got: {msg}"
    sub.close()


# ---------------------------------------------------------------------------
# 2. D8 anti-spam guard — no Started/Progressed handlers
# ---------------------------------------------------------------------------


def test_no_started_or_progressed_handlers() -> None:
    """D8: Telegram gets DownloadCompleted ONLY — no Started/Progressed handlers exist."""
    bus, sub, _notifier = _make_bus_and_sub(enabled=False)
    assert not hasattr(sub, "_on_download_started"), "D8 violation: _on_download_started must not exist (anti-spam)"
    assert not hasattr(sub, "_on_download_progressed"), (
        "D8 violation: _on_download_progressed must not exist (anti-spam)"
    )
    sub.close()


# ---------------------------------------------------------------------------
# 3. Subscription registration
# ---------------------------------------------------------------------------


def test_download_completed_subscription_registered() -> None:
    """__init__ subscribes DownloadCompleted (and never Started/Progressed)."""
    from personalscraper.acquire.events import DownloadProgressed, DownloadStarted

    bus = MagicMock(spec=EventBus)
    AcquisitionTelegramSubscriber(bus, notifier=None, enabled=False)
    subscribed_types = [call.args[0] for call in bus.subscribe.call_args_list]
    assert DownloadCompleted in subscribed_types, (
        f"DownloadCompleted not subscribed; got: {[t.__name__ for t in subscribed_types]}"
    )
    assert DownloadStarted not in subscribed_types, "D8 violation: DownloadStarted subscribed"
    assert DownloadProgressed not in subscribed_types, "D8 violation: DownloadProgressed subscribed"
