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

import json
import sqlite3 as _sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

import typer

from personalscraper.cli_app import app
from personalscraper.cli_helpers import handle_cli_errors
from personalscraper.cli_helpers.output import emit
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.indexer.ghost_items import GhostReport

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


def _disk_payload(report: GhostReport) -> dict[str, object]:
    """Return one disk's report as the command prints it.

    Args:
        report: The disk's :class:`~personalscraper.indexer.ghost_items.GhostReport`.

    Returns:
        A JSON-serialisable dict.
    """
    return {
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

    Prints a JSON summary: per disk, whether it was frozen (mount not verified),
    the ghosts retired (or that would be) and the ghost folders kept, each with
    its reason; then the disks whose pass failed. Each disk's report is also
    written to stderr as it completes. Exits 1 when ``--disk`` names a disk the
    configuration does not hold, or when any disk's pass failed.
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
        if disk is not None and not disks:
            # The store knows the disk but the configuration does not: its root
            # is mounted by nobody, so none of its folders can be judged.
            typer.echo(f"Disk {disk!r} is not in the configuration: its ghost items cannot be judged", err=True)
            raise typer.Exit(code=1)
        reports: list[GhostReport] = []
        failed: list[dict[str, str]] = []
        for d in disks:
            # One disk at a time: each pass commits on its own, so a failure on
            # one leaves the others' work done — and reported as it completes.
            try:
                report = retire_ghost_items(conn, d, verify_disk_mounted(d), dry_run=dry_run, max_share=None)
            except Exception as exc:  # noqa: BLE001 — the pass rolled back; the run goes on and exits 1
                log.error(
                    "retire_ghost_items.disk_failed",
                    disk=d.label,
                    error=str(exc),
                    error_type=type(exc).__name__,
                    exc_info=True,
                )
                failed.append({"disk": d.label, "error": f"{type(exc).__name__}: {exc}"})
                continue
            reports.append(report)
            typer.echo(json.dumps(_disk_payload(report)), err=True)
        retired = sum(report.retired for report in reports)
        if retired:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        log.info("retire_ghost_items.done", dry_run=dry_run, disks=len(reports), retired=retired, failed=len(failed))
        emit(
            {
                "dry_run": dry_run,
                "disks": [_disk_payload(report) for report in reports],
                "failed": failed,
                "would_retire" if dry_run else "retired": (
                    sum(len(report.ghosts) for report in reports) if dry_run else retired
                ),
            }
        )
        if failed:
            raise typer.Exit(code=1)
    finally:
        conn.close()
