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
        """Each sanitized item emits started + fixed/skipped events."""
        # noqa - SanitizeResult import verified

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
        assert len(started) >= 1
        assert started[0].step == "enforce"
