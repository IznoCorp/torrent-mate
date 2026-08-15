"""CLI command: ``personalscraper grab`` — batch acquisition run (RP5b).

Drives ``AcquisitionService.run()`` over the pending wanted queue.
``--dry-run`` searches + filters + ranks but never fetches or adds.
``--limit N`` caps the number of items attempted in one run.

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
    from personalscraper.api.torrent._base import TorrentItem
    from personalscraper.api.tracker._base import TrackerResult
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus
    from personalscraper.subscribers.acquire import AcquisitionTelegramSubscriber

log = get_logger("cli.grab")


def _build_acq_telegram_subscriber(
    config: "Config",
    settings: "Settings",
    event_bus: "EventBus",
) -> "AcquisitionTelegramSubscriber | None":
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


@command_with_telemetry("grab")
@handle_cli_errors
def grab(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Search, filter, rank — print top candidate. No fetch or add.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        "-n",
        help="Maximum number of wanted items to process. Default: all pending.",
    ),
    followed_id: int | None = typer.Option(
        None,
        "--followed-id",
        help="Restrict the run to one followed series' pending items (OBJ3 manual trigger).",
    ),
) -> None:
    """Run the grab loop — search trackers and add top-ranked torrents."""
    config = ctx.obj.config
    assert config is not None  # guaranteed by callback
    console = state["console"]
    settings = cli_helpers.get_settings()

    with (
        cli_run_row(config, "grab") as run_rec,
        per_step_boundary(config, settings, build_torrent_client=not dry_run) as app_context,
    ):
        redis_publisher = build_redis_publisher(app_context.event_bus, config.web)
        # D8 — the reconcile pass below emits DownloadCompleted; without this
        # subscriber the event had no Telegram consumer on the grab path (the
        # pipeline command wires it, but never calls reconcile_wanted). Built
        # INSIDE the try (pipeline.py pattern) so a construction failure still
        # reaches the finally and closes the redis publisher.
        acq_telegram_subscriber: "AcquisitionTelegramSubscriber | None" = None
        try:
            acq_telegram_subscriber = _build_acq_telegram_subscriber(config, settings, app_context.event_bus)
            acquire = app_context.acquire
            if acquire is None:
                console.print("[red]AcquireContext not available.[/red]")
                raise typer.Exit(1)

            if dry_run:
                _run_dry(acquire, console, limit=limit, followed_id=followed_id)
            else:
                grab_core = acquire.grab
                if grab_core is None:
                    console.print(
                        "[red]No torrent client configured — cannot run grab. Check config or use --dry-run.[/red]"
                    )
                    raise typer.Exit(1)

                # P0-B.3 — reconcile grabbed rows BEFORE searching: rows whose
                # work the library owns close ``done``; rows whose torrent
                # vanished from the client (and are unowned) requeue pending
                # and re-enter this very run's queue.
                reconcile = _reconcile_before_run(acquire, app_context.event_bus, console)

                # reswitch #342 — AFTER reconcile (review ordering note): reconcile
                # closes library-owned rows to ``done`` first, so reswitch only
                # acts on rows that are genuinely still downloading. For each
                # dead-stalled grab (dead swarm / broken / stuck past the deadline)
                # the dead torrent is removed and the row requeued with the failed
                # hash remembered, so the next search+grab picks a DIFFERENT
                # release. A vanished torrent is left to reconcile.
                _reswitch_before_run(acquire, app_context.event_bus, console)

                summary = grab_core.service.run(limit=limit, followed_id=followed_id, run_uid=run_rec.run_uid)
                console.print(
                    f"[green]Grab complete:[/green] "
                    f"{summary.grabbed} grabbed, "
                    f"{summary.retried} retried, "
                    f"{summary.abandoned} abandoned, "
                    f"{summary.skipped} skipped."
                )
                # §5 « résultat chiffré »: persist the run's numbers on its
                # pipeline_run row (self-owned for cron/CLI; the web runner's
                # row when spawned by POST /followed/{id}/search).
                run_rec.record_counts(
                    {
                        "grabbed": summary.grabbed,
                        "retried": summary.retried,
                        "abandoned": summary.abandoned,
                        "skipped": summary.skipped,
                        "closed_owned": reconcile.closed_owned,
                        "requeued_missing": reconcile.requeued_missing,
                        # A grab recovered out of the add→confirm crash window is
                        # a real acquisition this run is responsible for. Without
                        # it on the row, the recovery was computed, logged and
                        # then dropped — invisible to the operator (§5 « résultat
                        # chiffré »: a run states its numbers, all of them).
                        "confirmed_grabbed": reconcile.confirmed_grabbed,
                    }
                )
        finally:
            if acq_telegram_subscriber is not None:
                acq_telegram_subscriber.close()
            if redis_publisher is not None:
                redis_publisher.close()


def _reconcile_before_run(acquire: AcquireContext, event_bus: "EventBus", console: Console) -> "ReconcileSummary":
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

    Returns:
        The pass summary (zeroes when the store is unavailable or the sweep
        failed — a reconciliation problem must never abort the grab run).
    """
    from personalscraper.acquire.reconcile import ReconcileSummary, reconcile_wanted  # noqa: PLC0415

    store = acquire.store
    if store is None:
        return ReconcileSummary()

    client_items: "dict[str, TorrentItem] | None" = None
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
            client_items = {t.hash.lower(): t for t in torrent_client.get_by_hashes(in_flight)}
        except Exception as exc:  # noqa: BLE001 — fail-soft: skip the requeue half
            log.warning("cli.grab.reconcile_client_unavailable", error=str(exc))
            client_items = None

    # D2 — a grab confirmed out of the add→confirm crash window never ran the
    # grab-time obligation writer; record it now, from the torrent's own tracker
    # tag. Absent authority (no store) → no recorder, the confirmation still runs.
    authority = acquire.delete_authority
    recorder = authority.record_grab_obligation if authority is not None else None
    ownership = acquire.ownership

    try:
        summary = reconcile_wanted(store, ownership, client_items, event_bus=event_bus, record_obligation=recorder)
    except Exception as exc:  # noqa: BLE001 — reconciliation must never abort the grab
        log.warning("cli.grab.reconcile_failed", error=str(exc))
        return ReconcileSummary()
    if summary.closed_owned or summary.requeued_missing or summary.confirmed_grabbed:
        console.print(
            f"[cyan]Réconciliation:[/cyan] {summary.closed_owned} clos (en médiathèque), "
            f"{summary.requeued_missing} remis en file (torrent disparu), "
            f"{summary.confirmed_grabbed} confirmés (récupérés après interruption)."
        )
    return summary


