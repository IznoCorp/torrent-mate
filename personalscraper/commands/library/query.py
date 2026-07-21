"""Query Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, boundary, handle_cli_errors


@app.command("library-status")
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_status(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
    *,
    bundle: CommandContext,
) -> None:
    """Show the latest completed indexer scan run summary.

    Queries the indexer database for the most recently completed scan run
    and prints a one-line summary.  Prints "no scans yet" when the database
    has no completed scan runs.  Output format respects the global
    ``--format`` flag.

    Examples:
        personalscraper library-status
        personalscraper --format json library-status
        personalscraper library-status --config /path/to/config.json5
    """
    from personalscraper.cli_state import state  # noqa: PLC0415
    from personalscraper.indexer.cli import library_status_command  # noqa: PLC0415

    # Prefer explicit --config passed to this sub-command; fall back to the
    # global --config stored on the app context.
    effective_config: Path | None = config or (ctx.obj.config_override if ctx.obj else None)
    rc = library_status_command(
        effective_config,
        event_bus=bundle.event_bus,
        output_format=state["format"],
    )
    raise typer.Exit(rc)


@app.command("library-search")
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Query string, e.g. 'year:2024 disk:Disk1 -nfo:valid'"),
    limit: int = typer.Option(50, "--limit", help="Maximum number of results to return"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
    *,
    bundle: CommandContext,
) -> None:
    """Search indexed media items with the flex-attr query language.

    Field syntax: ``field:value``, ``-field:value`` (negation), ``year:>=2020``,
    ``title:"Exact Title"``.  Unknown fields exit 2.

    Examples:
        personalscraper library-search "year:2024 disk:Disk1 -nfo:valid"
        personalscraper library-search "kind:show codec:hevc -trailer"
        personalscraper library-search 'title:"Lost Highway"'
    """
    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.indexer.cli import library_search_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc, rows = library_search_command(query, limit=limit, config_path=effective_config, event_bus=bundle.event_bus)
    emit(
        {"rows": rows, "count": len(rows), "query": query, "limit": limit},
        rich_renderer=lambda: _print_search_table(rows),
    )
    if rc != 0:
        raise typer.Exit(rc)


def _print_search_table(rows: list[dict[str, object]]) -> None:
    """Render search results as a fixed-width table.

    Args:
        rows: List of row dicts with ``id``, ``title``, ``year``, ``kind``, ``nfo_status`` keys.
    """
    if not rows:
        typer.echo("(no results)")
        return
    typer.echo(f"{'ID':<8}{'TITLE':<40} {'YEAR':<6} {'NFO':<10}")
    for r in rows:
        year_str = str(r["year"]) if r["year"] is not None else ""
        nfo_str = str(r["nfo_status"]) or ""
        title = str(r["title"]) or ""
        typer.echo(f"{r['id']:<8}{title[:38]:<40} {year_str:<6} {nfo_str:<10}")


@app.command("library-show")
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_show(
    ctx: typer.Context,
    item_id: int = typer.Argument(..., help="media_item.id to display"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
    *,
    bundle: CommandContext,
) -> None:
    """Pretty-print all stored data for a single media item.

    Prints media_item fields, season/episode rows, media_file rows with streams,
    item_attribute rows, and deleted_item history.  Exits 2 for unknown ids.

    Examples:
        personalscraper library-show 42
    """
    from personalscraper.cli_helpers.output import emit  # noqa: PLC0415
    from personalscraper.indexer.cli import library_show_command  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    rc, payload = library_show_command(item_id, config_path=effective_config, event_bus=bundle.event_bus)
    emit(payload, rich_renderer=lambda: _print_show_sections(payload))
    if rc != 0:
        raise typer.Exit(rc)


def _print_show_sections(payload: dict[str, object]) -> None:
    """Render a single media item show as rich sections.

    Args:
        payload: The dict returned by :func:`~personalscraper.indexer.cli.library_show_command`.
    """
    from typing import cast  # noqa: PLC0415

    if "error" in payload:
        typer.echo(str(payload["error"]), err=True)
        return

    item = cast("dict[str, object]", payload.get("item", {}))
    item_id = payload.get("item_id", "?")
    typer.echo(f"=== media_item id={item_id} ===")
    for key, value in item.items():
        typer.echo(f"  {key}: {value}")

    seasons = cast("list[dict[str, object]]", payload.get("seasons", []))
    if seasons:
        typer.echo(f"\n=== seasons ({len(seasons)}) ===")
        for s in seasons:
            typer.echo(
                f"  season {s.get('number')}: episodes={s.get('episode_count')}, "
                f"has_poster={s.get('has_poster')}, nfo_count={s.get('episodes_with_nfo')}"
            )
            for ep in cast("list[dict[str, object]]", s.get("episodes", [])):
                typer.echo(f"    episode {ep.get('number')}: {ep.get('title')}")

    files = cast("list[dict[str, object]]", payload.get("files", []))
    if files:
        typer.echo(f"\n=== media_files ({len(files)}) ===")
        for f in files:
            typer.echo(
                f"  file id={f.get('id')} {f.get('rel_path')}/{f.get('filename')}"
                f" size={f.get('size_bytes')} mtime_ns={f.get('mtime_ns')}"
            )
            for st in cast("list[dict[str, object]]", f.get("streams", [])):
                typer.echo(
                    f"    stream idx={st.get('idx')} kind={st.get('kind')} "
                    f"codec={st.get('codec')} lang={st.get('lang')}"
                )

    attributes = cast("list[dict[str, object]]", payload.get("attributes", []))
    if attributes:
        typer.echo(f"\n=== item_attributes ({len(attributes)}) ===")
        for a in attributes:
            typer.echo(f"  {a.get('key')}: {a.get('value')}")

    deleted = cast("list[dict[str, object]]", payload.get("deleted_history", []))
    if deleted:
        typer.echo(f"\n=== deleted_item history ({len(deleted)}) ===")
        for d in deleted:
            typer.echo(f"  kind={d.get('kind')} deleted_at={d.get('deleted_at')} reason={d.get('reason')}")
