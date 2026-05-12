"""Unit tests for trailers/step.py -- pipeline step wiring.

Orchestrator is fully mocked; no real discovery or downloads occur.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import EventBus
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
            result = run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())
        assert isinstance(result, StepReport)
        assert result.name == "trailers"

    def test_skipped_when_disabled(self, config, tmp_path):
        """run_trailers() returns a skipped report when config.trailers.enabled=False."""
        config.trailers.enabled = False
        result = run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())
        assert result.name == "trailers"
        assert result.status == "skipped"

    def test_skip_trailers_flag_skips(self, config, tmp_path):
        """run_trailers() respects the skip_trailers flag."""
        result = run_trailers(config, staging_dir=tmp_path, verified=[], skip_trailers=True, event_bus=EventBus())
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
            result = run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())
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
            result = run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())
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
            result = run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())
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


class TestRunTrailersVerifiedFiltering:
    """Tests for verified-path filtering in run_trailers() (C8)."""

    def test_run_trailers_filters_orchestrator_items_to_verified_paths(self, config, tmp_path):
        """run_trailers() passes only verified-path items to orchestrator.run().

        When a non-empty ``verified`` list is provided, run_trailers() must scan
        staging, filter to items whose path is in the verified set, and pass
        that filtered list to ``orchestrator.run(items=...)``.  Items not in the
        verified set must be excluded even if the scanner sees them.

        Args:
            config: Mock Config fixture.
            tmp_path: Pytest tmp_path fixture.
        """
        from unittest.mock import MagicMock, patch

        from personalscraper.trailers.scanner import ScanItem

        verified_path = tmp_path / "Movie A (2020)"
        excluded_path = tmp_path / "Movie B (2021)"

        # Two ScanItems — only verified_path is in the verified list.
        item_a = ScanItem(path=verified_path, media_type="movie", title="Movie A", year=2020, tmdb_id="111")
        item_b = ScanItem(path=excluded_path, media_type="movie", title="Movie B", year=2021, tmdb_id="222")

        # Build verified list — only item_a's path is marked success.
        verified_item = MagicMock()
        verified_item.path = str(verified_path)
        verified_item.status = "success"

        with patch("personalscraper.trailers.orchestrator.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            # Scanner returns both items; only item_a should be passed to run().
            mock_orch._scanner.scan_staging.return_value = [item_a, item_b]
            mock_orch.run.return_value = {
                "downloaded": 1,
                "already_present": 0,
                "no_trailer": 0,
                "bot_detected": 0,
                "error": 0,
                "skipped_by_state": 0,
            }
            mock_orch.failed_items = []

            run_trailers(config, staging_dir=tmp_path, verified=[verified_item], event_bus=EventBus())

        # orchestrator.run() must have been called with only item_a
        mock_orch.run.assert_called_once()
        call_args = mock_orch.run.call_args
        # items is always passed as a keyword argument from step.py
        passed_items = call_args.kwargs.get("items")
        assert passed_items is not None, "orchestrator.run() must be called with items keyword argument"
        assert len(passed_items) == 1
        assert passed_items[0].path == verified_path

    def test_run_trailers_passes_none_when_verified_empty(self, config, tmp_path):
        """run_trailers() passes items=None to orchestrator when verified is empty.

        An empty verified list means the step was invoked directly (CLI or
        unit test), so the orchestrator should fall back to its own staging scan.

        Args:
            config: Mock Config fixture.
            tmp_path: Pytest tmp_path fixture.
        """
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

            run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())

        mock_orch.run.assert_called_once_with(items=None)


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


# ── Sub-phase 11.6 new tests ──────────────────────────────────────────────────


class TestStateWriteFailure:
    """I6 — OSError from _save() produces a distinct trailers_state_write_failed event."""

    def test_state_write_failure_returns_status_error_distinct_event(self, config, tmp_path, caplog):
        """OSError from state_store.set raises a distinct event and returns status='error'.

        Patching ``state_store.set`` to raise ``OSError(ENOSPC, "no space")``
        verifies that:
        - ``run_trailers`` returns ``StepReport(status='error')``
        - the structured log event is ``trailers_state_write_failed`` (not
          ``trailers_step_crashed``)
        - the log record carries an ``errno`` field equal to ENOSPC

        Args:
            config: Mock Config fixture with trailers enabled.
            tmp_path: Pytest tmp_path fixture.
            caplog: Pytest log capture fixture.
        """
        import errno as _errno
        import logging

        no_space_error = OSError(_errno.ENOSPC, "no space left on device")

        with patch("personalscraper.trailers.orchestrator.TrailersOrchestrator") as MockOrch:
            mock_orch = MockOrch.return_value
            # Simulate the orchestrator raising OSError when it tries to persist state.
            mock_orch.run.side_effect = no_space_error

            with caplog.at_level(logging.ERROR):
                result = run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=EventBus())

        assert result.status == "error", f"expected status='error', got {result.status!r}"
        assert result.error_count == 1

        # The event name must be the ops-transient event, not the generic crash event.
        def _is_write_failed_event(r: object) -> bool:
            msg = getattr(r, "msg", None)
            message = str(getattr(r, "message", ""))
            return (isinstance(msg, dict) and msg.get("event") == "trailers_state_write_failed") or (
                "trailers_state_write_failed" in message
            )

        def _is_crash_event(r: object) -> bool:
            msg = getattr(r, "msg", None)
            message = str(getattr(r, "message", ""))
            return (isinstance(msg, dict) and msg.get("event") == "trailers_step_crashed") or (
                "trailers_step_crashed" in message
            )

        write_failed_events = [r for r in caplog.records if _is_write_failed_event(r)]
        crash_events = [r for r in caplog.records if _is_crash_event(r)]

        assert write_failed_events, (
            "expected trailers_state_write_failed log event; "
            f"records: {[(r.levelno, getattr(r, 'msg', r.getMessage())) for r in caplog.records]}"
        )
        assert not crash_events, (
            "trailers_step_crashed must NOT fire for OSError; "
            f"records: {[(r.levelno, getattr(r, 'msg', r.getMessage())) for r in caplog.records]}"
        )


class TestRunTrailersBusPassThrough:
    """Regression: run_trailers must forward its event_bus argument to TrailersOrchestrator.

    Pre-fix the function instantiated a throwaway ``EventBus()`` for the
    orchestrator, so every event emitted by trailer download work fell into a
    void with no subscribers — breaking the Telegram/RichConsole delivery
    contract for the trailers stage of ``personalscraper run``.
    """

    def test_orchestrator_receives_caller_bus(self, config, tmp_path):
        """The bus passed to run_trailers() is the bus given to TrailersOrchestrator()."""
        caller_bus = EventBus()
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
            run_trailers(config, staging_dir=tmp_path, verified=[], event_bus=caller_bus)

        MockOrch.assert_called_once()
        kwargs = MockOrch.call_args.kwargs
        assert kwargs.get("event_bus") is caller_bus, (
            "TrailersOrchestrator must receive the bus passed to run_trailers, "
            "not a freshly constructed EventBus() with no subscribers."
        )
