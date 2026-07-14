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

from personalscraper import cli as cli_compat
from personalscraper.cli_app import command_with_telemetry
from personalscraper.cli_helpers import (
    handle_cli_errors,
    per_step_boundary,
)
from personalscraper.cli_state import state
from personalscraper.commands._acquire_run_row import acquisition_run_row
from personalscraper.logger import get_logger
from personalscraper.subscribers.redis_stream import build_redis_publisher

if TYPE_CHECKING:
    from personalscraper.acquire.context import AcquireContext

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
    settings = cli_compat.get_settings()

    with (
        acquisition_run_row(config, "grab") as run_rec,
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
                    }
                )
        finally:
            if redis_publisher is not None:
                redis_publisher.close()


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
    from personalscraper.acquire._dedup import dedup  # noqa: PLC0415
    from personalscraper.acquire._filters import apply_hard_filters  # noqa: PLC0415
    from personalscraper.acquire.desired import QualityProfile  # noqa: PLC0415
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

    from personalscraper.acquire.orchestrator import build_search_query  # noqa: PLC0415
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

        profile = QualityProfile()
        filtered = apply_hard_filters(results, profile)
        deduped = dedup(filtered)
        console.print(f"  After filter+dedup: {len(deduped)} candidates")
        if deduped:
            top = deduped[0]
            console.print(
                f"  [green]Top:[/green] [{top.provider}] {top.title} ({top.seeders} seeders, {top.resolution})"
            )
        else:
            console.print("  [yellow]All filtered.[/yellow]")
