"""Telegram observer — sends pipeline summary via Telegram on completion."""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.api.notify.telegram import TelegramNotifier
from personalscraper.api.transport._http import HttpTransport
from personalscraper.config import Settings
from personalscraper.pipeline_observer import StepEvent

if TYPE_CHECKING:
    from personalscraper.models import PipelineReport, StepReport


class TelegramObserver:
    """Sends the pipeline summary to a Telegram chat via ``on_pipeline_end``."""

    name = "telegram"

    def __init__(self, settings: Settings) -> None:
        """Initialize the observer with Telegram credentials.

        Args:
            settings: Pipeline settings containing telegram_bot_token
                and telegram_chat_id.
        """
        self._settings = settings

    def on_pipeline_start(self, report: PipelineReport) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_pipeline_end(self, report: PipelineReport) -> None:
        """Send the pipeline summary via Telegram.

        Args:
            report: The completed ``PipelineReport`` to send as HTML.
        """
        transport = HttpTransport(TelegramNotifier.policy(self._settings.telegram_bot_token))
        notifier = TelegramNotifier(transport, self._settings.telegram_chat_id)
        notifier.send_report(report)

    def on_step_start(self, step: str) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_step_end(self, step: str, report: StepReport, elapsed: float) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_step_error(self, step: str, error: Exception) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""

    def on_progress(self, event: StepEvent) -> None:  # noqa: ARG002
        """No-op — Telegram summary is sent only at completion."""
