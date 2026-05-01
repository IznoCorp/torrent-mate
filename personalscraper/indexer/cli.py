"""CLI command implementations for the media indexer sub-system.

Provides callable functions (not Typer decorators) that are wired into the
top-level :mod:`personalscraper.cli` application.  Each function returns an
integer exit code so it can be tested without invoking Typer machinery.

Commands:
- :func:`library_status_command` — tabular disk inventory, queue depths, and orphan count.
- :func:`library_index_command` — run a full/quick/incremental/enrich indexer scan.
- :func:`library_verify_command` — re-stat every file and mark mismatches for repair.
- :func:`library_search_command` — execute a flex-attr query string.
- :func:`library_repair_command` — drain the repair queue within a time budget.
- :func:`library_show_command` — pretty-print all stored data for one media item.
- :func:`config_migrate_category_command` — rewrite ``category_id`` for renamed categories.

Helpers (module-private):
- :func:`_bootstrap_disks_from_config` — populate the ``disk`` table from ``Config.disks``.

Note: :func:`~personalscraper.indexer.merkle._resolve_volume_root` is defined in
:mod:`personalscraper.indexer.merkle` and re-used here via import.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

import typer

from personalscraper.conf.models import DiskConfig
from personalscraper.indexer.merkle import _resolve_volume_root
from personalscraper.logger import get_logger

log = get_logger("indexer.cli")


# ---------------------------------------------------------------------------
# Module-private helpers
# ---------------------------------------------------------------------------


def _bootstrap_disks_from_config(
    conn: sqlite3.Connection,
    cfg_disks: Sequence[DiskConfig],
) -> int:
    """Populate the ``disk`` table from ``Config.disks`` entries on first run.

    Called when the ``disk`` table is empty and ``Config.disks`` is non-empty.
    For each :class:`~personalscraper.conf.models.DiskConfig`, this function:

    1. Resolves the volume mount root via :func:`_resolve_volume_root`.
    2. Calls ``diskutil`` via
       :func:`~personalscraper.indexer.merkle.bootstrap_disk_identity` to
       obtain the volume UUID and write the sentinel file.
    3. INSERTs the disk row with ``is_mounted=1`` and ``last_seen_at=now``.

    If ``bootstrap_disk_identity`` raises :class:`~personalscraper.indexer.merkle.BootstrapError`
    (e.g. disk offline or not a macOS system), the disk is skipped with a
    warning so that offline disks do not block the bootstrap entirely.

    Args:
        conn: Open :class:`sqlite3.Connection` with migrations applied.
        cfg_disks: Sequence of :class:`~personalscraper.conf.models.DiskConfig`
            objects from the loaded config.

    Returns:
        Number of disk rows successfully inserted.
    """
    from personalscraper.indexer.merkle import BootstrapError, bootstrap_disk_identity  # noqa: PLC0415

    registered = 0
    now = int(time.time())

    for disk_cfg in cfg_disks:
        mount_root = _resolve_volume_root(disk_cfg.path)
        try:
            uuid = bootstrap_disk_identity(mount_root)
        except BootstrapError as exc:
            log.warning(
                "indexer.bootstrap.disk_skipped",
                disk_id=disk_cfg.id,
                mount_root=str(mount_root),
                reason=str(exc),
            )
            continue

        conn.execute(
            "INSERT OR IGNORE INTO disk "
            "(uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes) "
            "VALUES (?, ?, ?, ?, NULL, 1, 0)",
            (uuid, disk_cfg.id, str(disk_cfg.path), now),
        )
        log.info(
            "indexer.bootstrap.disk_registered",
            disk_id=disk_cfg.id,
            uuid=uuid,
            mount_path=str(disk_cfg.path),
        )
        registered += 1

    return registered


# ---------------------------------------------------------------------------
# library-status
# ---------------------------------------------------------------------------


def library_status_command(config_path: Path | None = None) -> int:
    """Print a tabular summary of disk inventory, scan health, and queue depths.

    Loads the PersonalScraper config, opens (or creates) the indexer database,
    applies any pending migrations, then queries multiple tables for a rich
    status view.

    Output includes:
    - Disk inventory: label, mounted state, last scan time, generation.
    - Last completed scan run per disk (or global).
    - Repair queue: pending depth, age of oldest row.
    - Outbox: pending depth.
    - Deleted items: count.
    - Enrich-pending count (``media_file.enriched_at IS NULL``).
    - Category-orphan count (DESIGN §17.2): items with a ``category_id`` not
      present in the current config's declared categories.

    Exit codes:
    - ``0`` — healthy.
    - ``1`` — repair queue oldest > 7 days OR depth > 1 000 OR any category
      orphans exist, or an infrastructure error occurred.

    Args:
        config_path: Optional explicit path to the config file (or config
            directory for v2 split layout).  When ``None`` the standard
            resolution order is used (``$PERSONALSCRAPER_CONFIG``, then
            ``./config.json5``).

    Returns:
        ``0`` on success, ``1`` on infrastructure error or unhealthy state.
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
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    # --- Open DB and apply pending migrations ---
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
    except (
        IndexerLockError,
        IndexerCorruptError,
        IndexerDiskFullError,
        IndexerInvalidPathError,
        IndexerMigrationError,
    ) as exc:
        typer.echo(str(exc), err=True)
        return 1

    from contextlib import closing  # noqa: PLC0415

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

        # --- Disk inventory ---
        disk_rows = conn.execute(
            "SELECT id, label, is_mounted, last_seen_at, merkle_root FROM disk ORDER BY label"
        ).fetchall()
        typer.echo(f"{'DISK':<20} {'MOUNTED':<10} {'LAST_SEEN':<20} {'MERKLE_ROOT'}")
        for d_id, label, is_mounted, last_seen_at, merkle_root in disk_rows:
            mounted_str = "yes" if is_mounted else "no"
            last_seen_str = str(last_seen_at) if last_seen_at is not None else "never"
            root_str = (merkle_root or "")[:12] if merkle_root else ""
            typer.echo(f"  {label:<18} {mounted_str:<10} {last_seen_str:<20} {root_str}")

        # --- Query latest successful scan ---
        row = conn.execute(
            "SELECT id, finished_at, status, generation, disk_filter FROM scan_run "
            "WHERE status = 'ok' ORDER BY finished_at DESC LIMIT 1"
        ).fetchone()

        if row is None:
            typer.echo("no scans yet")
        else:
            run_id, finished_at, status, generation, disk_filter = row
            disk_scope = f" (disk={disk_filter})" if disk_filter else ""
            typer.echo(
                f"latest scan: id={run_id}, finished_at={finished_at}, status={status},"
                f" generation={generation}{disk_scope}"
            )

        # --- Repair queue health ---
        from personalscraper.indexer import repair  # noqa: PLC0415

        oldest_pending_age_seconds, pending_depth = repair.get_queue_health(conn)
        if oldest_pending_age_seconds is None:
            oldest_label = "never"
        else:
            oldest_label = f"{oldest_pending_age_seconds // 3600}h"
        typer.echo(f"repair queue: depth={pending_depth}, oldest={oldest_label}")

        # --- Outbox pending depth ---
        outbox_depth = conn.execute("SELECT COUNT(*) FROM index_outbox WHERE status = 'pending'").fetchone()[0]
        typer.echo(f"outbox pending: {outbox_depth}")

        # --- Deleted items count ---
        deleted_count = conn.execute("SELECT COUNT(*) FROM deleted_item").fetchone()[0]
        typer.echo(f"deleted items: {deleted_count}")

        # --- Enrich-pending count ---
        enrich_pending = conn.execute(
            "SELECT COUNT(*) FROM media_file WHERE enriched_at IS NULL AND deleted_at IS NULL"
        ).fetchone()[0]
        typer.echo(f"enrich pending: {enrich_pending}")

        # --- Category-orphan count (DESIGN §17.2) ---
        known_ids: frozenset[str] = cfg.all_category_ids
        orphan_count: int = 0
        if known_ids:
            placeholders = ",".join("?" * len(known_ids))
            orphan_count = conn.execute(
                f"SELECT COUNT(*) FROM media_item WHERE category_id NOT IN ({placeholders})",
                list(known_ids),
            ).fetchone()[0]
        typer.echo(f"category orphans: {orphan_count}")

        # --- Health warnings ---
        unhealthy = False
        if oldest_pending_age_seconds is not None and oldest_pending_age_seconds > 7 * 86400 or pending_depth > 1000:
            typer.echo(
                f"WARNING: repair queue: depth={pending_depth},"
                f" oldest pending {(oldest_pending_age_seconds or 0) // 86400} days",
                err=True,
            )
            unhealthy = True

        if orphan_count > 0:
            typer.echo(
                f"WARNING: {orphan_count} media_item row(s) with unknown category_id. "
                "Run 'config migrate-category' to fix.",
                err=True,
            )
            unhealthy = True

        return 1 if unhealthy else 0


