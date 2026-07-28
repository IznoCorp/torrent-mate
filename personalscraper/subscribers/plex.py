"""Plex subscriber for the in-process EventBus — refresh what was just dispatched.

Self-subscribes on construction to :class:`ItemDispatched` and asks Plex to scan
the ONE folder the dispatcher just wrote. Modelled on
:class:`~personalscraper.subscribers.telegram.TelegramSubscriber`: constructor
injection of a ready client, self-subscription, ``close()`` unsubscribing.

**Fail-soft is absolute.** Plex down, token refused, path in no section, a bug in
the client — every one of them is a warning and nothing else. The transfer
already happened; reporting it as a failure because its notifier could not reach
a media server would be a lie about what the pipeline did.

Work is scheduled off-thread, like the Telegram subscriber, so a slow Plex can
never back up the bus (the performance contract: subscribers return fast or hand
the work to a thread).
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from personalscraper.core.event_bus import EventBus, SubscriptionToken
from personalscraper.dispatch.events import ItemDispatched
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.api.plex import PlexClient

log = get_logger(__name__)


class PlexSubscriber:
    """Triggers a targeted Plex scan for each dispatched folder."""

    name = "plex"

    def __init__(self, bus: EventBus, client: PlexClient) -> None:
        """Register the subscription and store the client.

        Args:
            bus: The :class:`EventBus` to subscribe to.
            client: A pre-configured :class:`~personalscraper.api.plex.PlexClient`
                (base URL and token already wired). Construction-time injection
                keeps the subscriber free of transport and credential concerns.
        """
        self._bus = bus
        self._client = client
        self._tokens: list[SubscriptionToken] = [bus.subscribe(ItemDispatched, self._on_item_dispatched)]

    def close(self) -> None:
        """Unsubscribe every stored token. Idempotent."""
        for token in self._tokens:
            self._bus.unsubscribe(token)
        self._tokens.clear()

    def _on_item_dispatched(self, event: ItemDispatched) -> None:
        """Schedule a refresh of the dispatched folder (never blocks, never raises).

        A ``target_path`` of ``None`` is the honest signal that this emitter did
        not carry a folder (the field is additive — D1), so there is nothing to
        scan and the event is skipped at DEBUG rather than guessed at.

        Args:
            event: The dispatch record carrying the destination folder.
        """
        target = event.target_path
        if target is None:
            log.debug("plex.skipped_no_target_path", item=event.item, action=event.action)
            return
        threading.Thread(
            target=self._refresh,
            args=(target,),
            name="plex-refresh",
            daemon=True,
        ).start()

    def _refresh(self, target: object) -> None:
        """Call the client and swallow EVERYTHING (thread body — nothing may escape).

        An exception escaping a daemon thread would be printed to stderr by the
        threading machinery, polluting an operator's run output for a best-effort
        trigger. The client is already fail-soft; this is the second belt.

        Args:
            target: The dispatched folder (typed loosely — the client owns it).
        """
        try:
            self._client.refresh(target)  # type: ignore[arg-type]  # Path, kept loose for the thread seam
        except Exception:  # noqa: BLE001 — fail-soft: a dispatch is never failed by its notifier
            log.warning("plex.refresh_failed", path=str(target), exc_info=True)


__all__ = ["PlexSubscriber"]
