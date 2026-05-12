"""Telegram subscriber — replaces ``observers.telegram.TelegramObserver``.

Self-subscribes on construction to :class:`PipelineEnded` and
:class:`StepErrored`. Both handlers schedule the HTTP send off-thread so the
bus dispatch returns in well under 50 ms even if Telegram is slow or
unreachable (DESIGN §Performance contract — subscribers MUST be fast or
schedule work off-thread; the bus has no async offload in v1).

Phase 4 will add subscriptions to :class:`CircuitBreakerOpened` and
:class:`DiskFullWarning` in the same sub-phase that introduces those
events; do NOT pre-emptively wire them here.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.logger import get_logger
from personalscraper.pipeline_events import PipelineEnded, StepErrored

if TYPE_CHECKING:
    from personalscraper.api.notify.telegram import TelegramNotifier

log = get_logger(__name__)


class TelegramSubscriber:
    """Sends pipeline summary + step-error alerts via the Telegram Bot API.

    Subscribes to :class:`PipelineEnded` (HTML summary) and :class:`StepErrored`
    (step failure alert) only. Network I/O is dispatched on a daemon thread so
    a slow Telegram response cannot back up the bus.
    """

    name = "telegram"

    def __init__(self, bus: EventBus, notifier: TelegramNotifier) -> None:
        """Register two subscriptions and store the notifier.

        Args:
            bus: The :class:`EventBus` to subscribe to.
            notifier: A pre-configured :class:`TelegramNotifier` (transport,
                token and chat ID already wired). Construction-time injection
                keeps the subscriber decoupled from HTTP transport internals.
        """
        self._bus = bus
        self._notifier = notifier
        self._tokens: list[SubscriptionToken] = [
            bus.subscribe(PipelineEnded, self._on_pipeline_ended),  # type: ignore[arg-type]
            bus.subscribe(StepErrored, self._on_step_errored),  # type: ignore[arg-type]
        ]

    def close(self) -> None:
        """Unsubscribe both tokens. Idempotent."""
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens = []

    @staticmethod
    def _spawn(target: object, *args: object) -> None:
        """Schedule ``target(*args)`` on a fire-and-forget daemon thread.

        The daemon flag ensures the worker dies with the interpreter so a
        hanging Telegram POST cannot prevent the pipeline from exiting.
        """
        threading.Thread(target=target, args=args, daemon=True).start()  # type: ignore[arg-type]

    def _send_html(self, html: str) -> None:
        """Background-thread worker: HTML report send (fail-soft)."""
        if not self._notifier.send(html, parse_mode="HTML"):
            log.warning("telegram_subscriber_send_failed", concern="pipeline_ended")

    def _send_error_alert(self, step: str, error_class: str, error_message: str) -> None:
        """Background-thread worker: step-error alert (fail-soft)."""
        body = f"<b>step:</b> {step}\n<b>{error_class}:</b> {error_message}"
        if not self._notifier.send(body, parse_mode="HTML"):
            log.warning("telegram_subscriber_send_failed", concern="step_errored", step=step)

    # ----- Bus callbacks --------------------------------------------------

    def _on_pipeline_ended(self, event: PipelineEnded) -> None:
        """Handle :class:`PipelineEnded` — schedule the HTML summary send."""
        html = event.report.to_html()
        self._spawn(self._send_html, html)

    def _on_step_errored(self, event: StepErrored) -> None:
        """Handle :class:`StepErrored` — schedule an alert send."""
        self._spawn(self._send_error_alert, event.step, event.error_class, event.error_message)
