"""CLI command: ``personalscraper grab`` — batch acquisition run (RP5b).

Drives ``AcquisitionService.run()`` over the pending wanted queue.
``--dry-run`` searches + filters + ranks but never fetches or adds.
``--limit N`` caps the number of items attempted in one run.

Registered against the shared Typer ``app`` (imported side-effect in cli.py).
"""

from __future__ import annotations

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

log = get_logger("cli.grab")


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
        try:
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
                reconcile = _reconcile_before_run(acquire, console)

                summary = grab_core.service.run(limit=limit, followed_id=followed_id)
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
                    }
                )
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


def _reconcile_before_run(acquire: AcquireContext, console: Console) -> "ReconcileSummary":
    """Run the B.3 reconciliation pass ahead of a real grab run (fail-soft).

    Gathers the torrent client's known info-hashes once (``None`` on any
    client error — the vanished-torrent requeue is skipped rather than firing
    blind) and sweeps the grabbed rows via
    :func:`personalscraper.acquire.reconcile.reconcile_wanted`.

    Args:
        acquire: The live :class:`AcquireContext` (store + ownership + client).
        console: Rich console for the operator summary line.

    Returns:
        The pass summary (zeroes when the store is unavailable or the sweep
        failed — a reconciliation problem must never abort the grab run).
    """
    from personalscraper.acquire.reconcile import ReconcileSummary, reconcile_wanted  # noqa: PLC0415

    store = acquire.store
    if store is None:
        return ReconcileSummary()

    client_hashes: set[str] | None = None
    torrent_client = acquire.torrent_client
    if torrent_client is not None:
        try:
            grabbed_hashes = {(w.grabbed_hash or "").lower() for w in store.wanted.list_grabbed()}
            grabbed_hashes.discard("")
            client_hashes = {t.hash.lower() for t in torrent_client.get_by_hashes(grabbed_hashes)}
        except Exception as exc:  # noqa: BLE001 — fail-soft: skip the requeue half
            log.warning("cli.grab.reconcile_client_unavailable", error=str(exc))
            client_hashes = None

    try:
        summary = reconcile_wanted(store, acquire.ownership, client_hashes)
    except Exception as exc:  # noqa: BLE001 — reconciliation must never abort the grab
        log.warning("cli.grab.reconcile_failed", error=str(exc))
        return ReconcileSummary()
    if summary.closed_owned or summary.requeued_missing:
        console.print(
            f"[cyan]Réconciliation:[/cyan] {summary.closed_owned} clos (en médiathèque), "
            f"{summary.requeued_missing} remis en file (torrent disparu)."
        )
    return summary


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
        media_type = MediaType.TV if item.kind == "episode" else MediaType.MOVIE
        # Follow D3: same title resolution as the real grab (see build_search_query)
        # so the preview reflects the actual query the trackers receive.
        title = None
        if item.followed_id is not None:
            row = store.follow.get(item.followed_id)
            title = row.title if row is not None else None
        query = build_search_query(item, title)
        try:
            outcome = registry.search_candidates(query, media_type, None)
        except CircuitOpenError:
            # A dead tracker's OPEN circuit must not crash the preview (the real
            # grab already catches this in the orchestrator).
            console.print("  [yellow]Tracker circuit open — skipped this item.[/yellow]")
            continue
        console.print(
            f"  Search: {len(outcome.results)} results "
            f"({outcome.trackers_queried} queried, {outcome.trackers_errored} errored)"
        )
        if not outcome.results:
            console.print("  [yellow]No results.[/yellow]")
            continue

        # Episode-exactness: mirror the real grab so the preview's Top is the
        # actual episode, not a fuzzy same-show match.
        results = outcome.results
        if item.kind == "episode" and item.season is not None and item.episode is not None:
            from personalscraper.acquire.orchestrator import filter_to_episode  # noqa: PLC0415

            results = filter_to_episode(results, item.season, item.episode)
            if not results:
                console.print("  [yellow]No result matches the exact episode.[/yellow]")
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
