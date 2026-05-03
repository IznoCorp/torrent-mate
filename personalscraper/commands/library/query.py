"""Query Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors


@app.command("library-status")
@handle_cli_errors
def library_status(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Show the latest completed indexer scan run summary.

    Queries the indexer database for the most recently completed scan run
    and prints a one-line summary.  Prints "no scans yet" when the database
    has no completed scan runs.

    Examples:
        personalscraper library-status
        personalscraper library-status --config /path/to/config.json5
    """
    from personalscraper.indexer.cli import library_status_command  # noqa: PLC0415

    # Prefer explicit --config passed to this sub-command; fall back to the
    # global --config stored on the app context.
    effective_config: Path | None = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_status_command(effective_config)
    raise typer.Exit(rc)


@app.command("library-search")
@handle_cli_errors
def library_search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Query string, e.g. 'year:2024 disk:Disk1 -nfo:valid'"),
    limit: int = typer.Option(50, "--limit", help="Maximum number of results to return"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Search indexed media items with the flex-attr query language.

    Field syntax: ``field:value``, ``-field:value`` (negation), ``year:>=2020``,
    ``title:"Exact Title"``.  Unknown fields exit 2.

    Examples:
        personalscraper library-search "year:2024 disk:Disk1 -nfo:valid"
        personalscraper library-search "kind:show codec:hevc -trailer"
        personalscraper library-search 'title:"Lost Highway"'
    """
    from personalscraper.indexer.cli import library_search_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_search_command(query, limit=limit, config_path=effective_config)
    if rc != 0:
        raise typer.Exit(rc)


@app.command("library-show")
@handle_cli_errors
def library_show(
    ctx: typer.Context,
    item_id: int = typer.Argument(..., help="media_item.id to display"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Pretty-print all stored data for a single media item.

    Prints media_item fields, season/episode rows, media_file rows with streams,
    item_attribute rows, and deleted_item history.  Exits 2 for unknown ids.

    Examples:
        personalscraper library-show 42
    """
    from personalscraper.indexer.cli import library_show_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_show_command(item_id, config_path=effective_config)
    if rc != 0:
        raise typer.Exit(rc)
