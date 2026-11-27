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

Reconcile guard: the real run mirrors the grab's
:func:`~personalscraper.commands.acquisition_surroundings.reconcile_before_run` choice —
sweep the owned rows closed before searching, and never requeue a vanished torrent on a
blind spot. Here the blind spot is structural (no client on this boundary), so only the
ownership half runs. See
:func:`~personalscraper.commands.acquisition_surroundings.reconcile_before_search`.

Registered against the shared Typer ``app`` (imported side-effect in cli.py).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import typer
from rich.console import Console

from personalscraper import cli_helpers
from personalscraper.app.supervisor.acquisition_execution import search_counts
from personalscraper.app.supervisor.model import JobKind
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.commands import acquisition_queue
from personalscraper.commands._cli_run_row import cli_run_row
from personalscraper.commands.acquisition_surroundings import reconcile_before_search as _reconcile_before_search
from personalscraper.i18n import t
from personalscraper.subscribers.redis_stream import build_redis_publisher

if TYPE_CHECKING:
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.acquire.service import AcquisitionService
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus

# ── Command ──────────────────────────────────────────────────────────────────────


@command_with_telemetry("search", help=t("cli_acquisition.search.help"))
@handle_cli_errors
def search(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=t("cli_acquisition.search.dry_run_help"),
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help=t("cli_acquisition.search.limit_help"),
    ),
    followed_id: int | None = typer.Option(
        None,
        "--followed-id",
        help=t("cli_acquisition.search.followed_id_help"),
    ),
) -> None:
    """Run the search pass — state availability for pending wanted items.

    While a supervisor's lease is live the pass is asked through the queue and followed instead
    (:mod:`personalscraper.commands.acquisition_queue`); ``--dry-run`` always runs here.
    """
    config = ctx.obj.config
    assert config is not None  # guaranteed by callback
    console = state["console"]

    if not dry_run and acquisition_queue.supervised(config, console):
        acquisition_queue.queue_pass(config, console, JobKind.SEARCH, followed_id=followed_id, limit=limit)
        return

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
                msg = t("cli_acquisition.search.no_context")
                console.print("[red]" + msg + "[/red]")
                raise typer.Exit(1)
            if acquire.store is None:
                msg = t("cli_acquisition.search.no_store")
                console.print("[red]" + msg + "[/red]")
                raise typer.Exit(1)

            service = _build_search_service(acquire, config, app_context.event_bus)

            if dry_run:
                _run_dry(acquire, config, console, service, limit=limit, followed_id=followed_id)
            else:
                # Reconcile before searching: an item already in the médiathèque
                # closes ``done`` instead of costing a tracker query.
                reconcile = _reconcile_before_search(acquire, app_context.event_bus, console)

                summary = service.run_search(limit=limit, followed_id=followed_id)
                counts = t(
                    "cli_acquisition.search.complete_counts",
                    available=summary.available,
                    waiting=summary.waiting,
                    unverified=summary.unverified,
                    abandoned=summary.abandoned,
                    absorbed=summary.absorbed,
                    skipped=summary.skipped,
                )
                console.print("[green]" + t("cli_acquisition.search.complete_label") + "[/green] " + counts)
                # §5 « résultat chiffré »: persist the run's numbers on its
                # pipeline_run row (self-owned for cron/CLI; the web runner's row
                # when spawned by a web-triggered search).
                run_rec.record_counts(search_counts(summary, reconcile))
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


# ── Service builder ──────────────────────────────────────────────────────────────


def _build_search_service(
    acquire: AcquireContext,
    config: Config,
    event_bus: EventBus,
) -> AcquisitionService:
    """Build orchestrator + service inline for the search pass.

    The builder moved to :func:`personalscraper.acquire.build_search_service` so the supervisor's worker
    builds the same service; this keeps the command's own name for it.

    Args:
        acquire: The live ``AcquireContext`` (store + tracker_registry).
        config: Typed JSON5 configuration.
        event_bus: In-process event bus.

    Returns:
        A ready ``AcquisitionService`` wired for the search pass.
    """
    from personalscraper.acquire import build_search_service  # noqa: PLC0415

    return build_search_service(acquire, config, event_bus)


# ── Dry-run ──────────────────────────────────────────────────────────────────────


def _run_dry(
    acquire: AcquireContext,
    config: Config,
    console: Console,
    service: AcquisitionService,
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
        msg = t("cli_acquisition.search.dry_run_no_store")
        console.print("[yellow]" + msg + "[/yellow]")
        return

    now = int(time.time())

    # Build the queue exactly like run_search (pending + stale-searching,
    # de-duplicated, scoped, pause-gated, capped).  _build_queue is the shared private
    # helper both passes use — reusing it is what makes the preview faithful (a paused
    # follow's rows are not listed: the real pass would not search them); a
    # re-implementation here would be free to drift from the real pass.
    pass_queue = service._build_queue(
        store.wanted.list_pending(),
        now=now,
        limit=limit,
        followed_id=followed_id,
    )
    queue = pass_queue.items

    if not queue:
        msg = t("cli_acquisition.search.dry_run_empty")
        console.print("[yellow]" + msg + "[/yellow]")
        return

    global_cadence = cadence_from_config(config.acquire.cadence)
    # The queue carries the follow map it was gated with; _cadence_for is a private
    # read-only helper — same faithfulness justification as _build_queue above.
    follow_map = pass_queue.follow_map

    would_search: list[str] = []
    would_skip: list[str] = []
    would_abandon: list[str] = []

    for item in queue:
        cadence = service._cadence_for(item, follow_map, global_cadence)
        label = f"{item.media_ref} ({item.kind})"
        if is_past_cutoff(cadence, now=now, enqueued_at=item.enqueued_at):
            would_abandon.append(label)
        elif not is_due_by_cadence(cadence, now=now, enqueued_at=item.enqueued_at, last_search_at=item.last_search_at):
            would_skip.append(label)
        else:
            would_search.append(label)

    console.print(
        "\n[bold]"
        + t("cli_acquisition.search.dry_run_title")
        + "[/bold] "
        + t("cli_acquisition.search.dry_run_queue", items=len(queue))
    )
    console.print("  [green]" + t("cli_acquisition.search.dry_run_would_search") + "[/green] " + str(len(would_search)))
    for label in would_search:
        console.print("    • " + label)
    if would_skip:
        console.print("  [yellow]" + t("cli_acquisition.search.dry_run_skipped") + "[/yellow] " + str(len(would_skip)))
        for label in would_skip:
            console.print("    • " + label)
    if would_abandon:
        console.print(
            "  [red]" + t("cli_acquisition.search.dry_run_would_abandon") + "[/red] " + str(len(would_abandon))
        )
        for label in would_abandon:
            console.print("    • " + label)

    console.print("\n[dim]" + t("cli_acquisition.search.dry_run_complete") + "[/dim]")
