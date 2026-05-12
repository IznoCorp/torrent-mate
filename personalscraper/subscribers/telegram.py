"""Telegram subscriber — replaces ``observers.telegram.TelegramObserver``.

Self-subscribes on construction to :class:`PipelineEnded`,
:class:`StepErrored`, :class:`CircuitBreakerOpened` (Sub-phase 4.1), and
:class:`DiskFullWarning` (Sub-phase 4.2b). All handlers schedule the HTTP
send off-thread so the bus dispatch returns in well under 50 ms even if
Telegram is slow or unreachable (DESIGN §Performance contract — subscribers
MUST be fast or schedule work off-thread; the bus has no async offload in
v1).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from personalscraper.core.circuit import CircuitBreakerOpened
from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.indexer.events import DiskFullWarning
from personalscraper.logger import get_logger
from personalscraper.pipeline_events import PipelineEnded, StepErrored

if TYPE_CHECKING:
    from personalscraper.api.notify.telegram import TelegramNotifier

log = get_logger(__name__)


class TelegramSubscriber:
    """Sends pipeline summary + step-error + circuit-trip + disk-full alerts via Telegram.

    Subscribes to :class:`PipelineEnded` (HTML summary), :class:`StepErrored`
    (step failure alert), :class:`CircuitBreakerOpened` (provider-trip alert),
    and :class:`DiskFullWarning` (disk-saturation alert). Network I/O is
    dispatched on a daemon thread so a slow Telegram response cannot back up
    the bus.
    """

    name = "telegram"

    def __init__(self, bus: EventBus, notifier: TelegramNotifier) -> None:
        """Register four subscriptions and store the notifier.

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
            bus.subscribe(CircuitBreakerOpened, self._on_circuit_opened),  # type: ignore[arg-type]
            bus.subscribe(DiskFullWarning, self._on_disk_full),  # type: ignore[arg-type]
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

    def _send_circuit_alert(
        self,
        breaker: str,
        failure_count: int,
        last_error_class: str,
        last_error_message: str,
    ) -> None:
        """Background-thread worker: circuit-breaker-opened alert (fail-soft)."""
        body = (
            f"⚠️ Circuit breaker tripped: <b>{breaker}</b> "
            f"({failure_count} failures, last: {last_error_class}: {last_error_message})"
        )
        if not self._notifier.send(body, parse_mode="HTML"):
            log.warning("telegram_subscriber_send_failed", concern="circuit_opened", breaker=breaker)

    def _send_disk_full_alert(
        self,
        disk_path: str,
        free_bytes: int,
        threshold_bytes: int,
    ) -> None:
        """Background-thread worker: disk-full warning (fail-soft)."""
        free_gb = free_bytes // 1_000_000_000
        threshold_gb = threshold_bytes // 1_000_000_000
        body = f"🪐 Disk full warning: <code>{disk_path}</code> free={free_gb}GB threshold={threshold_gb}GB"
        if not self._notifier.send(body, parse_mode="HTML"):
            log.warning("telegram_subscriber_send_failed", concern="disk_full_warning", disk_path=disk_path)

    # ----- Bus callbacks --------------------------------------------------

    def _on_pipeline_ended(self, event: PipelineEnded) -> None:
        """Handle :class:`PipelineEnded` — schedule the HTML summary send."""
        html = event.report.to_html()
        self._spawn(self._send_html, html)

    def _on_step_errored(self, event: StepErrored) -> None:
        """Handle :class:`StepErrored` — schedule an alert send."""
        self._spawn(self._send_error_alert, event.step, event.error_class, event.error_message)

    def _on_circuit_opened(self, event: CircuitBreakerOpened) -> None:
        """Handle :class:`CircuitBreakerOpened` — schedule the circuit-trip alert send."""
        self._spawn(
            self._send_circuit_alert,
            event.breaker,
            event.failure_count,
            event.last_error_class,
            event.last_error_message,
        )

    def _on_disk_full(self, event: DiskFullWarning) -> None:
        """Handle :class:`DiskFullWarning` — schedule the disk-full alert send."""
        self._spawn(
            self._send_disk_full_alert,
            str(event.disk_path),
            event.free_bytes,
            event.threshold_bytes,
        )