# ---------------------------------------------------------------------------
# library-index
# ---------------------------------------------------------------------------


def library_index_command(
    *,
    mode: str = "full",
    disk: str | None = None,
    budget_seconds: int | None = None,
    no_budget: bool = False,
    dry_run: bool = False,
    wait_for_lock_seconds: int = 0,
    config_path: Path | None = None,
    confirm_bulk_change: bool = False,
    rebuild: bool = False,
) -> int:
    """Run an indexer scan (full / quick / incremental / enrich) and print a JSON summary.

    Loads config, acquires the writer lock, opens (or creates) the indexer
    database, applies pending migrations, resolves the disk list, then calls
    :func:`~personalscraper.indexer.scanner.scan` with the requested mode.
    After the scan, :func:`~personalscraper.indexer.outbox.drain_if_present`
    is called so Phase 5 can hook in event dispatch without a signature change.

    Args:
        mode: Scan mode — ``"full"``, ``"quick"``, ``"incremental"``, or ``"enrich"``.
        disk: If provided, restrict the scan to the disk with this label.
            On ``IndexerConfigError("no disk with label 'X'")`` the error
            is printed to stderr and exit code 2 is returned.
        budget_seconds: Maximum wall-clock seconds for the scan.  ``None`` falls
            back to ``cfg.indexer.scan.budget_seconds`` (cron-friendly default).
        no_budget: When ``True``, ignore both ``budget_seconds`` and the config
            default and run with no wall-clock cap.  Use for manual passes that
            must drain every pending file in one go (full enrich after a cold
            Stage A walk); the writer lock is held for the full duration.
        dry_run: When ``True``, all DB writes are wrapped in a SQLite savepoint
            that is always rolled back so no rows are persisted.
        wait_for_lock_seconds: Seconds to wait for the writer lock before
            giving up.  ``0`` = fail immediately if locked.
        config_path: Optional explicit path to config.json5 or config
            directory.  When ``None`` the standard resolution order is used.
        confirm_bulk_change: When ``True``, bypass the Merkle delta freeze guard
            in quick mode.  Pass ``--confirm-bulk-change`` to enable.
        rebuild: When ``True`` (``--rebuild``), bypass the corrupt-DB refusal:
            quarantine the existing DB if any and create a fresh one, then run
            a full Stage-A rescan from scratch.  DESIGN §17.1.

    Returns:
        ``0`` on success, ``1`` on infrastructure error, ``2`` on unknown disk,
        ``3`` when a bulk-change freeze is triggered on a disk.
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
        indexer_lock,
        open_db,
    )
    from personalscraper.indexer.merkle import DiskBulkChangeDetected  # noqa: PLC0415
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
        rebuild=rebuild,
        no_budget=no_budget,
        config_path=str(config_path) if config_path else None,
    )

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    # --- Validate mode early (before acquiring the lock) ---
    try:
        scan_mode = ScanMode(mode)
    except ValueError:
        valid_modes = ", ".join(m.value for m in ScanMode)
        typer.echo(f"Invalid mode '{mode}'. Valid: {valid_modes}", err=True)
        return 1

    from contextlib import closing  # noqa: PLC0415

    # --- Acquire writer lock ---
    try:
        with indexer_lock(db_path, timeout=wait_for_lock_seconds):
            # --- Open DB and apply pending migrations ---
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                # Pass rebuild=True to open_db so a corrupt DB is quarantined and a
                # fresh one is created rather than raising IndexerCorruptError.
                conn = open_db(db_path, rebuild=rebuild)
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

                # --- Bootstrap disk table on first run if empty ---
                # When the DB is freshly created the ``disk`` table is empty.
                # Without bootstrapping, ``scan`` would silently do nothing.
                # We populate the table from ``Config.disks`` so that the
                # very first ``library-index --mode full`` works out of the box.
                disk_count_row = conn.execute("SELECT COUNT(*) FROM disk").fetchone()
                disk_table_empty: bool = disk_count_row[0] == 0
                disks_bootstrapped: int = 0
                if disk_table_empty and cfg.disks:
                    log.info(
                        "indexer.bootstrap.starting",
                        disk_count=len(cfg.disks),
                    )
                    disks_bootstrapped = _bootstrap_disks_from_config(conn, cfg.disks)
                    log.info(
                        "indexer.bootstrap.done",
                        disks_registered=disks_bootstrapped,
                    )

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
                    typer.echo(str(exc), err=True)
                    return 2

                # --- Allocate next scan generation ---
                gen_row = conn.execute("SELECT MAX(scan_generation) FROM media_file").fetchone()
                next_gen: int = (gen_row[0] or 0) + 1

                # --- Run scan (dry_run wraps writes in a rolled-back savepoint) ---
                if dry_run:
                    conn.execute("SAVEPOINT _dry_run")

                if no_budget:
                    effective_budget_seconds: int | None = None
                elif budget_seconds is not None:
                    effective_budget_seconds = budget_seconds
                else:
                    effective_budget_seconds = cfg.indexer.scan.budget_seconds

                try:
                    result = scan(
                        disks=filtered_disks,
                        mode=scan_mode,
                        generation=next_gen,
                        conn=conn,
                        disk_filter=disk,
                        drop_indexes=cfg.indexer.scan.drop_indexes_during_full_scan,
                        budget_seconds=effective_budget_seconds,
                        db_path=db_path,
                        checkpoint_every_n_files=cfg.indexer.scan.checkpoint_every_n_files,
                        confirm_bulk_change=confirm_bulk_change,
                        merkle_delta_freeze_threshold=cfg.indexer.drift.merkle_delta_freeze_threshold,
                        max_workers=cfg.indexer.scan.max_workers_total,
                        read_rate_mb_per_sec=cfg.indexer.scan.read_rate_mb_per_sec,
                        staging_dir=str(cfg.paths.staging_dir),
                        spotlight_enabled=cfg.indexer.spotlight.use_when_available,
                        paranoia_window_seconds=cfg.indexer.scan.paranoia_window_seconds,
                    )
                except DiskBulkChangeDetected as bulk_exc:
                    typer.echo(
                        f"disk {bulk_exc.disk_uuid!r} looks like a bulk restore "
                        f"({bulk_exc.delta:.0%} files changed). "
                        f"Re-run with --confirm-bulk-change to proceed.",
                        err=True,
                    )
                    if dry_run:
                        try:
                            conn.execute("ROLLBACK TO SAVEPOINT _dry_run")
                        except Exception:  # noqa: BLE001
                            pass
                    return 3
                except (IndexerCorruptError, IndexerDiskFullError) as exc:
                    typer.echo(str(exc), err=True)
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

                # --- Drain outbox ---
                drained = drain_if_present(conn, cfg.indexer)
                log.debug("indexer.cli.index.outbox_drained", count=drained)

                # --- Print JSON summary to stdout ---
                summary = {
                    "mode": scan_mode.value,
                    "files_walked": result.files_visited,
                    "dirs_walked": result.dirs_visited,
                    "disks_skipped": result.disks_skipped,
                    "disks_bootstrapped": disks_bootstrapped,
                    "scan_run_id": result.scan_run_id,
                    "status": result.status,
                    "budget_exhausted": False,
                    "dry_run": dry_run,
                    "rebuild": rebuild,
                }
                typer.echo(json.dumps(summary))
                return 0

    except IndexerLockError as exc:
        typer.echo(str(exc), err=True)
        return 1


# ---------------------------------------------------------------------------
# library-verify
# ---------------------------------------------------------------------------


def library_verify_command(
    *,
    disk: str | None = None,
    budget_seconds: float | None = None,
    config_path: Path | None = None,
) -> int:
    """Re-stat every indexed file and escalate mismatches to the repair queue.

    Wraps ``scan(mode='verify')`` for a targeted re-verification pass.  Unlike
    a full rescan, verify mode does NOT soft-delete missing files — it only marks
    them for repair so they can be investigated before any destructive action.

    Args:
        disk: Optional disk label to restrict verification to a single disk.
        budget_seconds: Maximum wall-clock seconds for the verify pass. ``None``
            means unlimited.  Per-file commit guarantees partial progress is
            preserved when the budget is exhausted; the next invocation
            resumes from rows whose ``last_verified_at`` is older than this run.
        config_path: Optional explicit path to config.json5 or config directory.

    Returns:
        ``0`` on success, ``1`` on infrastructure error, ``2`` on unknown disk.
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
        indexer_lock,
        open_db,
    )
    from personalscraper.indexer.scanner import (  # noqa: PLC0415
        IndexerConfigError,
        ScanMode,
        filter_disks,
        scan,
    )
    from personalscraper.indexer.schema import DiskRow  # noqa: PLC0415

    log.info("indexer.cli.verify", disk=disk)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    from contextlib import closing  # noqa: PLC0415

    try:
        with indexer_lock(db_path, timeout=0):
            try:
                db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = open_db(db_path)
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

                try:
                    filtered_disks = filter_disks(disks, disk)
                except IndexerConfigError as exc:
                    typer.echo(str(exc), err=True)
                    return 2

                gen_row = conn.execute("SELECT MAX(scan_generation) FROM media_file").fetchone()
                next_gen: int = (gen_row[0] or 0) + 1

                result = scan(
                    disks=filtered_disks,
                    mode=ScanMode.verify,
                    generation=next_gen,
                    conn=conn,
                    disk_filter=disk,
                    budget_seconds=budget_seconds,
                    merkle_delta_freeze_threshold=cfg.indexer.drift.merkle_delta_freeze_threshold,
                    paranoia_window_seconds=cfg.indexer.scan.paranoia_window_seconds,
                )

                summary = {
                    "mode": "verify",
                    "files_walked": result.files_visited,
                    "dirs_walked": result.dirs_visited,
                    "disks_skipped": result.disks_skipped,
                    "scan_run_id": result.scan_run_id,
                    "status": result.status,
                }
                typer.echo(json.dumps(summary))
                return 0

    except IndexerLockError as exc:
        typer.echo(str(exc), err=True)
        return 1


