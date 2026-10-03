"""Remove the 0-file phantom index rows beside a row of the same provider id that holds files.

Reads the provider-id duplicate groups, picks in each group holding a row with
live files the rows holding none, and removes them from the index (a
``deleted_item`` tombstone and a ``destructive_op`` journal row each). Files on
disk are never touched; a row holding a file and a group whose every row holds
no file are left alone.

``--apply`` removes; without it (the default) the rows are listed and nothing is
written. The output is codes and counts: ``apply``, ``phantom_rows`` (the ids)
and ``deleted`` / ``would_delete``.

Examples:
    personalscraper library-remove-phantom-rows
    personalscraper library-remove-phantom-rows --apply
    personalscraper --format json library-remove-phantom-rows --db /custom/path/library.db
"""

from __future__ import annotations

import os
import sqlite3 as _sqlite3
import uuid
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit


@app.command("library-remove-phantom-rows")
@handle_cli_errors
def library_remove_phantom_rows(
    ctx: typer.Context,
    apply: bool = typer.Option(False, "--apply", help="Remove the rows (default: dry-run)."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Remove the index rows holding no file beside a row of the same provider id that holds some.

    Dry run unless ``--apply``. The journal rows carry the maintenance runner's
    ``PERSONALSCRAPER_RUN_UID`` when it launched the command, a fresh uid otherwise.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415
    from personalscraper.indexer.duplicates import find_provider_id_duplicates  # noqa: PLC0415
    from personalscraper.indexer.phantom_rows import phantom_rows, remove_phantom_rows  # noqa: PLC0415

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

    # A dry run opens the database read only: it cannot write, even by mistake.
    target = str(db_path) if apply else f"file:{db_path}?mode=ro"
    conn = _sqlite3.connect(target, uri=not apply, isolation_level=None)
    _apply_pragmas(conn)
    try:
        ids = phantom_rows(find_provider_id_duplicates(conn))
        removed = remove_phantom_rows(
            conn,
            ids,
            db_path=db_path,
            run_uid=os.environ.get("PERSONALSCRAPER_RUN_UID") or uuid.uuid4().hex,
            dry_run=not apply,
        )
    finally:
        conn.close()

    emit({"apply": apply, "phantom_rows": ids, "deleted" if apply else "would_delete": removed})
