"""Muted Telegram subscriber for acquisition events (RP4).

Subscribes to all 10 acquisition events from :mod:`personalscraper.acquire.events`.
Each handler formats a human-readable message and emits a structlog line.
Network send is dispatched on a fire-and-forget daemon thread only when
``enabled=True`` (default ``False`` — muted until wave-4/5 producers are active).

Mirrors the pattern of :mod:`personalscraper.subscribers.telegram`:
- Self-registers in ``__init__`` via ``bus.subscribe``.
- ``_spawn`` launches a daemon thread for the HTTP call.
- ``close`` unsubscribes every stored token (idempotent).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from personalscraper.acquire.events import (
    GrabFailed,
    GrabSucceeded,
    RatioMeasured,
    SeedObligationBreached,
    SeedObligationRecorded,
    SeedObligationSatisfied,
    SeriesFollowed,
    SeriesUnfollowed,
    WantedAbandoned,
    WantedEnqueued,
)
from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.notify.telegram import TelegramNotifier

log = get_logger(__name__)


class AcquisitionTelegramSubscriber:
    """Formats and (optionally) sends Telegram alerts for acquisition events.

    Subscribes to all 10 acquisition event types defined in
    :mod:`personalscraper.acquire.events`. Each handler formats a short message
    and emits a structlog line at ``INFO`` level (``acquire.notify.<event>``).
    When ``enabled=True`` the message is also sent via ``notifier`` on a
    fire-and-forget daemon thread (fail-soft: any notifier exception is caught
    and logged at ``WARNING``). When ``enabled=False`` (default) the subscriber
    is fully silent toward Telegram — useful for wiring + testing before the
    wave-4/5 producers go live.

    Attributes:
        name: Subscriber identity tag for logging.
    """

    name = "acquire_telegram"

    def __init__(
        self,
        bus: EventBus,
        notifier: TelegramNotifier | None = None,
        *,
        enabled: bool = False,
    ) -> None:
        """Register one handler per acquisition event and store state.

        Args:
            bus: The :class:`EventBus` to subscribe to.
            notifier: Pre-configured :class:`TelegramNotifier`; required when
                ``enabled=True``. When ``None`` and ``enabled=True``, sending
                is silently skipped (fail-soft for mis-configured callers).
            enabled: When ``True``, handlers send messages via ``notifier``.
                Default ``False`` (muted) — no messages sent until wave-4/5.
        """
        self._bus = bus
        self._notifier = notifier
        self._enabled = enabled
        self._tokens: list[SubscriptionToken] = [
            bus.subscribe(SeriesFollowed, self._on_series_followed),
            bus.subscribe(SeriesUnfollowed, self._on_series_unfollowed),
            bus.subscribe(WantedEnqueued, self._on_wanted_enqueued),
            bus.subscribe(WantedAbandoned, self._on_wanted_abandoned),
            bus.subscribe(GrabSucceeded, self._on_grab_succeeded),
            bus.subscribe(GrabFailed, self._on_grab_failed),
            bus.subscribe(SeedObligationRecorded, self._on_seed_obligation_recorded),
            bus.subscribe(SeedObligationBreached, self._on_seed_obligation_breached),
            bus.subscribe(SeedObligationSatisfied, self._on_seed_obligation_satisfied),
            bus.subscribe(RatioMeasured, self._on_ratio_measured),
        ]

    def close(self) -> None:
        """Unsubscribe every stored token. Idempotent.

        Releases all 10 subscriptions registered in ``__init__``.
        """
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens = []

    @staticmethod
    def _spawn(target: object, *args: object) -> None:
        """Schedule ``target(*args)`` on a fire-and-forget daemon thread.

        The daemon flag ensures the worker dies with the interpreter so a
        hanging Telegram POST cannot prevent the pipeline from exiting.
        Any uncaught exception from the worker is logged at WARNING level.
        """

        def _runner() -> None:
            try:
                target(*args)  # type: ignore[operator]
            except Exception:
                log.warning(
                    "acquire_telegram_subscriber_worker_crashed",
                    target=getattr(target, "__name__", repr(target)),
                    exc_info=True,
                )

        threading.Thread(target=_runner, daemon=True).start()

    def _send(self, message: str, event_name: str) -> None:
        """Background-thread worker: send message (fail-soft).

        Args:
            message: Plain-text or HTML message to send.
            event_name: Event class name for the warning log.
        """
        if self._notifier is None:
            log.warning("acquire_telegram_subscriber_no_notifier", kind=event_name)
            return
        if not self._notifier.send(message):
            log.warning("acquire_telegram_subscriber_send_failed", kind=event_name)

    def _dispatch(self, message: str, event_name: str) -> None:
        """Log the structlog line and optionally schedule the send.

        Args:
            message: Formatted human-readable message.
            event_name: Structlog event name (``acquire.notify.<event>``).
        """
        log.info("acquire.notify.event", acquire_event=event_name, message=message)
        if self._enabled:
            self._spawn(self._send, message, event_name)

    # ----- Bus callbacks --------------------------------------------------

    def _on_series_followed(self, event: SeriesFollowed) -> None:
        """Handle SeriesFollowed — format + dispatch."""
        msg = f"📺 Following: {event.title} (tvdb:{event.media_ref.tvdb_id})"
        self._dispatch(msg, "series_followed")

    def _on_series_unfollowed(self, event: SeriesUnfollowed) -> None:
        """Handle SeriesUnfollowed — format + dispatch."""
        msg = f"📺 Unfollowed: tvdb:{event.media_ref.tvdb_id}"
        self._dispatch(msg, "series_unfollowed")

    def _on_wanted_enqueued(self, event: WantedEnqueued) -> None:
        """Handle WantedEnqueued — format + dispatch."""
        if event.kind == "episode":
            loc = f"S{event.season:02d}E{event.episode:02d}" if event.season and event.episode else "?"
            msg = f"🔍 Wanted episode: tvdb:{event.media_ref.tvdb_id} {loc}"
        else:
            msg = f"🔍 Wanted movie: tvdb:{event.media_ref.tvdb_id}"
        self._dispatch(msg, "wanted_enqueued")

    def _on_wanted_abandoned(self, event: WantedAbandoned) -> None:
        """Handle WantedAbandoned — format + dispatch."""
        msg = f"❌ Wanted abandoned: tvdb:{event.media_ref.tvdb_id} — {event.reason}"
        self._dispatch(msg, "wanted_abandoned")

    def _on_grab_succeeded(self, event: GrabSucceeded) -> None:
        """Handle GrabSucceeded — format + dispatch."""
        tags = ", ".join(event.tags) if event.tags else "—"
        msg = (
            f"✅ Grabbed: {event.info_hash[:8]}… tracker={event.source_tracker} cat={event.category or '?'} tags={tags}"
        )
        self._dispatch(msg, "grab_succeeded")

    def _on_grab_failed(self, event: GrabFailed) -> None:
        """Handle GrabFailed — format + dispatch."""
        tracker = event.source_tracker or "unknown"
        msg = f"⚠️ Grab failed: tracker={tracker} — {event.reason}"
        self._dispatch(msg, "grab_failed")

    def _on_seed_obligation_recorded(self, event: SeedObligationRecorded) -> None:
        """Handle SeedObligationRecorded — format + dispatch."""
        hours = event.min_seed_time_s // 3600
        msg = f"🌱 Seed obligation: {event.info_hash[:8]}… tracker={event.source_tracker} min={hours}h"
        self._dispatch(msg, "seed_obligation_recorded")

    def _on_seed_obligation_breached(self, event: SeedObligationBreached) -> None:
        """Handle SeedObligationBreached — format + dispatch."""
        msg = f"🚨 Seed obligation BREACHED: {event.info_hash[:8]}… tracker={event.source_tracker}"
        self._dispatch(msg, "seed_obligation_breached")

    def _on_seed_obligation_satisfied(self, event: SeedObligationSatisfied) -> None:
        """Handle SeedObligationSatisfied — format + dispatch."""
        msg = f"✔️ Seed obligation satisfied: {event.info_hash[:8]}… tracker={event.source_tracker}"
        self._dispatch(msg, "seed_obligation_satisfied")

    def _on_ratio_measured(self, event: RatioMeasured) -> None:
        """Handle RatioMeasured — format + dispatch."""
        msg = f"📊 Ratio: tracker={event.tracker} observed={event.observed_ratio:.2f} target={event.target_ratio:.2f}"
        self._dispatch(msg, "ratio_measured")
