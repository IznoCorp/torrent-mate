"""Query Typer commands for the library."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import CommandContext, boundary, handle_cli_errors
from personalscraper.i18n import t


@app.command("library-status", help=t("cli_library.query.library_status_help"))
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_status(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help=t("cli_library.query.config_help")),
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


@app.command("library-search", help=t("cli_library.query.library_search_help"))
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_search(
    ctx: typer.Context,
    query: str = typer.Argument(..., help=t("cli_library.query.library_search_query_help")),
    limit: int = typer.Option(50, "--limit", help=t("cli_library.query.library_search_limit_help")),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help=t("cli_library.query.config_help")),
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
        typer.echo(t("cli_library.query.no_results"))
        return
    typer.echo(
        t(
            "cli_library.query.search_header",
            id=f"{'ID':<8}",
            title=f"{'TITLE':<40}",
            year=f"{'YEAR':<6}",
            nfo=f"{'NFO':<10}",
        )
    )
    for r in rows:
        year_str = str(r["year"]) if r["year"] is not None else ""
        nfo_str = str(r["nfo_status"]) or ""
        title = str(r["title"]) or ""
        typer.echo(
            t(
                "cli_library.query.search_row",
                id=f"{r['id']:<8}",
                title=f"{title[:38]:<40}",
                year=f"{year_str:<6}",
                nfo=f"{nfo_str:<10}",
            )
        )


@app.command("library-show", help=t("cli_library.query.library_show_help"))
@handle_cli_errors
@boundary(needs="config", staging=False)
def library_show(
    ctx: typer.Context,
    item_id: int = typer.Argument(..., help=t("cli_library.query.library_show_item_id_help")),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help=t("cli_library.query.config_help")),
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
    typer.echo(t("cli_library.query.item_heading", item_id=str(item_id)))
    for key, value in item.items():
        typer.echo(t("cli_library.query.item_field", key=str(key), value=str(value)))

    seasons = cast("list[dict[str, object]]", payload.get("seasons", []))
    if seasons:
        typer.echo(t("cli_library.query.seasons_heading", total=len(seasons)))
        for s in seasons:
            typer.echo(
                t(
                    "cli_library.query.season_line",
                    number=str(s.get("number")),
                    episodes=str(s.get("episode_count")),
                    has_poster=str(s.get("has_poster")),
                    nfo_count=str(s.get("episodes_with_nfo")),
                )
            )
            for ep in cast("list[dict[str, object]]", s.get("episodes", [])):
                typer.echo(
                    t("cli_library.query.episode_line", number=str(ep.get("number")), title=str(ep.get("title")))
                )

    files = cast("list[dict[str, object]]", payload.get("files", []))
    if files:
        typer.echo(t("cli_library.query.files_heading", total=len(files)))
        for f in files:
            typer.echo(
                t(
                    "cli_library.query.file_line",
                    id=str(f.get("id")),
                    rel_path=str(f.get("rel_path")),
                    filename=str(f.get("filename")),
                    size_bytes=str(f.get("size_bytes")),
                    mtime_ns=str(f.get("mtime_ns")),
                )
            )
            for st in cast("list[dict[str, object]]", f.get("streams", [])):
                typer.echo(
                    t(
                        "cli_library.query.stream_line",
                        idx=str(st.get("idx")),
                        kind=str(st.get("kind")),
                        codec=str(st.get("codec")),
                        lang=str(st.get("lang")),
                    )
                )

    attributes = cast("list[dict[str, object]]", payload.get("attributes", []))
    if attributes:
        typer.echo(t("cli_library.query.attributes_heading", total=len(attributes)))
        for a in attributes:
            typer.echo(t("cli_library.query.attribute_line", key=str(a.get("key")), value=str(a.get("value"))))

    deleted = cast("list[dict[str, object]]", payload.get("deleted_history", []))
    if deleted:
        typer.echo(t("cli_library.query.deleted_heading", total=len(deleted)))
        for d in deleted:
            typer.echo(
                t(
                    "cli_library.query.deleted_line",
                    kind=str(d.get("kind")),
                    deleted_at=str(d.get("deleted_at")),
                    reason=str(d.get("reason")),
                )
            )
