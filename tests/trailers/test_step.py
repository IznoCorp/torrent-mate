"""Unit tests for trailers/step.py -- pipeline step wiring.

Orchestrator is fully mocked; no real discovery or downloads occur.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.models import PipelineReport, StepReport
from personalscraper.trailers.step import run_trailers


@pytest.fixture()
def config(tmp_path):
    """Minimal mock Config with trailers enabled."""
    cfg = MagicMock()
    cfg.trailers.enabled = True
    cfg.trailers.retry_after_days = [1, 7, 30]
    cfg.trailers.state_file = str(tmp_path / ".data/trailers_state.json")
    cfg.trailers.filters.min_file_size_bytes = 102400
    return cfg


class TestRunTrailers:
    """Tests for run_trailers() pipeline step."""

    def test_returns_step_report(self, config, tmp_path):
        """run_trailers() returns a StepReport instance."""
        with patch("personalscraper.trailers.orchestrator.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 0,
                "already_present": 0,
                "no_trailer": 0,
                "bot_detected": 0,
                "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert isinstance(result, StepReport)
        assert result.name == "trailers"

    def test_skipped_when_disabled(self, config, tmp_path):
        """run_trailers() returns a skipped report when config.trailers.enabled=False."""
        config.trailers.enabled = False
        result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.name == "trailers"
        assert result.status == "skipped"

    def test_skip_trailers_flag_skips(self, config, tmp_path):
        """run_trailers() respects the skip_trailers flag."""
        result = run_trailers(config, staging_dir=tmp_path, verified=[], skip_trailers=True)
        assert result.status == "skipped"

    def test_counts_in_step_report(self, config, tmp_path):
        """run_trailers() populates StepReport counts from orchestrator output."""
        with patch("personalscraper.trailers.orchestrator.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 3,
                "already_present": 5,
                "no_trailer": 1,
                "bot_detected": 0,
                "error": 0,
                "skipped_by_state": 2,
            }
            mock_orch.failed_items = []
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.success_count == 3
        assert result.skip_count == 5 + 2
        assert result.counts.get("downloaded") == 3

    def test_partial_status_on_failures(self, config, tmp_path):
        """run_trailers() returns status='partial' when some items failed."""
        with patch("personalscraper.trailers.orchestrator.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 2,
                "already_present": 1,
                "no_trailer": 0,
                "bot_detected": 1,
                "error": 1,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = [("movie:tmdb:1", "bot_detected", "sign in")]
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.status == "partial"

    def test_success_status_when_no_failures(self, config, tmp_path):
        """run_trailers() returns status='success' when no errors or bot detections."""
        with patch("personalscraper.trailers.orchestrator.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            mock_orch.run.return_value = {
                "downloaded": 5,
                "already_present": 0,
                "no_trailer": 0,
                "bot_detected": 0,
                "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []
            result = run_trailers(config, staging_dir=tmp_path, verified=[])
        assert result.status == "success"


class TestStepReportBackwardCompat:
    """Non-regression tests for StepReport extension backward compatibility."""

    def test_stepreport_without_new_fields(self):
        """StepReport construction without the new optional fields is still valid."""
        step = StepReport(name="ingest", success_count=3, skip_count=1)
        assert step.status is None
        assert step.counts == {}
        assert step.failed_items == []

    def test_to_html_renders_without_new_fields(self):
        """PipelineReport.to_html() works when StepReport has no status/counts/failed_items."""
        report = PipelineReport(started_at=datetime(2026, 4, 24, 0, 0, 0))
        report.add_step("ingest", StepReport(name="ingest", success_count=3))
        report.add_step("sort", StepReport(name="sort", success_count=5))
        report.finished_at = datetime(2026, 4, 24, 0, 2, 30)
        html = report.to_html()
        assert "Ingest" in html
        assert "3 OK" in html


class TestStepReportTelegramSummary:
    """Verify StepReport counts flow through to PipelineReport.to_html() for Telegram delivery.

    DESIGN section 11 promises a summary like "N trailers downloaded, M skipped, K failed".
    This test asserts the counts flow through to_html() so Telegram delivery works without
    touching notifier.py.
    """

    def test_step_report_renders_in_pipeline_html(self):
        """StepReport(name='trailers', counts={...}) renders via PipelineReport.to_html()."""
        step = StepReport(
            name="trailers",
            success_count=2,
            counts={"downloaded": 2, "skipped": 3, "error": 1},
        )
        report = PipelineReport(started_at=datetime(2026, 4, 24, 0, 0, 0))
        report.add_step("trailers", step)
        report.finished_at = datetime(2026, 4, 24, 0, 1, 0)
        html = report.to_html()
        # Trailers step name and at least one count number must appear in the HTML.
        assert "trailers" in html.lower()
        assert "2" in html  # downloaded
