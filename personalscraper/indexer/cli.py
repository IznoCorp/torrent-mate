"""CLI command implementations for the media indexer sub-system.

Provides callable functions (not Typer decorators) that are wired into the
top-level :mod:`personalscraper.cli` application.  Each function returns an
integer exit code so it can be tested without invoking Typer machinery.

Commands:
- :func:`library_status_command` — show the latest completed scan run summary.
- :func:`library_index_command` — run a full or quick indexer scan.
"""

from __future__ import annotations

import sys
from pathlib import Path

from personalscraper.logger import get_logger

log = get_logger("indexer.cli")

# ---------------------------------------------------------------------------
# library-status
# ---------------------------------------------------------------------------


def library_status_command(config_path: Path | None = None) -> int:
    """Print a one-line summary of the latest completed scan run.

    Loads the PersonalScraper config, opens (or creates) the indexer database,
    applies any pending migrations, then queries ``scan_run`` for the most
    recently finished ``'completed'`` row.

    If no completed scan exists the message ``"no scans yet"`` is printed to
    stdout and exit code 0 is returned.

    On any indexer infrastructure error (:class:`~personalscraper.indexer.db.IndexerLockError`,
    :class:`~personalscraper.indexer.db.IndexerCorruptError`,
    :class:`~personalscraper.indexer.db.IndexerDiskFullError`,
    :class:`~personalscraper.indexer.db.IndexerInvalidPathError`,
    :class:`~personalscraper.indexer.db.IndexerMigrationError`) the error
    message is printed to stderr and exit code 1 is returned.

    Args:
        config_path: Optional explicit path to the config file (or config
            directory for v2 split layout).  When ``None`` the standard
            resolution order is used (``$PERSONALSCRAPER_CONFIG``, then
            ``./config.json5``).

    Returns:
        ``0`` on success (even when no scans exist), ``1`` on infrastructure error.
    """
    log.info("indexer.cli.status", config_path=str(config_path) if config_path else None)

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

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    # --- Open DB and apply pending migrations ---
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
        apply_migrations(conn, migrations_dir)
    except (
        IndexerLockError,
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerMigrationError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # --- Query latest successful scan ---
    # The schema CHECK allows: 'running', 'ok', 'failed', 'aborted'.
    # 'ok' is the terminal success status.
    row = conn.execute(
        "SELECT id, finished_at, status FROM scan_run WHERE status = 'ok' ORDER BY finished_at DESC LIMIT 1"
    ).fetchone()

    if row is None:
        print("no scans yet")
        return 0

    run_id, finished_at, status = row
    print(f"latest scan: {run_id}, finished_at={finished_at}, status={status}")
    return 0


# ---------------------------------------------------------------------------
# library-index
# ---------------------------------------------------------------------------


def library_index_command(
    *,
    mode: str = "full",
    disk: str | None = None,
    budget_seconds: int | None = None,
    dry_run: bool = False,
    wait_for_lock_seconds: int = 0,
    config_path: Path | None = None,
) -> int:
    """Run an indexer scan (full or quick) and print a JSON summary to stdout.

    Loads config, acquires the writer lock, opens (or creates) the indexer
    database, applies pending migrations, resolves the disk list, then calls
    :func:`~personalscraper.indexer.scanner.scan` with the requested mode.
    After the scan, :func:`~personalscraper.indexer.outbox.drain_if_present`
    is called so Phase 5 can hook in event dispatch without a signature change.

    Args:
        mode: Scan mode — ``"full"`` or ``"quick"`` (``"incremental"`` and
            ``"enrich"`` are accepted by the scanner but not yet fully
            implemented).
        disk: If provided, restrict the scan to the disk with this label.
            On ``IndexerConfigError("no disk with label 'X'")`` the error
            is printed to stderr and exit code 2 is returned.
        budget_seconds: Not yet used by the scanner; reserved for Phase 4
            budget-exhaustion logic.
        dry_run: When ``True``, all DB writes are wrapped in a SQLite savepoint
            that is always rolled back so no rows are persisted.
        wait_for_lock_seconds: Seconds to wait for the writer lock before
            giving up.  ``0`` = fail immediately if locked.
        config_path: Optional explicit path to config.json5 or config
            directory.  When ``None`` the standard resolution order is used.

    Returns:
        ``0`` on success, ``1`` on infrastructure error, ``2`` on unknown disk.
    """
    import json  # noqa: PLC0415
    import sqlite3  # noqa: PLC0415

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
        indexer_lock,
        open_db,
    )
    from personalscraper.indexer.outbox import drain_if_present  # noqa: PLC0415
    from personalscraper.indexer.scanner import (  # noqa: PLC0415
        IndexerConfigError,
        ScanMode,
        filter_disks,
        scan,
    )
    from personalscraper.indexer.schema import DiskRow  # noqa: PLC0415

    log.info(
        "indexer.cli.index",
        mode=mode,
        disk=disk,
        dry_run=dry_run,
        config_path=str(config_path) if config_path else None,
    )

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    # --- Validate mode early (before acquiring the lock) ---
    try:
        scan_mode = ScanMode(mode)
    except ValueError:
        valid_modes = ", ".join(m.value for m in ScanMode)
        print(f"Invalid mode '{mode}'. Valid: {valid_modes}", file=sys.stderr)
        return 1

    # --- Acquire writer lock ---
    try:
        with indexer_lock(db_path, timeout=wait_for_lock_seconds):
            # --- Open DB and apply pending migrations ---
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = open_db(db_path)
                apply_migrations(conn, migrations_dir)
            except (
                IndexerLockError,
                IndexerCorruptError,
                IndexerDiskFullError,
                IndexerInvalidPathError,
                IndexerMigrationError,
            ) as exc:
                print(str(exc), file=sys.stderr)
                return 1

            # --- Resolve disk list from the ``disk`` table ---
            conn.row_factory = sqlite3.Row
            raw_rows = conn.execute(
                "SELECT id, uuid, label, mount_path, last_seen_at, merkle_root, "
                "is_mounted, unreachable_strikes FROM disk"
            ).fetchall()
            disks: list[DiskRow] = [
                DiskRow(
                    id=r["id"],
                    uuid=r["uuid"],
                    label=r["label"],
                    mount_path=r["mount_path"],
                    last_seen_at=r["last_seen_at"],
                    merkle_root=r["merkle_root"],
                    is_mounted=r["is_mounted"],
                    unreachable_strikes=r["unreachable_strikes"],
                )
                for r in raw_rows
            ]

            # --- Filter to requested disk label (if provided) ---
            try:
                filtered_disks = filter_disks(disks, disk)
            except IndexerConfigError as exc:
                print(str(exc), file=sys.stderr)
                return 2

            # --- Allocate next scan generation ---
            gen_row = conn.execute("SELECT MAX(scan_generation) FROM media_file").fetchone()
            next_gen: int = (gen_row[0] or 0) + 1

            # --- Run scan (dry_run wraps writes in a rolled-back savepoint) ---
            if dry_run:
                conn.execute("SAVEPOINT _dry_run")

            try:
                result = scan(
                    disks=filtered_disks,
                    mode=scan_mode,
                    generation=next_gen,
                    conn=conn,
                    disk_filter=disk,
                )
            except (IndexerCorruptError, IndexerDiskFullError) as exc:
                print(str(exc), file=sys.stderr)
                if dry_run:
                    conn.execute("ROLLBACK TO SAVEPOINT _dry_run")
                return 1
            finally:
                if dry_run:
                    # Always roll back on dry_run so no rows are committed.
                    try:
                        conn.execute("ROLLBACK TO SAVEPOINT _dry_run")
                    except Exception:  # noqa: BLE001 — best-effort rollback
                        pass

            # --- Drain outbox (no-op stub until Phase 5) ---
            drained = drain_if_present(conn)
            log.debug("indexer.cli.index.outbox_drained", count=drained)

            # --- Print JSON summary to stdout ---
            summary = {
                "mode": scan_mode.value,
                "files_walked": result.files_visited,
                "dirs_walked": result.dirs_visited,
                "disks_skipped": result.disks_skipped,
                "scan_run_id": result.scan_run_id,
                "status": result.status,
                "budget_exhausted": False,
            }
            print(json.dumps(summary))
            return 0

    except IndexerLockError as exc:
        print(str(exc), file=sys.stderr)
        return 1
