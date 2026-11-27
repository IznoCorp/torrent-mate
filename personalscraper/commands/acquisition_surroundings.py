"""What runs around an acquisition pass, for the commands and for the supervisor's worker.

A ``search`` closes what the library already owns before it queries a tracker; a ``grab`` reconciles the
open rows against the torrent client, switches the dead-stalled grabs, and tells Telegram what it
downloaded. The ``grab`` and ``search`` commands run these on their direct path; the worker runs the same
ones around a queued pass (:func:`personalscraper.app.supervisor.worker.open_engine`). They log under the
command's own logger (``cli.grab``, ``cli.search``), whoever calls them.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from rich.console import Console

from personalscraper.api.torrent._base import lookup_scoped
from personalscraper.i18n import t
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.acquire.reconcile import ReconcileSummary
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.conf.models.api_config import TorrentScope
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus
    from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber

grab_log = get_logger("cli.grab")
search_log = get_logger("cli.search")


def build_acq_telegram_subscriber(
    config: Config,
    settings: Settings,
    event_bus: EventBus,
) -> AcquisitionTelegramSubscriber | None:
    """Build the acquisition Telegram subscriber for a grab run (D8).

    Mirrors EXACTLY the gates of the ``run`` command's wiring
    (``commands/pipeline.py``): construction is gated on
    ``TelegramNotifier.is_configured(settings)``, and actual sends are gated
    inside the subscriber by ``config.notify.acquire_notify_enabled``. Without
    this wiring the D8 deliverable was unreachable from ``grab`` — the only
    command whose reconcile pass emits ``DownloadCompleted``.

    Args:
        config: Loaded application config (``notify.acquire_notify_enabled``).
        settings: Env-backed settings carrying the Telegram credentials.
        event_bus: The app bus the subscriber self-registers on.

    Returns:
        The constructed subscriber (caller owns ``close()``), or ``None``
        when Telegram is not configured.
    """
    from personalscraper.api.notify.telegram import TelegramNotifier  # noqa: PLC0415
    from personalscraper.api.transport._http import HttpTransport  # noqa: PLC0415
    from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber  # noqa: PLC0415

    if not TelegramNotifier.is_configured(settings):
        return None
    tg_transport = HttpTransport(
        TelegramNotifier.policy(settings.telegram_bot_token),
        event_bus=event_bus,
    )
    tg_notifier = TelegramNotifier(tg_transport, settings.telegram_chat_id)
    return AcquisitionTelegramSubscriber(
        event_bus,
        notifier=tg_notifier,
        enabled=config.notify.acquire_notify_enabled,
    )


def reconcile_before_run(
    acquire: AcquireContext, event_bus: EventBus, console: Console, *, scope: TorrentScope | None
) -> ReconcileSummary:
    """Run the B.3 reconciliation pass ahead of a real grab run (fail-soft).

    Gathers the torrent client's live items once for every OPEN row carrying a
    hash (``None`` on any client error — the vanished-torrent requeue, the
    intent confirmation and the download-event emission are then skipped
    rather than firing blind) and sweeps the open rows via
    :func:`personalscraper.acquire.reconcile.reconcile_wanted`.

    Args:
        acquire: The live :class:`AcquireContext` (store + ownership + client).
        event_bus: The app event bus (download events fire from the sweep).
        console: Rich console for the operator summary line.
        scope: What this instance owns in a shared client, or ``None`` (the whole
            client). Under a scope a stored hash held in another category is left
            out of the client view, so the sweep never settles it as ours.

    Returns:
        The pass summary (zeroes when the store is unavailable or the sweep
        failed — a reconciliation problem must never abort the grab run).
    """
    from personalscraper.acquire.reconcile import ReconcileSummary, reconcile_wanted  # noqa: PLC0415

    store = acquire.store
    if store is None:
        return ReconcileSummary()

    client_items: dict[str, TorrentItem] | None = None
    foreign: set[str] = set()
    torrent_client = acquire.torrent_client
    if torrent_client is not None:
        try:
            # Probe EVERY open row carrying a hash, not just the grabbed ones:
            # since D2 a 'searching' row can hold a pre-add intent, and a hash
            # the client is never asked about would read as « vanished » — the
            # sweep would requeue a row whose torrent is alive and downloading.
            # Full items, not bare hashes: the sweep reads ``progress`` to emit
            # the download lifecycle events (seed-caps D9).
            in_flight = store.wanted.hashes_in_flight()
            own, foreign = lookup_scoped(torrent_client, in_flight, scope)
            client_items = {t.hash.lower(): t for t in own}
        except Exception as exc:  # noqa: BLE001 — fail-soft: skip the requeue half
            grab_log.warning("cli.grab.reconcile_client_unavailable", error=str(exc))
            client_items = None

    # D2 — a grab confirmed out of the add→confirm crash window never ran the
    # grab-time obligation writer; record it now, from the torrent's own tracker
    # tag. Absent authority (no store) → no recorder, the confirmation still runs.
    authority = acquire.delete_authority
    recorder = authority.record_grab_obligation if authority is not None else None
    ownership = acquire.ownership

    try:
        summary = reconcile_wanted(
            store, ownership, client_items, event_bus=event_bus, record_obligation=recorder, foreign=foreign
        )
    except Exception as exc:  # noqa: BLE001 — reconciliation must never abort the grab
        grab_log.warning("cli.grab.reconcile_failed", error=str(exc))
        return ReconcileSummary()
    if summary.closed_owned or summary.requeued_missing or summary.confirmed_grabbed:
        reconciled = t(
            "cli_acquisition.grab.reconcile_summary",
            closed=summary.closed_owned,
            requeued=summary.requeued_missing,
            confirmed=summary.confirmed_grabbed,
        )
        console.print("[cyan]" + t("cli_acquisition.grab.reconcile_label") + "[/cyan] " + reconciled)
    # Its own line, and only when it happened — see the twin site in search.py.
    if summary.fell_back_to_episodes:
        fell_back = t("cli_acquisition.grab.reconcile_fell_back", seasons=summary.fell_back_to_episodes)
        console.print("[cyan]" + t("cli_acquisition.grab.reconcile_label") + "[/cyan] " + fell_back)
    return summary


def reswitch_before_run(
    acquire: AcquireContext, event_bus: EventBus, console: Console, *, scope: TorrentScope | None
) -> None:
    """Switch every dead-stalled grabbed release to another one before grabbing (reswitch #342).

    A grabbed torrent whose swarm is dead / that broke / that is stuck past the
    deadline is removed and its row requeued (the failed hash remembered) so the
    next search+grab picks a DIFFERENT release. Requires the torrent client (only
    built for a real run), so a dry-run / clientless config is a silent no-op.
    Fail-soft: a reswitch error never aborts the grab.

    Args:
        acquire: The live :class:`AcquireContext` (store + client).
        event_bus: The app event bus (a ``GrabReswitched`` is a visible trace).
        console: Rich console for the operator line.
        scope: What this instance owns in a shared client, or ``None``; a hash held
            in another category is never switched nor deleted.
    """
    from personalscraper.acquire._reswitch import reswitch_stalled

    store = acquire.store
    torrent_client = acquire.torrent_client
    if store is None or torrent_client is None:
        return
    try:
        summary = reswitch_stalled(store, torrent_client, time.time(), event_bus=event_bus, scope=scope)
    except Exception as exc:  # noqa: BLE001 — reswitch must never abort the grab
        grab_log.warning("cli.grab.reswitch_failed", error=str(exc))
        return
    if summary.reswitched:
        switched = t("cli_acquisition.grab.reswitch_summary", reswitched=summary.reswitched, checked=summary.checked)
        console.print("[cyan]" + t("cli_acquisition.grab.reswitch_label") + "[/cyan] " + switched)


def reconcile_before_search(acquire: AcquireContext, event_bus: EventBus, console: Console) -> ReconcileSummary:
    """Run the ownership reconcile sweep ahead of a real search run (fail-soft).

    Mirrors :func:`reconcile_before_run`'s guard choice.  That sweep has
    two halves: close the rows whose media the library already owns, and requeue a
    row whose torrent vanished from the client — the second half firing ONLY when
    the client's live items could actually be read (``client_items=None`` means
    « blind spot », and grab never requeues on a blind spot).

    On a search the blind spot is structural, not accidental: the search
    boundary is opened with ``build_torrent_client=False``, so there is no client
    to interrogate and ``client_items`` is always ``None``.  The ownership half
    therefore runs and the requeue half — like the download-event emission — is
    skipped by construction, the same behaviour grab falls back to, reached
    without ever contacting the daemon (NE-DOIT-PAS-8).  ``follow.py``'s detect
    sweep passes ``None`` for the same reason.

    Args:
        acquire: The live ``AcquireContext`` (store + ownership).
        event_bus: The app event bus (REQUIRED by the sweep; zero download
            events fire here — no client items, no observation).
        console: Rich console for the operator summary line.

    Returns:
        The sweep summary (zeroes when the store is unavailable or the sweep
        failed — a reconciliation problem must never abort the search run).
    """
    from personalscraper.acquire.reconcile import ReconcileSummary, reconcile_wanted  # noqa: PLC0415

    store = acquire.store
    if store is None:
        return ReconcileSummary()

    try:
        # client_items=None → ownership half only (see docstring): the sweep still closes by
        # ownership (mark_done) and does the season fallback, but never decides on the client's
        # view, so it cannot misread another instance's torrent.
        summary = reconcile_wanted(store, acquire.ownership, client_items=None, event_bus=event_bus)
    except Exception as exc:  # noqa: BLE001 — reconciliation must never abort the search
        search_log.warning("cli.search.reconcile_failed", error=str(exc))
        return ReconcileSummary()
    if summary.closed_owned:
        closed = t("cli_acquisition.search.reconcile_closed", closed=summary.closed_owned)
        console.print("[cyan]" + t("cli_acquisition.search.reconcile_label") + "[/cyan] " + closed)
    # Announced on its OWN line, and only when it happened: appending « 0 saisons »
    # to the line above would have printed a zero on every ordinary run — a number
    # nobody reads, which is how a number nobody compares gets there in the first place.
    if summary.fell_back_to_episodes:
        fell_back = t("cli_acquisition.search.reconcile_fell_back", seasons=summary.fell_back_to_episodes)
        console.print("[cyan]" + t("cli_acquisition.search.reconcile_label") + "[/cyan] " + fell_back)
    return summary
