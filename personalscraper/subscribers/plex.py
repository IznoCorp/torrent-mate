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
    from personalscraper.config import Settings

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

        Only ``type(exc).__name__`` is logged — NEVER ``exc_info``. The console
        renderer expands ``exc_info`` into a traceback WITH FRAME LOCALS, and any
        frame between here and the socket holds the ``X-Plex-Token`` header, so
        a traceback here printed the credential in clear to the operator's
        terminal. The exception type is what an operator can act on anyway.

        Args:
            target: The dispatched folder (typed loosely — the client owns it).
        """
        try:
            self._client.refresh(target)  # type: ignore[arg-type]  # Path, kept loose for the thread seam
        except Exception as exc:  # noqa: BLE001 — fail-soft: a dispatch is never failed by its notifier
            log.warning("plex.refresh_failed", path=str(target), error=type(exc).__name__)


def build_plex_subscriber(bus: EventBus, settings: Settings) -> PlexSubscriber | None:
    """Build + wire the Plex refresh trigger for one dispatch entry point.

    The SINGLE owner of the wiring decision, for the same reason
    ``resolve_dispatch_authority`` and ``maybe_run_post_dispatch_maintenance``
    are single owners: the pipeline's ``DispatchStep`` and the standalone
    ``personalscraper dispatch`` command are BOTH dispatch composition roots and
    must behave identically. Wiring this in only one of them left the other
    emitting ``ItemDispatched`` with nobody listening — media on disk, invisible
    in Plex, which is the exact bug this feature closes (Margin Call).

    The gate is the token alone, deliberately NOT ``--headless``: the other
    subscribers produce OPERATOR OUTPUT (console, Telegram) that a cron run
    legitimately silences, whereas this one makes the dispatched media visible
    in Plex — a headless run needs it exactly as much.

    Fail-soft at construction too: a malformed ``PLEX_URL`` returns ``None``
    instead of taking the caller's boot down with it.

    Args:
        bus: The process :class:`EventBus` the subscriber listens on.
        settings: Environment settings carrying ``plex_url`` / ``plex_token``.

    Returns:
        A subscribed :class:`PlexSubscriber`, or ``None`` when no token is
        configured or the client could not be constructed. Callers wire it
        unconditionally and simply skip a ``None``.
    """
    if not settings.plex_token:
        log.info("plex_refresh_disabled", reason="no_token")
        return None
    # Imported here so the caller pays nothing when no token is set, and so the
    # symbol is resolved at call time (the tests substitute the client).
    from personalscraper.api.plex import PlexClient  # noqa: PLC0415

    try:
        return PlexSubscriber(bus, PlexClient(settings.plex_url, settings.plex_token))
    except Exception as exc:  # noqa: BLE001 — a notifier never breaks the caller's boot
        log.warning("plex_refresh_unavailable", error=type(exc).__name__)
        return None


__all__ = ["PlexSubscriber", "build_plex_subscriber"]
