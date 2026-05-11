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

    def test_sanitize_skip_emits_skipped(self) -> None:
        """A sanitize_result with action='skipped' emits a skipped event (no fixed)."""
        collector = CollectorObserver()
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")

        skipped_result = MagicMock()
        skipped_result.old_name = "Already.OK.2024"
        skipped_result.new_name = None
        skipped_result.action = "skipped"

        with (
            patch("personalscraper.enforce.run.sanitize_files", return_value=[skipped_result]),
            patch("personalscraper.enforce.run.validate_structure", return_value=[]),
            patch("personalscraper.enforce.run.check_coherence", return_value=[]),
        ):
            run_enforce(settings, config, dry_run=True, observers=(collector,))

        skipped = [e for e in collector.progress if e.status == "skipped"]
        fixed = [e for e in collector.progress if e.status == "fixed"]
        assert len(skipped) >= 1
        assert len(fixed) == 0

    def test_structure_unrepaired_emits_skipped(self) -> None:
        """A structure_result with action != 'repaired' emits skipped (not fixed)."""
        collector = CollectorObserver()
        settings = MagicMock()
        config = MagicMock()
        config.paths.staging_dir = Path("/tmp/staging")

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
            run_enforce(settings, config, dry_run=True, observers=(collector,))

        events_for_item = [e for e in collector.progress if e.item == "Broken (2010)"]
        statuses = [e.status for e in events_for_item]
        assert "started" in statuses
        assert "skipped" in statuses
        assert "fixed" not in statuses
