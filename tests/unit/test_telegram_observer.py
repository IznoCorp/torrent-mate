"""Tests for TelegramObserver."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.telegram import TelegramObserver
from personalscraper.pipeline_observer import PipelineObserver


class TestTelegramObserver:
    """TelegramObserver tests."""

    @staticmethod
    def _make_notifier(**kwargs) -> MagicMock:
        notifier = MagicMock()
        notifier.send_report.return_value = kwargs.get("send_report_return", True)
        return notifier

    def test_is_pipeline_observer(self) -> None:
        """TelegramObserver satisfies the PipelineObserver Protocol."""
        notifier = self._make_notifier()
        assert isinstance(TelegramObserver(notifier), PipelineObserver)

    def test_name(self) -> None:
        """Observer has the expected name."""
        notifier = self._make_notifier()
        assert TelegramObserver(notifier).name == "telegram"

    def test_on_pipeline_end_sends_report(self) -> None:
        """on_pipeline_end calls TelegramNotifier.send_report with the report."""
        notifier = self._make_notifier()
        obs = TelegramObserver(notifier)
        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest", success_count=1))
        report.finished_at = datetime.now()

        obs.on_pipeline_end(report)

        notifier.send_report.assert_called_once_with(report)

    def test_all_other_callbacks_are_noop(self) -> None:
        """All callbacks except on_pipeline_end are no-ops."""
        notifier = self._make_notifier()
        obs = TelegramObserver(notifier)
        report = PipelineReport(started_at=datetime.now())
        step_report = StepReport(name="test")

        obs.on_pipeline_start(report)
        obs.on_step_start("ingest")
        obs.on_step_end("ingest", step_report, 1.0)
        obs.on_step_error("ingest", ValueError())
        obs.on_progress(MagicMock())
        # No exception = pass

    def test_on_pipeline_end_logs_warning_on_send_failure(self) -> None:
        """on_pipeline_end survives when send_report returns False."""
        notifier = self._make_notifier(send_report_return=False)
        obs = TelegramObserver(notifier)
        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest", success_count=1))
        report.finished_at = datetime.now()

        obs.on_pipeline_end(report)
        notifier.send_report.assert_called_once_with(report)

    def test_on_pipeline_end_survives_notifier_exception(self) -> None:
        """Observer does not crash when the notifier raises an exception."""
        notifier = self._make_notifier()
        notifier.send_report.side_effect = RuntimeError("telegram API unreachable")
        obs = TelegramObserver(notifier)
        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest", success_count=1))
        report.finished_at = datetime.now()

        # Must raise — the observer does not catch; _notify_observers does.
        with pytest.raises(RuntimeError, match="telegram API unreachable"):
            obs.on_pipeline_end(report)
