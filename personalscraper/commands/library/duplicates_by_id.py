"""Report the provider ids that name two index rows or two media folders.

Read only: opens ``library.db`` with ``mode=ro`` and prints one record per
duplicated id (provider, id, kind, then each row's id, live-file count and folder
count) and the totals. Nothing is merged or deleted (Q15); settling a group is a
separate action.

Examples:
    personalscraper library-duplicates-by-id
    personalscraper --format json library-duplicates-by-id --db /custom/path/library.db
"""

from __future__ import annotations

import sqlite3 as _sqlite3
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit


@app.command("library-duplicates-by-id")
@handle_cli_errors
def library_duplicates_by_id(
    ctx: typer.Context,
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Report the provider ids held by two or more rows, or by one row over two media folders.

    Read only. The output carries codes and counts: per group the provider, the id,
    the kind and each row's ``item_id``, ``live_files`` and ``folders`` count; then
    ``groups``, ``rows`` and ``empty_rows`` (rows holding no live file).
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415
    from personalscraper.indexer.duplicates import find_provider_id_duplicates  # noqa: PLC0415

    if db is not None:
        db_path = db
    else:
        cfg = ctx.obj.config if ctx.obj is not None else load_config(config)
        if cfg.indexer.db_path is None:
            typer.echo("indexer.db_path is not configured", err=True)
            raise typer.Exit(code=1)
        db_path = Path(cfg.indexer.db_path)

    if not db_path.exists():
        typer.echo(f"Database not found: {db_path}", err=True)
        raise typer.Exit(code=1)

    conn = _sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    _apply_pragmas(conn)
    try:
        groups = find_provider_id_duplicates(conn)
    finally:
        conn.close()

    payload = {
        "groups": len(groups),
        "rows": sum(len(g.rows) for g in groups),
        "empty_rows": sum(1 for g in groups for r in g.rows if r.live_files == 0),
        "duplicates": [
            {
                "provider": g.provider,
                "provider_id": g.provider_id,
                "kind": g.kind,
                "rows": [{"item_id": r.item_id, "live_files": r.live_files, "folders": len(r.folders)} for r in g.rows],
            }
            for g in groups
        ],
    }
    emit(payload)
