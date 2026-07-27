"""Tests for enforce progress events — migrated to EventBus + ``ItemProgressed``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.core.event_bus import EventBus
from personalscraper.enforce.run import run_enforce
from personalscraper.pipeline_events import ItemProgressed
from tests.fixtures.event_bus import CollectingSubscriber


def _config() -> MagicMock:
    config = MagicMock()
    config.paths.staging_dir = Path("/tmp/staging")
    return config


class TestEnforceProgress:
    """Verify run_enforce emits per-item ``ItemProgressed`` events on the bus."""

    @patch("personalscraper.enforce.run.check_coherence", return_value=[])
    @patch("personalscraper.enforce.run.validate_structure", return_value=[])
    @patch("personalscraper.enforce.run.sanitize_files", return_value=[])
    def test_accepts_event_bus(self, _san, _val, _coh) -> None:
        """run_enforce accepts ``event_bus`` without error."""
        report = run_enforce(MagicMock(), _config(), dry_run=True, event_bus=EventBus())
        assert report.name == "enforce"

    def test_emits_events_per_sanitize_result(self) -> None:
        """Each sanitized item emits a terminal ``fixed`` event from run_enforce.

        ``started`` is emitted by ``sanitize_files`` itself now (F8 real
        lifecycle); with the sub-component mocked here only the terminal event is
        observed. The started-before-work contract is pinned in
        tests/event_bus/test_real_started_lifecycle.py.
        """
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        fake_result = MagicMock()
        fake_result.old_name = "Bad.Name.2024"
        fake_result.new_name = "Bad Name (2024)"
        fake_result.action = "renamed"

        with patch("personalscraper.enforce.run.sanitize_files", return_value=[fake_result]):
            with patch("personalscraper.enforce.run.validate_structure", return_value=[]):
                with patch("personalscraper.enforce.run.check_coherence", return_value=[]):
                    run_enforce(MagicMock(), _config(), dry_run=True, event_bus=bus)

        fixed = [e for e in collector.received if e.status == "fixed"]
        assert len(fixed) >= 1
        assert fixed[0].step == "enforce"

    def test_emits_events_for_structure_results(self) -> None:
        """A repaired structure result emits a terminal ``fixed`` event.

        ``started`` moved into ``validate_structure`` (F8); a mocked
        sub-component therefore produces only run_enforce's terminal event.
        """
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        fake_structure = MagicMock()
        fake_structure.path = MagicMock()
        fake_structure.path.name = "Inception (2010)"
        fake_structure.action = "repaired"
        fake_structure.fixes = ["added missing NFO"]
        fake_structure.warnings = []

        with patch("personalscraper.enforce.run.sanitize_files", return_value=[]):
            with patch("personalscraper.enforce.run.validate_structure", return_value=[fake_structure]):
                with patch("personalscraper.enforce.run.check_coherence", return_value=[]):
                    run_enforce(MagicMock(), _config(), dry_run=True, event_bus=bus)

        structure_events = [e for e in collector.received if e.item == "Inception (2010)"]
        assert [e.status for e in structure_events] == ["fixed"]

    def test_sanitize_skip_emits_skipped(self) -> None:
        """A sanitize_result with action='skipped' emits a skipped event (no fixed)."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        skipped_result = MagicMock()
        skipped_result.old_name = "Already.OK.2024"
        skipped_result.new_name = None
        skipped_result.action = "skipped"

        with (
            patch("personalscraper.enforce.run.sanitize_files", return_value=[skipped_result]),
            patch("personalscraper.enforce.run.validate_structure", return_value=[]),
            patch("personalscraper.enforce.run.check_coherence", return_value=[]),
        ):
            run_enforce(MagicMock(), _config(), dry_run=True, event_bus=bus)

        skipped = [e for e in collector.received if e.status == "skipped"]
        fixed = [e for e in collector.received if e.status == "fixed"]
        assert len(skipped) >= 1
        assert len(fixed) == 0

    def test_structure_unrepaired_emits_skipped(self) -> None:
        """A structure_result with action != 'repaired' emits skipped (not fixed)."""
        bus = EventBus()
        collector = CollectingSubscriber(bus, ItemProgressed)

        struct = MagicMock()
        struct.path = MagicMock()
        struct.path.name = "Broken (2010)"
        struct.action = "blocked"
        struct.fixes = []
        struct.warnings = ["unrecoverable structure"]

        with (
            patch("personalscraper.enforce.run.sanitize_files", return_value=[]),
            patch("personalscraper.enforce.run.validate_structure", return_value=[struct]),
            patch("personalscraper.enforce.run.check_coherence", return_value=[]),
        ):
            run_enforce(MagicMock(), _config(), dry_run=True, event_bus=bus)

        events_for_item = [e for e in collector.received if e.item == "Broken (2010)"]
        statuses = [e.status for e in events_for_item]
        # ``started`` now originates in ``validate_structure`` (mocked here);
        # run_enforce emits the terminal ``skipped`` for a non-repaired result.
        assert "skipped" in statuses
        assert "fixed" not in statuses
