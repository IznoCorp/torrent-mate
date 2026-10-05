"""Typer command for the Plex match coherence guard."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, boundary, handle_cli_errors
from personalscraper.cli_state import state
from personalscraper.i18n import t

if TYPE_CHECKING:
    from personalscraper.maintenance.plex_guard import PlexGuardFinding


@app.command(help=t("cli_acquisition.plex_guard.help"))
@handle_cli_errors
@boundary(needs="db-read", staging=False)
def plex_guard(
    context: typer.Context,
    repair: bool = typer.Option(False, "--repair", help=t("cli_acquisition.plex_guard.repair_help")),
    item_id: list[int] | None = typer.Option(
        None,
        "--item-id",
        help=t("cli_acquisition.plex_guard.item_id_help"),
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
        console.print("[red]" + t("cli_acquisition.plex_guard.no_indexer_db") + "[/red]")
        raise typer.Exit(1)

    settings = bundle.settings
    if not settings.plex_token:
        console.print("[yellow]" + t("cli_acquisition.plex_guard.no_token") + "[/yellow]")
        raise typer.Exit(1)

    client = PlexClient(settings.plex_url, settings.plex_token)
    mode = (
        f"[bold yellow]{t('cli_acquisition.plex_guard.mode_dry_run')}[/bold yellow]"
        if not repair
        else f"[bold green]{t('cli_acquisition.plex_guard.mode_repair')}[/bold green]"
    )
    console.print("[bold]" + t("cli_acquisition.plex_guard.heading", mode=mode) + "[/bold]")

    result = run_plex_guard(
        client=client,
        connection=bundle.indexer_conn,
        repair=repair,
        item_ids=item_id,
        now=datetime.now(timezone.utc).isoformat(),
    )

    for finding in result.findings:
        console.print(_finding_line(finding))

    if repair:
        action_count = result.repaired_count
        action_label = f"[yellow]{t('cli_acquisition.plex_guard.repaired_label')}[/yellow]"
    else:
        action_count = sum(1 for f in result.findings if f.state == STATE_MISALIGNED)
        action_label = f"[yellow]{t('cli_acquisition.plex_guard.misaligned_label')}[/yellow]"

    errors_skipped = result.skipped_count - (0 if repair else action_count)
    console.print(
        "[green]"
        + t("cli_acquisition.plex_guard.aligned_label")
        + "[/green] "
        + str(result.aligned_count)
        + "  "
        + str(action_label)
        + " "
        + str(action_count)
        + "  [red]"
        + t("cli_acquisition.plex_guard.errors_label")
        + "[/red] "
        + str(errors_skipped)
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


def _finding_line(finding: PlexGuardFinding) -> str:
    """Render one finding as its console line (Rich markup stays here, the words come from the catalogue).

    Args:
        finding: A ``PlexGuardFinding`` of the run's result.

    Returns:
        The line, state colour included, ready for ``console.print``.
    """
    colour = _STATE_COLORS.get(finding.state, "white")
    parts = [
        f"  [{colour}]{finding.state}[/] ",
        t("cli_acquisition.plex_guard.finding_item", item_id=finding.item_id, title=finding.title),
    ]
    if finding.canonical_id:
        # Layout only (no words): never translated.
        parts.append(f" ({finding.canonical_provider}-{finding.canonical_id})")
    if finding.rating_key:
        parts.append(f" → {finding.rating_key}")
    if finding.plex_title:
        parts.append(t("cli_acquisition.plex_guard.finding_plex_title", plex_title=finding.plex_title))
    if finding.title_suspect:
        parts.append(t("cli_acquisition.plex_guard.finding_title_suspect"))
    if finding.dispatch_path and finding.state == "not_found":
        parts.append(t("cli_acquisition.plex_guard.finding_path", path=finding.dispatch_path))
    return "".join(parts)