# ---------------------------------------------------------------------------
# library-search
# ---------------------------------------------------------------------------


def library_search_command(
    query_str: str,
    *,
    limit: int = 50,
    config_path: Path | None = None,
) -> int:
    """Execute a flex-attr query and print matching media items.

    Delegates to :func:`~personalscraper.indexer.query.execute` for tokenisation,
    SQL compilation, and execution.  Each matching item is printed as one
    space-padded row with the columns ``id | title | year | nfo``; the header
    row uses the same widths so columns line up in a fixed-width terminal.

    Args:
        query_str: Query string in the flex-attr syntax, e.g.
            ``"year:2024 disk:Disk1 -nfo:valid"``.
        limit: Maximum number of rows to return.  Defaults to 50.
        config_path: Optional explicit path to config.json5 or config directory.

    Returns:
        ``0`` on success (even with zero results), ``1`` on infrastructure error,
        ``2`` on query syntax / unknown-field error.
    """
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
    from personalscraper.indexer.query import QueryError, execute  # noqa: PLC0415

    log.info("indexer.cli.search", query=query_str, limit=limit)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    from contextlib import closing  # noqa: PLC0415

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
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

        try:
            items = execute(conn, query_str, limit=limit)
        except QueryError as exc:
            typer.echo(str(exc), err=True)
            return 2

        if not items:
            typer.echo("(no results)")
            return 0

        # Print header + rows. Widths must match between header and data so
        # columns align in a fixed-width terminal.
        typer.echo(f"{'ID':<8}{'TITLE':<40} {'YEAR':<6} {'NFO':<10}")
        for item in items:
            year_str = str(item.year) if item.year is not None else ""
            nfo_str = item.nfo_status or ""
            typer.echo(f"{item.id:<8}{(item.title or '')[:38]:<40} {year_str:<6} {nfo_str:<10}")

        return 0


