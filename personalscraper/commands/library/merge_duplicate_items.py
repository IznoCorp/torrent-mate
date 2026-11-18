"""Merge ``media_item`` rows that share one ``dispatch_path`` into the oldest.

A media folder is one work. An older build split some folders into two items
(see :mod:`personalscraper.indexer.merge_items`); this command folds each
duplicate into the oldest item of its folder, re-pointing every child row
(releases and their files, seasons and episodes, attributes, issues, scan
events, item repairs) before the duplicate is deleted.

Like its siblings (``library-dedup-titles``, ``library-fix-*``), it previews by
default: it lists the groups and writes nothing. ``--apply`` runs the merge in
one transaction, then checkpoints the WAL.

Examples:
    personalscraper library-merge-duplicate-items
    personalscraper library-merge-duplicate-items --apply
    personalscraper library-merge-duplicate-items --db /custom/path/library.db
"""

from __future__ import annotations

import sqlite3 as _sqlite3
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.core.sqlite import refuse_newer_schema
from personalscraper.i18n import t
from personalscraper.indexer.migrations import MIGRATIONS_DIR as LIBRARY_MIGRATIONS_DIR
from personalscraper.logger import get_logger

log = get_logger("cli")


@app.command(
    "library-merge-duplicate-items", help=t("cli_library.merge_duplicate_items.library_merge_duplicate_items_help")
)
@handle_cli_errors
def library_merge_duplicate_items(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False, "--apply", help=t("cli_library.merge_duplicate_items.library_merge_duplicate_items_apply_help")
    ),
    config: Path | None = typer.Option(
        None, "--config", "-c", help=t("cli_library.merge_duplicate_items.library_merge_duplicate_items_config_help")
    ),
    db: Path | None = typer.Option(
        None, "--db", help=t("cli_library.merge_duplicate_items.library_merge_duplicate_items_db_help")
    ),
) -> None:
    """Merge every group of items sharing a ``dispatch_path`` into its oldest item.

    Prints a JSON summary: each group's path, keeper and merged ids, the groups
    skipped (a movie and a show on one folder) and the merged count.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415
    from personalscraper.indexer.merge_items import merge_duplicate_items  # noqa: PLC0415

    dry_run = not apply

    if db is not None:
        db_path = db
    else:
        cfg = ctx.obj.config if ctx.obj is not None else load_config(config)
        if cfg.indexer.db_path is None:
            typer.echo(t("cli_library.merge_duplicate_items.db_path_not_configured"), err=True)
            raise typer.Exit(code=1)
        db_path = Path(cfg.indexer.db_path)

    if not db_path.exists():
        typer.echo(t("cli_library.merge_duplicate_items.database_not_found", path=str(db_path)), err=True)
        raise typer.Exit(code=1)

    conn = _sqlite3.connect(str(db_path))
    refuse_newer_schema(conn, LIBRARY_MIGRATIONS_DIR)
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
                "titles_kept": [{"keeper_id": keeper_id, "title": title} for keeper_id, title in report.titles_kept],
                "would_merge" if dry_run else "merged": (
                    sum(len(group.duplicate_ids) for group in report.groups) if dry_run else report.merged
                ),
            }
        )
    finally:
        conn.close()
