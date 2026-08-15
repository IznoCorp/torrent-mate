"""CLI command: ``personalscraper search`` — the availability pass (DESIGN §4 D5).

``search`` is the MIDDLE pass of the three-pass flow ``detect → search → grab``:
``detect`` enqueues what aired, ``search`` states whether it is takeable, ``grab``
takes what a search already concluded takeable. The pass **states availability and
downloads nothing** — it holds no torrent client at all, so the command opens its
boundary with ``build_torrent_client=False`` and never wakes qBittorrent
(NE-DOIT-PAS-8: ne pas maltraiter les dépendances). Its tracker traffic is bounded
by the per-item cadence gates, for the same reason.

Drives :meth:`~personalscraper.acquire.service.AcquisitionService.run_search` over
the pending + stale-searching queue:

* ``--dry-run`` shows what WOULD be searched after cadence gating — no tracker
  call, no write.
* ``--limit N`` caps the number of items searched in one run.
* ``--followed-id ID`` restricts the run to one followed series' pending items.

Reconcile guard: the real run mirrors ``commands/grab.py``'s
``_reconcile_before_run`` choice — sweep the owned rows closed before searching,
and never requeue a vanished torrent on a blind spot. Here the blind spot is
structural (no client on this boundary), so only the ownership half runs. See
:func:`_reconcile_before_search`.

Registered against the shared Typer ``app`` (imported side-effect in cli.py).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from personalscraper import cli_helpers
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.logger import get_logger
from personalscraper.subscribers.redis_stream import build_redis_publisher

if TYPE_CHECKING:
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.acquire.reconcile import ReconcileSummary
    from personalscraper.acquire.service import AcquisitionService
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

log = get_logger("cli.search")


# ── Command ──────────────────────────────────────────────────────────────────────


@command_with_telemetry("search")
@handle_cli_errors
def search(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what WOULD be searched after cadence gating. No tracker calls, no writes.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum number of wanted items to search. Default: all pending.",
    ),
    followed_id: int | None = typer.Option(
        None,
        "--followed-id",
        help="Restrict the run to one followed series' pending items.",
    ),
) -> None:
    """Run the search pass — state availability for pending wanted items."""
    config = ctx.obj.config
    assert config is not None  # guaranteed by callback
    console = state["console"]
    settings = cli_helpers.get_settings()

    # The search pass NEVER needs the torrent client — neither in dry-run nor in a
    # real run.  ``build_torrent_client=False`` means no connect + no login is
    # attempted at the boundary, and ``acquire.grab`` stays None (the factory only
    # builds GrabCore when a client is present), so the command builds the
    # orchestrator + service inline — see _build_search_service.
    with (
        cli_run_row(config, "search") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=False) as app_context,
    ):
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        try:
            acquire = app_context.acquire
            if acquire is None:
                console.print("[red]AcquireContext not available.[/red]")
                raise typer.Exit(1)
            if acquire.store is None:
                console.print("[red]No acquire store — cannot run search.[/red]")
                raise typer.Exit(1)

            service = _build_search_service(acquire, config, app_context.event_bus)

            if dry_run:
                _run_dry(acquire, config, console, service, limit=limit, followed_id=followed_id)
            else:
                # Reconcile before searching: an item already in the médiathèque
                # closes ``done`` instead of costing a tracker query.
                reconcile = _reconcile_before_search(acquire, app_context.event_bus, console)

                summary = service.run_search(limit=limit, followed_id=followed_id)
                console.print(
                    f"[green]Search complete:[/green] "
                    f"{summary.available} available, "
                    f"{summary.waiting} waiting, "
                    f"{summary.unverified} unverified, "
                    f"{summary.abandoned} abandoned, "
                    f"{summary.skipped} skipped."
                )
                # §5 « résultat chiffré »: persist the run's numbers on its
                # pipeline_run row (self-owned for cron/CLI; the web runner's row
                # when spawned by a web-triggered search).  ``requeued_missing`` is
                # NOT recorded — this pass structurally cannot requeue (no client),
                # and a hardcoded 0 would read as « nothing vanished » in the UI.
                run_rec.record_counts(
                    {
                        "available": summary.available,
                        "waiting": summary.waiting,
                        "unverified": summary.unverified,
                        "abandoned": summary.abandoned,
                        "skipped": summary.skipped,
                        "closed_owned": reconcile.closed_owned,
                    }
                )
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


# ── Service builder ──────────────────────────────────────────────────────────────


def _build_search_service(
    acquire: "AcquireContext",
    config: "Config",
    event_bus: "EventBus",
) -> "AcquisitionService":
    """Build orchestrator + service inline for the search pass.

    ``acquire/_factory.py`` builds ``GrabCore`` (orchestrator + service) only when
    a torrent client is present, and the search boundary deliberately has none —
    so ``acquire.grab`` is always ``None`` here.  The orchestrator's
    :meth:`~personalscraper.acquire.orchestrator.GrabOrchestrator.search` is a pure
    search → filter → rank chain that never touches ``self._torrent_client``, so
    this helper constructs the pair directly with ``torrent_client=None``.

    Args:
        acquire: The live ``AcquireContext`` (store + tracker_registry).
        config: Typed JSON5 configuration.
        event_bus: In-process event bus.

    Returns:
        A ready ``AcquisitionService`` wired for the search pass.
    """
    from personalscraper.acquire.domain import WantedItem  # noqa: PLC0415
    from personalscraper.acquire.orchestrator import GrabOrchestrator  # noqa: PLC0415
    from personalscraper.acquire.service import AcquisitionService  # noqa: PLC0415

    store = acquire.store
    assert store is not None  # caller already checked

    # Follow D3 title resolver: same pattern as the factory — resolves the
    # followed-series title so tracker queries are "{title} SxxEyy", not a bare ID.
    def _title_resolver(item: WantedItem) -> str | None:
        if item.followed_id is None:
            return None
        row = store.follow.get(item.followed_id)
        return row.title if row is not None else None

    # #28 (review HIGH) — the search pass MUST resolve the year too, or its movie
    # availability verdict counts the WRONG « Wicker* » film (query yearless +
    # filter_to_movie year-disabled) while the grab pass, correctly year-wired,
    # disagrees. Both feed the same _search_chain, so the wiring must match.
    def _year_resolver(item: WantedItem) -> int | None:
        if item.followed_id is None:
            return None
        row = store.follow.get(item.followed_id)
        return row.year if row is not None else None

    # Season-pack coverage resolver (review F4) — same wiring as the factory,
    # so the search pass verdict and the grab never diverge on what counts as
    # « the season ».
    def _episode_count_resolver(item: WantedItem) -> int | None:
        if item.followed_id is None or item.season is None:
            return None
        aired = store.aired.list_for_followed(item.followed_id)
        return len([r for r in aired if r.season == item.season]) or None

    # Original-title resolver (#435) — same wiring as the factory, so the
    # search pass verdict and the grab never diverge on which releases count
    # as « the movie » (a cross-language release must not read as available
    # to one pass and all_filtered to the other).
    def _original_title_resolver(item: WantedItem) -> str | None:
        if item.followed_id is None:
            return None
        row = store.follow.get(item.followed_id)
        return row.original_title if row is not None else None

    orchestrator = GrabOrchestrator(
        tracker_registry=acquire.tracker_registry,
        torrent_client=None,  # the search pass adds nothing
        event_bus=event_bus,
        ranking=config.ranking,
        title_resolver=_title_resolver,
        year_resolver=_year_resolver,
        original_title_resolver=_original_title_resolver,
        episode_count_resolver=_episode_count_resolver,
        bandwidth=config.acquire.bandwidth,
    )
    return AcquisitionService(
        store=store,
        orchestrator=orchestrator,
        event_bus=event_bus,
        config=config,
    )


# ── Reconcile ────────────────────────────────────────────────────────────────────


def _reconcile_before_search(acquire: "AcquireContext", event_bus: "EventBus", console: Console) -> "ReconcileSummary":
    """Run the ownership reconcile sweep ahead of a real search run (fail-soft).

    Mirrors ``grab.py``'s ``_reconcile_before_run`` guard choice.  That sweep has
    two halves: close the rows whose media the library already owns, and requeue a
    row whose torrent vanished from the client — the second half firing ONLY when
    the client's live items could actually be read (``client_items=None`` means
    « blind spot », and grab never requeues on a blind spot).

    On this command the blind spot is structural, not accidental: the search
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
        # client_items=None → ownership half only (see docstring).
        summary = reconcile_wanted(store, acquire.ownership, client_items=None, event_bus=event_bus)
    except Exception as exc:  # noqa: BLE001 — reconciliation must never abort the search
        log.warning("cli.search.reconcile_failed", error=str(exc))
        return ReconcileSummary()
    if summary.closed_owned:
        console.print(f"[cyan]Réconciliation:[/cyan] {summary.closed_owned} clos (déjà en médiathèque).")
    return summary