def _reswitch_before_run(acquire: AcquireContext, event_bus: "EventBus", console: Console) -> None:
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
    """
    from personalscraper.acquire._reswitch import reswitch_stalled

    store = acquire.store
    torrent_client = acquire.torrent_client
    if store is None or torrent_client is None:
        return
    try:
        summary = reswitch_stalled(store, torrent_client, time.time(), event_bus=event_bus)
    except Exception as exc:  # noqa: BLE001 — reswitch must never abort the grab
        log.warning("cli.grab.reswitch_failed", error=str(exc))
        return
    if summary.reswitched:
        console.print(
            f"[cyan]Bascule:[/cyan] {summary.reswitched} release(s) bloquée(s) remplacée(s) "
            f"(sur {summary.checked} en cours)."
        )


def _run_dry(
    acquire: AcquireContext,
    console: Console,
    *,
    limit: int | None,
    followed_id: int | None = None,
) -> None:
    """Dry-run: search + filter + dedup + rank, print top candidates. No add.

    Args:
        acquire: :class:`~personalscraper.acquire.context.AcquireContext`.
        console: Rich Console for output.
        limit: Max items to inspect.
        followed_id: When set, restrict the dry-run to one followed series'
            pending items (mirrors the real run's OBJ3 per-series scoping).
    """
    from personalscraper.api._contracts import MediaType  # noqa: PLC0415

    store = acquire.store
    if store is None:
        console.print("[yellow]No acquire store — nothing to dry-run.[/yellow]")
        return

    pending = store.wanted.list_pending()
    if followed_id is not None:
        pending = [item for item in pending if item.followed_id == followed_id]
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        console.print("[yellow]No pending wanted items.[/yellow]")
        return

    from personalscraper.acquire.orchestrator import build_search_query, rank_candidates  # noqa: PLC0415
    from personalscraper.core._contracts import CircuitOpenError  # noqa: PLC0415

    registry = acquire.tracker_registry
    for item in pending:
        console.print(f"\n[bold]Item:[/bold] {item.media_ref} ({item.kind})")
        # A `season` row is TV too — it was classified as MOVIE here while the
        # orchestrator (orchestrator.py) says `in ("episode", "season")`. The
        # preview therefore hit the movie endpoint AND, once the year stopped
        # being appended to TV queries, kept appending it to season queries:
        # exactly the « … S01 2025 » → 0 result that stranded Pan Am 103.
        media_type = MediaType.TV if item.kind in ("episode", "season") else MediaType.MOVIE
        # Follow D3: same title + year resolution as the real grab (see
        # build_search_query) so the preview reflects the ACTUAL query the
        # trackers receive — for a movie that means « {title} {year} » (#28,
        # review F4: a preview that ranks a different film than the grab is a lie).
        title = None
        year: int | None = None
        original_title = None
        if item.followed_id is not None:
            row = store.follow.get(item.followed_id)
            if row is not None:
                title = row.title
                year = row.year
                original_title = row.original_title
        # #435 — mirror the real grab's original-title retry: a fruitless
        # display-title query replays once in the original language, so the
        # preview reflects the SAME candidates the grab would rank (review F4:
        # a preview that diverges from the run is a lie).
        queries = [build_search_query(item, title, year)]
        if original_title and original_title != title:
            queries.append(build_search_query(item, original_title, year))
        results: "list[TrackerResult] | None" = None
        circuit_open = False
        for attempt_no, attempt_query in enumerate(queries):
            try:
                outcome = registry.search_candidates(attempt_query, media_type, year)
            except CircuitOpenError:
                # A dead tracker's OPEN circuit must not crash the preview (the
                # real grab already catches this in the orchestrator).
                console.print("  [yellow]Tracker circuit open — skipped this item.[/yellow]")
                circuit_open = True
                break
            label = "Search" if attempt_no == 0 else "Retry (original title)"
            console.print(
                f"  {label}: {len(outcome.results)} results "
                f"({outcome.trackers_queried} queried, {outcome.trackers_errored} errored)"
            )
            if not outcome.results:
                continue

            # Episode-exactness: mirror the real grab so the preview's Top is
            # the actual episode, not a fuzzy same-show match.
            narrowed = outcome.results
            if item.kind == "episode" and item.season is not None and item.episode is not None:
                from personalscraper.acquire.orchestrator import filter_to_episode  # noqa: PLC0415

                narrowed = filter_to_episode(narrowed, item.season, item.episode)
            elif item.kind == "movie" and title is not None:
                # #28 (review F4) — mirror the real grab's movie identity filter
                # so the preview's Top is the SAME film the grab would take, not
                # a higher-seeded « Wicker* » of a different year. Every known
                # title (#435): a release named in the original language must
                # survive here exactly as it does in the real grab.
                from personalscraper.acquire.orchestrator import filter_to_movie  # noqa: PLC0415

                narrowed = filter_to_movie(narrowed, [title, original_title], year)
            if narrowed:
                results = narrowed
                break
        if circuit_open:
            continue
        if not results:
            console.print("  [yellow]No result matches the wanted item (title/episode/year).[/yellow]")
            continue

        # Resolve the SAME effective profile the real grab uses (series
        # quality_profile_json overlaid with item criteria) and pass the
        # media_ref for TMDB-identity parity — otherwise the preview's Top can
        # diverge from the real run for a series with a custom profile
        # (exclude_3d=False, min_resolution, required_audio).
        from personalscraper.acquire.service import resolve_effective_profile  # noqa: PLC0415

        profile = resolve_effective_profile(store, item)
        # F4: run the SAME hard-filter → dedup → rank tail the real grab runs
        # (rank_candidates), with the SAME ranking source (config.ranking, held
        # by the registry). The old preview printed dedup[0] — the UNRANKED first
        # candidate — so the operator validated a decision the real run would
        # never make (a lower-seeder / wrong-variant release); the dry-run-first
        # rule needs the Top to be the actual ranked winner, rank[0].
        representatives, ranked = rank_candidates(results, profile, item.media_ref, registry.ranking)
        console.print(f"  After filter+dedup: {len(representatives)} candidates")
        if not representatives:
            console.print("  [yellow]All filtered.[/yellow]")
            continue
        if not ranked:
            # Survivors exist but none meets min_seeders — the real grab returns
            # no_seeders (retryable), so there is no candidate to act on today.
            console.print("  [yellow]No candidate meets the minimum seeders threshold.[/yellow]")
            continue
        top, _score = ranked[0]
        console.print(f"  [green]Top:[/green] [{top.provider}] {top.title} ({top.seeders} seeders, {top.resolution})")
