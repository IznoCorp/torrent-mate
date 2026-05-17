"""Repair indexer command functions."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import typer

from personalscraper.core.event_bus import EventBus
from personalscraper.logger import get_logger

log = get_logger("indexer.cli")


def library_repair_command(
    *,
    budget_seconds: float = 60.0,
    config_path: Path | None = None,
    event_bus: EventBus,
) -> int:
    """Drain the repair queue within a wall-clock time budget.

    Delegates to :func:`~personalscraper.indexer.repair.drain`.  The noop
    processor is used by default (real handlers wired in later phases).

    Args:
        budget_seconds: Maximum wall-clock seconds to spend draining.
            Default ``60.0`` seconds.
        config_path: Optional explicit path to config.json5 or config directory.
        event_bus: Required :class:`EventBus` forwarded to ``open_db`` so the
            pre-open free-space guard emits ``DiskFullWarning`` on the run's
            subscriber-wired bus.

    Returns:
        ``0`` on completion (budget exhausted or queue empty), ``1`` on error.
    """
    import json  # noqa: PLC0415

    from personalscraper.conf.loader import (  # noqa: PLC0415
        ConfigNotFoundError,
        ConfigValidationError,
        load_config,
        resolve_config_path,
    )
    from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
    from personalscraper.indexer.db import (  # noqa: PLC0415
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerLockError,
        IndexerMigrationError,
        apply_migrations,
        open_db,
    )
    from personalscraper.indexer.repair import drain  # noqa: PLC0415

    log.info("indexer.cli.repair", budget_seconds=budget_seconds)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    migrations_dir = Path(_migrations_pkg.__file__).parent

    from contextlib import closing  # noqa: PLC0415

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path, event_bus=event_bus)
    except (
        IndexerLockError,
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerMigrationError,
    ) as exc:
        typer.echo(str(exc), err=True)
        return 1

    with closing(conn):
        try:
            apply_migrations(conn, migrations_dir)
        except (
            IndexerLockError,
            IndexerCorruptError,
            IndexerDiskFullError,
            IndexerInvalidPathError,
            IndexerMigrationError,
        ) as exc:
            typer.echo(str(exc), err=True)
            return 1

        stats = drain(conn, budget_seconds=budget_seconds)

        # Tombstone retention: purge deleted_item rows older than the
        # configured retention window (DESIGN §8.x).  library-repair is
        # the natural maintenance home for this — drift writes new rows
        # whenever a soft-delete is finalised; without periodic purge
        # the tombstone table grows monotonically.
        from personalscraper.indexer.drift import purge_old_tombstones  # noqa: PLC0415

        retention_days = int(cfg.indexer.log.deleted_item_retention_days)
        try:
            tombstones_purged = purge_old_tombstones(conn, retention_days=retention_days)
            conn.commit()
        except sqlite3.Error as exc:
            log.warning(
                "indexer.repair.tombstone_purge_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                retention_days=retention_days,
                exc_info=True,
            )
            tombstones_purged = 0

        summary = {
            "processed": stats.processed,
            "succeeded": stats.succeeded,
            "failed": stats.failed,
            "budget_exhausted": stats.budget_exhausted,
            "pending_depth": stats.pending_depth,
            "tombstones_purged": tombstones_purged,
            "retention_days": retention_days,
        }
        typer.echo(json.dumps(summary))
        return 0


# ---------------------------------------------------------------------------
# library-show
# ---------------------------------------------------------------------------
