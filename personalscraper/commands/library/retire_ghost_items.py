"""Retire every ``media_item`` whose media folder is gone, with no cap.

The full scan retires ghost items itself, but never more than a tenth of a
disk's items in one run (:data:`personalscraper.indexer.ghost_items.MAX_RETIRE_SHARE`):
a larger share points at a disk problem rather than at the library. A backlog
of ghosts left by older builds is larger than that, so it is cleared by this
explicit command, which applies every other guard of
:func:`~personalscraper.indexer.ghost_items.retire_ghost_items` — configured and
mounted disk, folder gone, no live file, no open item repair — and lifts the cap.

``--dry-run`` lists each ghost with its reason and writes nothing.

Examples:
    personalscraper --format json library-retire-ghost-items --dry-run
    personalscraper --format json library-retire-ghost-items
    personalscraper library-retire-ghost-items --disk medias1 --dry-run
"""

from __future__ import annotations

import sqlite3 as _sqlite3
from pathlib import Path

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

log = get_logger("cli")


def _disk_rows(conn: _sqlite3.Connection) -> list[DiskRow]:
    """Return every row of the ``disk`` table.

    Args:
        conn: Open SQLite connection.

    Returns:
        The rows, by id.
    """
    rows = conn.execute(
        "SELECT id, uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes "
        "FROM disk ORDER BY id"
    ).fetchall()
    return [
        DiskRow(
            id=r[0],
            uuid=r[1],
            label=r[2],
            mount_path=r[3],
            last_seen_at=r[4],
            merkle_root=r[5],
            is_mounted=r[6],
            unreachable_strikes=r[7],
        )
        for r in rows
    ]


@app.command("library-retire-ghost-items")
@handle_cli_errors
def library_retire_ghost_items(
    ctx: typer.Context,
    dry_run: bool = typer.Option(False, "--dry-run", help="List the ghost items and why; write nothing."),
    disk: str | None = typer.Option(None, "--disk", help="Only this disk label."),
    config: Path | None = typer.Option(None, "--config", "-c", help="Path to config.json5 or config dir."),
    db: Path | None = typer.Option(None, "--db", help="Path to library.db (overrides config)."),
) -> None:
    """Retire the items whose ``dispatch_path`` is gone, on every configured and mounted disk.

    Prints a JSON summary: per disk, whether it was frozen (mount not confirmed),
    the ghosts retired (or that would be) and the ghost folders kept, each with
    its reason.
    """
    from personalscraper.conf.loader import load_config  # noqa: PLC0415
    from personalscraper.indexer.db import _apply_pragmas  # noqa: PLC0415
    from personalscraper.indexer.ghost_items import configured_disks, retire_ghost_items  # noqa: PLC0415
    from personalscraper.indexer.merkle import verify_disk_mounted  # noqa: PLC0415
    from personalscraper.indexer.scanner import filter_disks  # noqa: PLC0415

    cfg = ctx.obj.config if ctx.obj is not None else load_config(config)
    if db is not None:
        db_path = db
    else:
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
        disks = configured_disks(filter_disks(_disk_rows(conn), disk), cfg)
        reports = [retire_ghost_items(conn, d, verify_disk_mounted(d), dry_run=dry_run, max_share=None) for d in disks]
        retired = sum(report.retired for report in reports)
        if retired:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        log.info("retire_ghost_items.done", dry_run=dry_run, disks=len(reports), retired=retired)
        emit(
            {
                "dry_run": dry_run,
                "disks": [
                    {
                        "disk": report.disk_label,
                        "frozen": report.frozen,
                        "disk_items": report.disk_items,
                        "ghosts": [
                            {
                                "item_id": ghost.item_id,
                                "title": ghost.title,
                                "kind": ghost.kind,
                                "dispatch_path": ghost.dispatch_path,
                                "reason": ghost.reason,
                            }
                            for ghost in report.ghosts
                        ],
                        "kept": [
                            {"item_id": kept.item_id, "dispatch_path": kept.dispatch_path, "reason": kept.reason}
                            for kept in report.kept
                        ],
                    }
                    for report in reports
                ],
                "would_retire" if dry_run else "retired": (
                    sum(len(report.ghosts) for report in reports) if dry_run else retired
                ),
            }
        )
    finally:
        conn.close()
