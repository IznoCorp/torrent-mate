"""Tests for TelegramObserver."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from personalscraper.models import PipelineReport, StepReport
from personalscraper.observers.telegram import TelegramObserver
from personalscraper.pipeline_observer import PipelineObserver


class TestTelegramObserver:
    """TelegramObserver tests."""

    def test_is_pipeline_observer(self) -> None:
        """TelegramObserver satisfies the PipelineObserver Protocol."""
        settings = MagicMock()
        settings.telegram_bot_token = "fake-token"
        settings.telegram_chat_id = "123"
        assert isinstance(TelegramObserver(settings), PipelineObserver)

    def test_name(self) -> None:
        """Observer has the expected name."""
        settings = MagicMock()
        assert TelegramObserver(settings).name == "telegram"

    def test_on_pipeline_end_sends_report(self) -> None:
        """on_pipeline_end calls TelegramNotifier.send_report with the report."""
        settings = MagicMock()
        settings.telegram_bot_token = "t"
        settings.telegram_chat_id = "1"
        obs = TelegramObserver(settings)
        report = PipelineReport(started_at=datetime.now())
        report.add_step("ingest", StepReport(name="ingest", success_count=1))
        report.finished_at = datetime.now()

        with patch("personalscraper.observers.telegram.TelegramNotifier") as mock_cls:
            mock_notifier = MagicMock()
            mock_cls.return_value = mock_notifier

            with patch("personalscraper.observers.telegram.HttpTransport"):
                obs.on_pipeline_end(report)

            mock_notifier.send_report.assert_called_once_with(report)

    def test_all_other_callbacks_are_noop(self) -> None:
        """All callbacks except on_pipeline_end are no-ops."""
        settings = MagicMock()
        obs = TelegramObserver(settings)
        report = PipelineReport(started_at=datetime.now())
        step_report = StepReport(name="test")

        obs.on_pipeline_start(report)
        obs.on_step_start("ingest")
        obs.on_step_end("ingest", step_report, 1.0)
        obs.on_step_error("ingest", ValueError())
        obs.on_progress(MagicMock())
        # No exception = pass
