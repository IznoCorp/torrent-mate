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
from personalscraper.logger import get_logger

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
) -> None:
    """Run the grab loop — search trackers and add top-ranked torrents."""
    config = ctx.obj.config
    assert config is not None  # guaranteed by callback
    console = state["console"]
    settings = cli_compat.get_settings()

    with per_step_boundary(config, settings, build_torrent_client=not dry_run) as app_context:
        acquire = app_context.acquire
        if acquire is None:
            console.print("[red]AcquireContext not available.[/red]")
            raise typer.Exit(1)

        if dry_run:
            _run_dry(acquire, console, limit=limit)
        else:
            grab_core = acquire.grab
            if grab_core is None:
                console.print(
                    "[red]No torrent client configured — cannot run grab. Check config or use --dry-run.[/red]"
                )
                raise typer.Exit(1)
            summary = grab_core.service.run(limit=limit)
            console.print(
                f"[green]Grab complete:[/green] "
                f"{summary.grabbed} grabbed, "
                f"{summary.retried} retried, "
                f"{summary.abandoned} abandoned, "
                f"{summary.skipped} skipped."
            )


def _run_dry(
    acquire: AcquireContext,
    console: Console,
    *,
    limit: int | None,
) -> None:
    """Dry-run: search + filter + dedup + rank, print top candidates. No add.

    Args:
        acquire: :class:`~personalscraper.acquire.context.AcquireContext`.
        console: Rich Console for output.
        limit: Max items to inspect.
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
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        console.print("[yellow]No pending wanted items.[/yellow]")
        return

    registry = acquire.tracker_registry
    for item in pending:
        console.print(f"\n[bold]Item:[/bold] {item.media_ref} ({item.kind})")
        media_type = MediaType.TV if item.kind == "episode" else MediaType.MOVIE
        query = str(item.media_ref.tvdb_id or item.media_ref.tmdb_id or "")
        outcome = registry.search_candidates(query, media_type, None)
        console.print(
            f"  Search: {len(outcome.results)} results "
            f"({outcome.trackers_queried} queried, {outcome.trackers_errored} errored)"
        )
        if not outcome.results:
            console.print("  [yellow]No results.[/yellow]")
            continue

        profile = QualityProfile()
        filtered = apply_hard_filters(outcome.results, profile)
        deduped = dedup(filtered)
        console.print(f"  After filter+dedup: {len(deduped)} candidates")
        if deduped:
            top = deduped[0]
            console.print(
                f"  [green]Top:[/green] [{top.provider}] {top.title} ({top.seeders} seeders, {top.resolution})"
            )
        else:
            console.print("  [yellow]All filtered.[/yellow]")
