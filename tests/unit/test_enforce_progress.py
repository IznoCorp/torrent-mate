"""Tests for enforce progress events."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from personalscraper.enforce.run import run_enforce
from personalscraper.pipeline_observer import CollectorObserver


class TestEnforceProgress:
    """Verify run_enforce emits per-item progress events."""

    @patch("personalscraper.enforce.run.check_coherence", return_value=[])
    @patch("personalscraper.enforce.run.validate_structure", return_value=[])
    @patch("personalscraper.enforce.run.sanitize_files", return_value=[])
    def test_accepts_observers(self, _san, _val, _coh) -> None:
        """run_enforce accepts observers without error."""
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")

        report = run_enforce(settings, config, dry_run=True, observers=())
        assert report.name == "enforce"

    def test_emits_events_per_sanitize_result(self) -> None:
        """Each sanitized item emits started + fixed events."""
        collector = CollectorObserver()
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")

        fake_result = MagicMock()
        fake_result.old_name = "Bad.Name.2024"
        fake_result.new_name = "Bad Name (2024)"
        fake_result.action = "renamed"

        with patch("personalscraper.enforce.run.sanitize_files", return_value=[fake_result]):
            with patch("personalscraper.enforce.run.validate_structure", return_value=[]):
                with patch("personalscraper.enforce.run.check_coherence", return_value=[]):
                    run_enforce(settings, config, dry_run=True, observers=(collector,))

        started = [e for e in collector.progress if e.status == "started"]
        fixed = [e for e in collector.progress if e.status == "fixed"]
        assert len(started) >= 1, "expected at least 1 started event from sanitize"
        assert len(fixed) >= 1, "expected at least 1 fixed event from sanitize"
        assert started[0].step == "enforce"

    def test_emits_events_for_structure_results(self) -> None:
        """Structure results emit started + fixed events."""
        collector = CollectorObserver()
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")

        fake_structure = MagicMock()
        fake_structure.path = MagicMock()
        fake_structure.path.name = "Inception (2010)"
        fake_structure.action = "repaired"
        fake_structure.fixes = ["added missing NFO"]
        fake_structure.warnings = []

        with patch("personalscraper.enforce.run.sanitize_files", return_value=[]):
            with patch("personalscraper.enforce.run.validate_structure", return_value=[fake_structure]):
                with patch("personalscraper.enforce.run.check_coherence", return_value=[]):
                    run_enforce(settings, config, dry_run=True, observers=(collector,))

        structure_events = [e for e in collector.progress if e.item == "Inception (2010)"]
        assert len(structure_events) >= 2, "expected started + fixed events for structure item"
