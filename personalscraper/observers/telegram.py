"""Telegram observer — sends pipeline summary via Telegram on completion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.api.notify.telegram import TelegramNotifier
from personalscraper.pipeline_observer import StepEvent

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


class TelegramObserver:
    """Sends the pipeline summary to a Telegram chat via ``on_pipeline_end``."""

    name = "telegram"

    def __init__(self, notifier: TelegramNotifier) -> None:
        """Initialize the observer with a pre-configured Telegram notifier.

        Args:
            notifier: A configured ``TelegramNotifier`` instance (already
                wired with transport, token, and chat ID). Construction-time
                injection eliminates the need for the observer to depend on
                HTTP transport internals.
        """
        self._notifier = notifier

    def on_pipeline_start(self, report: PipelineReport) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_pipeline_end(self, report: PipelineReport) -> None:
        """Send the pipeline summary via Telegram.

        Args:
            report: The completed ``PipelineReport`` to send as HTML.
        """
        if not self._notifier.send_report(report):
            from personalscraper.logger import get_logger

            get_logger(__name__).warning("telegram_observer_send_failed", reason="send_report_returned_false")

    def on_step_start(self, step: str) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_step_error(self, step: str, error: Exception) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_progress(self, event: StepEvent) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""
