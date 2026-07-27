"""CLI command group: ``personalscraper seed`` — manual seed-pure tagger (O1).

Sub-commands:
- ``seed mark <info_hash>``   — apply the ``seed-pure`` tag to a torrent.
- ``seed unmark <info_hash>`` — remove the ``seed-pure`` tag from a torrent.
- ``seed list``               — list all completed torrents tagged ``seed-pure``.

Registered as a Typer sub-group (``seed_app = typer.Typer(...)`` mounted via
``_root_app.add_typer``). Sub-commands use ``@seed_app.command("name")``
(NOT ``@command_with_telemetry`` which is root-app-only).
Uses ``@handle_cli_errors``, ``per_step_boundary``,
``build_torrent_client=True`` (all three sub-commands touch the torrent client;
the guard ``torrent_client is not None`` is checked at command entry and exits 1
with a clear message otherwise).

Import direction: commands/ imports core/, api/torrent/, cli_app, cli_helpers only.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from personalscraper import cli_helpers
from personalscraper.cli_app import app as _root_app
from personalscraper.cli_helpers import handle_cli_errors, per_step_boundary
from personalscraper.core.tags import SEED_PURE
from personalscraper.logger import get_logger

log = get_logger("cli.seed")

# Typer sub-group for the ``seed`` command.
seed_app = typer.Typer(help="Tag torrents as seed-only (seed-pure) or inspect the list.")

console = Console()


@seed_app.command("mark")
@handle_cli_errors
def seed_mark(
    ctx: typer.Context,
    info_hash: str = typer.Argument(..., help="Lowercase-hex info hash of the torrent to tag."),
) -> None:
    """Apply the ``seed-pure`` tag to a torrent already in the client.

    Idempotent: tagging a torrent that already carries ``seed-pure`` is a
    no-op at the client level.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        info_hash: Lowercase-hex info hash of the torrent to tag.

    Raises:
        typer.Exit: Exit code 1 when no torrent client is configured.
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_mark_no_client", info_hash=info_hash)
            console.print("[red]Error:[/red] No torrent client configured. Check config/torrent.json5.")
            raise typer.Exit(code=1)
        app_context.torrent_client.add_tags(info_hash, [SEED_PURE])
        log.info("seed_marked", info_hash=info_hash, tag=SEED_PURE)
        console.print(f"[green]Marked[/green] {info_hash} as [bold]{SEED_PURE}[/bold].")


@seed_app.command("unmark")
@handle_cli_errors
def seed_unmark(
    ctx: typer.Context,
    info_hash: str = typer.Argument(..., help="Lowercase-hex info hash of the torrent to untag."),
) -> None:
    """Remove the ``seed-pure`` tag from a torrent in the client.

    Idempotent: removing the tag from a torrent that does not carry it is a
    no-op at the client level.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.
        info_hash: Lowercase-hex info hash of the torrent to untag.

    Raises:
        typer.Exit: Exit code 1 when no torrent client is configured.
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_unmark_no_client", info_hash=info_hash)
            console.print("[red]Error:[/red] No torrent client configured. Check config/torrent.json5.")
            raise typer.Exit(code=1)
        app_context.torrent_client.remove_tags(info_hash, [SEED_PURE])
        log.info("seed_unmarked", info_hash=info_hash, tag=SEED_PURE)
        console.print(f"[green]Unmarked[/green] {info_hash} — [bold]{SEED_PURE}[/bold] tag removed.")


@seed_app.command("list")
@handle_cli_errors
def seed_list(ctx: typer.Context) -> None:
    """List all completed torrents currently tagged ``seed-pure``.

    Queries the torrent client for completed torrents and filters those
    whose ``tags`` list contains ``SEED_PURE``. Output is a Rich table
    with columns: Hash, Name, Tags, State.

    Args:
        ctx: Typer context carrying the loaded ``Config`` in ``ctx.obj``.

    Raises:
        typer.Exit: Exit code 1 when no torrent client is configured.
    """
    config = ctx.obj.config
    settings = cli_helpers.get_settings()
    with per_step_boundary(config, settings, build_torrent_client=True) as app_context:
        if app_context.torrent_client is None:
            log.error("seed_list_no_client")
            console.print("[red]Error:[/red] No torrent client configured. Check config/torrent.json5.")
            raise typer.Exit(code=1)
        torrents = app_context.torrent_client.get_completed()
        seed_pure_torrents = [t for t in torrents if SEED_PURE in (getattr(t, "tags", None) or [])]
        log.info("seed_list", total=len(torrents), seed_pure=len(seed_pure_torrents))
        if not seed_pure_torrents:
            console.print(f"No completed torrents tagged [bold]{SEED_PURE}[/bold].")
            return
        table = Table(title=f"Torrents tagged '{SEED_PURE}'", show_lines=True)
        table.add_column("Hash", style="dim", no_wrap=True)
        table.add_column("Name")
        table.add_column("Tags")
        table.add_column("State")
        for t in seed_pure_torrents:
            table.add_row(
                t.hash,
                t.name,
                ", ".join(t.tags),
                t.state,
            )
        console.print(table)


# Register the seed sub-group on the root Typer app (import side-effect, called by cli.py).
_root_app.add_typer(seed_app, name="seed")

__all__ = ["seed_app", "seed_list", "seed_mark", "seed_unmark"]
