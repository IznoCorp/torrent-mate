"""Merge ``media_item`` rows that share one ``dispatch_path`` into the oldest.

A media folder is one work. An older build split some folders into two items
(see :mod:`personalscraper.indexer.merge_items`); this command folds each
duplicate into the oldest item of its folder, re-pointing every child row
(releases and their files, seasons and episodes, attributes, issues, scan
events, item repairs) before the duplicate is deleted.

``--dry-run`` lists the groups and writes nothing. Without it the merge runs in
one transaction, then checkpoints the WAL.

Examples:
    personalscraper library-merge-duplicate-items --dry-run
    personalscraper library-merge-duplicate-items
    personalscraper library-merge-duplicate-items --db /custom/path/library.db --dry-run
"""

from __future__ import annotations

import sqlite3 as _sqlite3
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.logger import get_logger

log = get_logger("cli")


@app.command("library-merge-duplicate-items")
@handle_cli_errors
def library_merge_duplicate_items(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="List the duplicate groups and the item each merges into; write nothing.",
    ),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Merge every group of items sharing a ``dispatch_path`` into its oldest item.

    Prints a JSON summary: each group's path, keeper and merged ids, the groups
    skipped (a movie and a show on one folder) and the merged count.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415
    from personalscraper.indexer.merge_items import merge_duplicate_items  # noqa: PLC0415

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

    conn = _sqlite3.connect(str(db_path))
    _apply_pragmas(conn)
    try:
        report = merge_duplicate_items(conn, dry_run=dry_run)
        if not dry_run and report.merged:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        log.info(
            "merge_duplicate_items.done",
            dry_run=dry_run,
            groups=len(report.groups),
            skipped=len(report.skipped),
            merged=report.merged,
        )
        emit(
            {
                "dry_run": dry_run,
                "groups": [
                    {
                        "dispatch_path": group.dispatch_path,
                        "keeper_id": group.keeper_id,
                        "merged_ids": list(group.duplicate_ids),
                        "titles": {str(item_id): title for item_id, title in group.titles.items()},
                    }
                    for group in report.groups
                ],
                "skipped": [
                    {
                        "dispatch_path": group.dispatch_path,
                        "ids": [group.keeper_id, *group.duplicate_ids],
                        "reason": why,
                    }
                    for group, why in report.skipped
                ],
                "would_merge" if dry_run else "merged": (
                    sum(len(group.duplicate_ids) for group in report.groups) if dry_run else report.merged
                ),
            }
        )
    finally:
        conn.close()
