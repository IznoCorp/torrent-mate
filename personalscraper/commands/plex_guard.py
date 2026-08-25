"""Typer command for the Plex match coherence guard."""

from __future__ import annotations

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, boundary, handle_cli_errors
from personalscraper.cli_state import state


@app.command()
@handle_cli_errors
@boundary(needs="db-read", staging=False)
def plex_guard(
    context: typer.Context,
    repair: bool = typer.Option(False, "--repair", help="Apply the match over the Plex API (default: dry-run)"),
    item_id: list[int] | None = typer.Option(
        None,
        "--item-id",
        help="Check only this item by DB id (repeatable), bypassing the sweep.",
    ),
    *,
    bundle: CommandContext,
) -> None:
    """Check that Plex matched every dispatched item to the pipeline's ids.

    The default run is READ-ONLY: it compares, for each dispatched movie/show,
    the provider guids Plex resolved against the canonical ids in the indexer
    (tmdb for movies, tvdb for shows) and reports every misalignment — dry-run
    writes nothing, not even to the local data dir. With ``--repair``, a
    misaligned item is re-matched over the Plex API (``matches`` → ``match``);
    the local filesystem and the indexer DB are never written.

    Fail-soft: Plex down, wrong token, or a folder Plex has not scanned yet
    degrades to a per-item report line. The guard never fails the run. A
    dry-run writes NOTHING (report included — the repair mode is what
    persists ``library_plex_guard.json``); it does issue read-only requests,
    including one match-resolution probe per misaligned item, so the report
    can tell « the id resolves to nothing » apart from « Plex was down ».

    Examples:
        personalscraper plex-guard
        personalscraper plex-guard --item-id 1600
        personalscraper plex-guard --repair --item-id 1600
    """
    from datetime import datetime, timezone  # noqa: PLC0415

    from personalscraper.api.plex import PlexClient  # noqa: PLC0415
    from personalscraper.io_utils import write_json  # noqa: PLC0415
    from personalscraper.maintenance.plex_guard import STATE_MISALIGNED, run_plex_guard  # noqa: PLC0415

    console = state["console"]

    if bundle.indexer_conn is None:
        console.print("[red]Indexer DB not found; run `library-index` first.[/red]")
        raise typer.Exit(1)

    settings = bundle.settings
    if not settings.plex_token:
        console.print("[yellow]No Plex token configured — nothing to compare against.[/yellow]")
        raise typer.Exit(1)

    client = PlexClient(settings.plex_url, settings.plex_token)
    mode = "[bold yellow]DRY-RUN[/bold yellow]" if not repair else "[bold green]REPAIR[/bold green]"
    console.print(f"[bold]Plex match coherence ({mode})...[/bold]")

    result = run_plex_guard(
        client=client,
        connection=bundle.indexer_conn,
        repair=repair,
        item_ids=item_id,
        now=datetime.now(timezone.utc).isoformat(),
    )

    for finding in result.findings:
        console.print(
            f"  [{_STATE_COLORS.get(finding.state, 'white')}]{finding.state}[/] "
            f"item {finding.item_id} « {finding.title} »"
            f"{f' ({finding.canonical_provider}-{finding.canonical_id})' if finding.canonical_id else ''}"
            f"{f' → {finding.rating_key}' if finding.rating_key else ''}"
            f"{f' [Plex: « {finding.plex_title} »]' if finding.plex_title else ''}"
            f"{' [title suspect]' if finding.title_suspect else ''}"
            f"{f' [path: {finding.dispatch_path}]' if finding.dispatch_path and finding.state == 'not_found' else ''}"
        )

    if repair:
        action_count = result.repaired_count
        action_label = "[yellow]Repaired:[/yellow]"
    else:
        action_count = sum(1 for f in result.findings if f.state == STATE_MISALIGNED)
        action_label = "[yellow]Misaligned (would repair):[/yellow]"

    console.print(
        f"[green]Aligned:[/green] {result.aligned_count}  "
        f"{action_label} {action_count}  "
        f"[red]Errors/skipped:[/red] {result.skipped_count - (0 if repair else action_count)}"
    )

    # A repair run persists the result (dry-run writes nothing, report
    # included — the CLI docstring promises it, the behaviour keeps it).
    if repair:
        write_json(result, bundle.config.paths.data_dir / "library_plex_guard.json")


#: Console colour per finding state — aligned is green, actionable states are
#: yellow, errors red. A state missing here renders in the default colour
#: rather than crashing the report.
_STATE_COLORS = {
    "aligned": "green",
    "misaligned": "yellow",
    "repaired": "green",
    "repair_failed": "red",
    "ambiguous": "yellow",
    "no_candidate": "yellow",
    "no_ids": "yellow",
    "not_found": "yellow",
    "plex_error": "red",
}
