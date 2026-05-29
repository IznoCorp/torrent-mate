"""Tests for trailers progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.event_bus import EventBus
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.trailers.step import run_trailers
from tests.fixtures.event_bus import CollectingSubscriber


def _mk_registry():
    """Return a MagicMock standing in for a ProviderRegistry."""
    return MagicMock(spec=ProviderRegistry)


class TestTrailersProgress:
    """Verify run_trailers emits ``ItemProgressed`` events on the bus."""

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_accepts_event_bus(self, _orch) -> None:
        """run_trailers accepts ``event_bus`` without error."""
        _orch.return_value.run.return_value = {}
        _orch.return_value.failed_items = []
        _orch.return_value.item_results = []
        config = MagicMock()
        config.trailers.enabled = True
        report = run_trailers(
            config,
            staging_dir=Path("/tmp/staging"),
            verified=[],
            event_bus=EventBus(),
            registry=_mk_registry(),
        )
        assert report.name == "trailers"

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_emits_per_item_from_orchestrator(self, _orch) -> None:
        """Per-item results from orchestrator are emitted as progress events."""
        _orch.return_value.run.return_value = {
            "downloaded": 1,
            "already_present": 0,
            "skipped_by_state": 0,
            "error": 0,
            "bot_detected": 0,
        }
        _orch.return_value.failed_items = []
        _orch.return_value.item_results = [("/tmp/Inception (2010)", "downloaded", "downloaded")]

        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        config = MagicMock()
        config.trailers.enabled = True

        run_trailers(
            config,
            staging_dir=Path("/tmp/staging"),
            verified=[MagicMock()],
            event_bus=bus,
            registry=_mk_registry(),
        )

        downloaded = [e for e in collector.received if e.status == "downloaded"]
        assert len(downloaded) >= 1
        assert "Inception" in downloaded[0].item

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_emits_bot_detected_and_error_statuses(self, _orch) -> None:
        """bot_detected and error per-item statuses surface in progress events."""
        _orch.return_value.run.return_value = {
            "downloaded": 0,
            "already_present": 0,
            "skipped_by_state": 0,
            "error": 1,
            "bot_detected": 1,
        }
        _orch.return_value.failed_items = [
            ("bad", "error", "ytdlp_failed"),
            ("blocked", "bot_detected", "captcha"),
        ]
        _orch.return_value.item_results = [
            ("/tmp/Bad (2010)", "error", "ytdlp_failed"),
            ("/tmp/Blocked (2011)", "bot_detected", "captcha"),
        ]

        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        config = MagicMock()
        config.trailers.enabled = True

        run_trailers(
            config,
            staging_dir=Path("/tmp/staging"),
            verified=[MagicMock()],
            event_bus=bus,
            registry=_mk_registry(),
        )

        statuses = [e.status for e in collector.received]
        assert "error" in statuses
        assert "bot_detected" in statuses

    def test_skip_flag_emits_skipped_event(self) -> None:
        """--skip-trailers (or config.trailers.enabled=False) emits a step-level skipped event."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        config = MagicMock()
        config.trailers.enabled = True

        run_trailers(
            config,
            staging_dir=Path("/tmp/staging"),
            verified=[],
            skip_trailers=True,
            event_bus=bus,
            registry=_mk_registry(),
        )

        skipped = [e for e in collector.received if e.status == "skipped"]
        assert len(skipped) == 1
        assert skipped[0].step == "trailers"
        assert skipped[0].details["reason"] == "skip_flag"

    @patch("personalscraper.trailers.orchestrator.TrailersOrchestrator")
    def test_orchestrator_crash_emits_failed_event(self, _orch) -> None:
        """A crashing orchestrator emits a step-level failed event before returning error."""
        _orch.return_value.run.side_effect = RuntimeError("yt-dlp blew up")
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)
        config = MagicMock()
        config.trailers.enabled = True

        report = run_trailers(
            config,
            staging_dir=Path("/tmp/staging"),
            verified=[],
            event_bus=bus,
            registry=_mk_registry(),
        )

        assert report.status == "error"
        failed = [e for e in collector.received if e.status == "failed"]
        assert len(failed) == 1
        assert failed[0].details["reason"] == "crashed"