# ---------------------------------------------------------------------------
# library-repair
# ---------------------------------------------------------------------------


def library_repair_command(
    *,
    budget_seconds: float = 60.0,
    config_path: Path | None = None,
) -> int:
    """Drain the repair queue within a wall-clock time budget.

    Delegates to :func:`~personalscraper.indexer.repair.drain`.  The noop
    processor is used by default (real handlers wired in later phases).

    Args:
        budget_seconds: Maximum wall-clock seconds to spend draining.
            Default ``60.0`` seconds.
        config_path: Optional explicit path to config.json5 or config directory.

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

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    from contextlib import closing  # noqa: PLC0415

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
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


def library_show_command(
    item_id: int,
    *,
    config_path: Path | None = None,
) -> int:
    """Pretty-print all stored data for a single media item.

    Prints:
    - ``media_item`` columns.
    - ``season`` / ``episode`` rows (for shows).
    - ``media_file`` rows with their ``media_stream`` rows.
    - ``item_attribute`` rows.
    - ``deleted_item`` history.

    Args:
        item_id: PK of the ``media_item`` to display.
        config_path: Optional explicit path to config.json5 or config directory.

    Returns:
        ``0`` on success, ``1`` on infrastructure error, ``2`` if no item with
        the given id exists.
    """
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

    log.info("indexer.cli.show", item_id=item_id)

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    from contextlib import closing  # noqa: PLC0415

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
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

        conn.row_factory = sqlite3.Row

        # --- Fetch media_item ---
        item_row = conn.execute("SELECT * FROM media_item WHERE id = ?", (item_id,)).fetchone()
        if item_row is None:
            typer.echo(f"no item with id {item_id}", err=True)
            return 2

        # --- Print media_item fields ---
        typer.echo(f"=== media_item id={item_id} ===")
        for key in item_row.keys():
            typer.echo(f"  {key}: {item_row[key]}")

        # --- Seasons and episodes (shows) ---
        seasons = conn.execute("SELECT * FROM season WHERE item_id = ? ORDER BY number", (item_id,)).fetchall()
        if seasons:
            typer.echo(f"\n=== seasons ({len(seasons)}) ===")
            for s in seasons:
                typer.echo(
                    f"  season {s['number']}: episodes={s['episode_count']}, "
                    f"has_poster={s['has_poster']}, nfo_count={s['episodes_with_nfo']}"
                )
                eps = conn.execute("SELECT * FROM episode WHERE season_id = ? ORDER BY number", (s["id"],)).fetchall()
                for ep in eps:
                    typer.echo(f"    episode {ep['number']}: {ep['title']}")

        # --- media_file rows ---
        files = conn.execute(
            "SELECT mf.*, p.rel_path, p.disk_id FROM media_file mf "
            "JOIN media_release mr ON mf.release_id = mr.id "
            "JOIN path p ON mf.path_id = p.id "
            "WHERE mr.item_id = ? ORDER BY mf.id",
            (item_id,),
        ).fetchall()
        if not files:
            # Fallback: try via path → disk without requiring a release link
            files = conn.execute(
                "SELECT mf.*, p.rel_path, p.disk_id FROM media_file mf "
                "JOIN path p ON mf.path_id = p.id "
                "WHERE p.disk_id IN (SELECT id FROM disk) "
                "AND mf.release_id IS NULL "
                "LIMIT 0"  # empty fallback — Stage A files may lack release linkage
            ).fetchall()

        if files:
            typer.echo(f"\n=== media_files ({len(files)}) ===")
            for f in files:
                typer.echo(
                    f"  file id={f['id']} {f['rel_path']}/{f['filename']}"
                    f" size={f['size_bytes']} mtime_ns={f['mtime_ns']}"
                )
                streams = conn.execute(
                    "SELECT * FROM media_stream WHERE file_id = ? ORDER BY idx",
                    (f["id"],),
                ).fetchall()
                for st in streams:
                    typer.echo(f"    stream idx={st['idx']} kind={st['kind']} codec={st['codec']} lang={st['lang']}")

        # --- item_attribute rows ---
        attrs = conn.execute(
            "SELECT key, value FROM item_attribute WHERE item_id = ? ORDER BY key",
            (item_id,),
        ).fetchall()
        if attrs:
            typer.echo(f"\n=== item_attributes ({len(attrs)}) ===")
            for a in attrs:
                typer.echo(f"  {a['key']}: {a['value']}")

        # --- deleted_item history ---
        deleted = conn.execute(
            "SELECT * FROM deleted_item WHERE original_id = ? ORDER BY deleted_at",
            (item_id,),
        ).fetchall()
        if deleted:
            typer.echo(f"\n=== deleted_item history ({len(deleted)}) ===")
            for d in deleted:
                typer.echo(f"  kind={d['kind']} deleted_at={d['deleted_at']} reason={d['reason']}")

        return 0


# ---------------------------------------------------------------------------
# config migrate-category
# ---------------------------------------------------------------------------


def config_migrate_category_command(
    *,
    from_category: str,
    to_category: str,
    config_path: Path | None = None,
) -> int:
    """Rewrite every ``media_item.category_id`` from *from_category* to *to_category*.

    Run this after renaming a category in ``categories.json5`` to clear orphan-tagged
    rows detected by ``library status``.  The command is idempotent: running twice
    with the same args is a no-op the second time.

    The operation is:

    1. Verify ``to_category`` is a declared category id in ``Config.all_category_ids``
       (i.e. the rename has already been applied to the config).  Exit 2 if not.
    2. Issue ``UPDATE media_item SET category_id = ? WHERE category_id = ?`` inside
       a single transaction.
    3. Print the number of rows updated.

    Args:
        from_category: The old category_id string to replace (may or may not still
            be in the config — it is the source of the orphan rows).
        to_category: The new category_id string to write.  Must be a declared id
            in the current config.
        config_path: Optional explicit path to config.json5 or config directory.

    Returns:
        ``0`` on success (including no-op when zero rows matched), ``1`` on
        infrastructure error, ``2`` when ``to_category`` is not a declared id.
    """
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

    log.info(
        "indexer.cli.migrate_category",
        from_category=from_category,
        to_category=to_category,
    )

    # --- Load config ---
    try:
        cfg = load_config(resolve_config_path(config_path))
    except (ConfigNotFoundError, ConfigValidationError) as exc:
        typer.echo(f"Config error: {exc}", err=True)
        return 1

    # --- Validate to_category is a declared id ---
    known_ids: frozenset[str] = cfg.all_category_ids
    if to_category not in known_ids:
        known_sorted = ", ".join(sorted(known_ids))
        typer.echo(
            f"unknown category '{to_category}'; declared ids: {known_sorted}",
            err=True,
        )
        return 2

    db_path: Path = cfg.indexer.db_path
    migrations_dir = Path(_migrations_pkg.__file__).parent

    from contextlib import closing  # noqa: PLC0415

    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = open_db(db_path)
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

        # --- Execute the migration in a transaction ---
        conn.execute("BEGIN")
        try:
            cur = conn.execute(
                "UPDATE media_item SET category_id = ? WHERE category_id = ?",
                (to_category, from_category),
            )
            updated = cur.rowcount
            conn.execute("COMMIT")
        except Exception as exc:  # noqa: BLE001
            conn.execute("ROLLBACK")
            typer.echo(f"migration failed: {exc}", err=True)
            return 1

        if updated == 0:
            typer.echo(f"no rows matched category_id='{from_category}' (already migrated or no such rows)")
        else:
            typer.echo(f"updated {updated} media_item row(s): '{from_category}' → '{to_category}'")

        return 0
