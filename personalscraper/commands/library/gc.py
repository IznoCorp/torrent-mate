"""Garbage-collection Typer command for the library index_outbox."""

from __future__ import annotations

import json as _json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.core.event_bus import EventBus


@app.command("library-gc")
@handle_cli_errors
def library_gc(
    ctx: typer.Context,
    older_than_days: int = typer.Option(
        30,
        "--older-than-days",
        help=(
            "Delete ``index_outbox`` rows with status=done whose "
            "``processed_at`` timestamp is older than this many days. "
            "Default: 30."
        ),
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=("Preview mode: count how many rows would be deleted without actually deleting them. No DB writes occur."),
    ),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir"),
) -> None:
    """Garbage-collect old index_outbox rows (status=done, processed_at < cutoff).

    Removes stale ``index_outbox`` rows that have been fully processed
    (status=``done``) and whose ``processed_at`` timestamp is older than
    ``--older-than-days`` days.  These rows accumulate over time as the
    pipeline emits dispatch / scraper / trailer events — without periodic
    GC the table grows without bound and degrades query performance.

    With ``--dry-run`` the command counts matching rows and prints a JSON
    summary without deleting anything.  Without ``--dry-run`` the matching
    rows are hard-deleted and the count is reported.

    The cutoff is computed as ``now() - older_than_days * 86400`` seconds
    (UTC).  Only rows with ``status='done'`` are targeted — pending, failed,
    and deferred rows are never touched.

    Examples:
        personalscraper library-gc --dry-run
        personalscraper library-gc --older-than-days 7
        personalscraper library-gc
    """
    import os as _os  # noqa: PLC0415

    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

    effective_config: Optional[Path] = config or (ctx.obj.config_override if ctx.obj else None)
    cfg = ctx.obj.config if ctx.obj is not None else load_config(effective_config)

    if cfg.indexer.db_path is None:
        typer.echo("indexer.db_path is not configured", err=True)
        raise typer.Exit(code=1)

    db_path = Path(cfg.indexer.db_path)  # narrow Any|Path|None → Path for mypy strict mode
    migrations_dir = _os.path.dirname(_migrations_pkg.__file__)

    # Compute cutoff as a UTC Unix timestamp (integer seconds).
    # ``processed_at`` is stored as INTEGER (Unix seconds) in index_outbox.
    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(days=older_than_days)
    cutoff_ts = int(cutoff_dt.timestamp())

    event_bus = EventBus()
    conn = open_db(db_path, event_bus=event_bus)
    apply_migrations(conn, Path(migrations_dir))

    try:
        # Count matching rows regardless of dry-run mode so we can report
        # how many were (or would be) deleted.
        row = conn.execute(
            "SELECT COUNT(*) FROM index_outbox WHERE status='done' AND processed_at < ?",
            (cutoff_ts,),
        ).fetchone()
        count = row[0] if row else 0

        if dry_run:
            conn.close()
            typer.echo(
                _json.dumps(
                    {
                        "dry_run": True,
                        "older_than_days": older_than_days,
                        "rows_to_delete": count,
                    }
                )
            )
            return

        # Live delete — hard-delete all done rows older than the cutoff.
        conn.execute(
            "DELETE FROM index_outbox WHERE status='done' AND processed_at < ?",
            (cutoff_ts,),
        )
        conn.commit()
    finally:
        conn.close()

    typer.echo(
        _json.dumps(
            {
                "dry_run": False,
                "older_than_days": older_than_days,
                "rows_deleted": count,
            }
        )
    )