# ── Dry-run ──────────────────────────────────────────────────────────────────────


def _run_dry(
    acquire: "AcquireContext",
    config: "Config",
    console: Console,
    service: "AcquisitionService",
    *,
    limit: int | None,
    followed_id: int | None = None,
) -> None:
    """Dry-run: show what WOULD be searched after cadence gating. No tracker calls, no writes.

    Builds the queue identically to ``run_search`` (pending + stale-searching),
    then replays the pass's two gates per item using the pure predicates from
    ``acquire/cadence.py`` in the same order the service applies them (cutoff
    first, then cadence).  Nothing is claimed, no status is written and no
    tracker is contacted.

    Args:
        acquire: The live ``AcquireContext``.
        config: Typed JSON5 configuration (for the global cadence policy).
        console: Rich Console for output.
        service: The already-built ``AcquisitionService`` (for queue building
            and cadence resolution).
        limit: Max items to preview.
        followed_id: When set, restrict to one followed series' pending items.
    """
    from personalscraper.acquire.cadence import is_due_by_cadence, is_past_cutoff  # noqa: PLC0415
    from personalscraper.acquire.desired import cadence_from_config  # noqa: PLC0415

    store = acquire.store
    if store is None:
        console.print("[yellow]No acquire store — nothing to dry-run.[/yellow]")
        return

    now = int(time.time())

    # Build the queue exactly like run_search (pending + stale-searching,
    # de-duplicated, scoped, capped).  _build_queue is the shared private helper
    # both passes use — reusing it is what makes the preview faithful; a
    # re-implementation here would be free to drift from the real pass.
    queue = service._build_queue(  # noqa: SLF001
        store.wanted.list_pending(),
        now=now,
        limit=limit,
        followed_id=followed_id,
    )

    if not queue:
        console.print("[yellow]No pending wanted items.[/yellow]")
        return

    global_cadence = cadence_from_config(config.acquire.cadence)
    # _load_follow_map / _cadence_for are private read-only helpers — same
    # faithfulness justification as _build_queue above.
    follow_map = service._load_follow_map(queue)  # noqa: SLF001

    would_search: list[str] = []
    would_skip: list[str] = []
    would_abandon: list[str] = []

    for item in queue:
        cadence = service._cadence_for(item, follow_map, global_cadence)  # noqa: SLF001
        label = f"{item.media_ref} ({item.kind})"
        if is_past_cutoff(cadence, now=now, enqueued_at=item.enqueued_at):
            would_abandon.append(label)
        elif not is_due_by_cadence(cadence, now=now, enqueued_at=item.enqueued_at, last_search_at=item.last_search_at):
            would_skip.append(label)
        else:
            would_search.append(label)

    console.print(f"\n[bold]Search dry-run:[/bold] {len(queue)} items in queue")
    console.print(f"  [green]Would search:[/green] {len(would_search)}")
    for label in would_search:
        console.print(f"    • {label}")
    if would_skip:
        console.print(f"  [yellow]Skipped by cadence:[/yellow] {len(would_skip)}")
        for label in would_skip:
            console.print(f"    • {label}")
    if would_abandon:
        console.print(f"  [red]Would abandon (cutoff):[/red] {len(would_abandon)}")
        for label in would_abandon:
            console.print(f"    • {label}")

    console.print("\n[dim]Dry-run complete — no trackers contacted, no writes performed.[/dim]")
