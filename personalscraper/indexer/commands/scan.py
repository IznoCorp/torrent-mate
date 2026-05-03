"""Scan and reconciliation indexer command functions."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import typer

from personalscraper.indexer import cli as cli_compat
from personalscraper.logger import get_logger

log = get_logger("indexer.cli")


def library_index_command(
    *,
    mode: str = "full",
    disk: str | None = None,
    budget_seconds: int | None = None,
    no_budget: bool = False,
    backfill_streams: bool = False,
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
        backfill_streams: When ``True`` and ``mode == "enrich"``, runs the
            targeted backfill that re-extracts streams only for files whose
            ``media_stream`` rows are missing migration-004 columns and
            UPDATEs only those columns in place. Rejected with exit code 1
            when paired with any other mode.
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
    from personalscraper.indexer.outbox._drain import drain_if_present  # noqa: PLC0415
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

    db_path = cfg.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    migrations_dir = Path(_migrations_pkg.__file__).parent

    # --- Validate mode early (before acquiring the lock) ---
    try:
        scan_mode = ScanMode(mode)
    except ValueError:
        valid_modes = ", ".join(m.value for m in ScanMode)
        typer.echo(f"Invalid mode '{mode}'. Valid: {valid_modes}", err=True)
        return 1

    # --backfill-streams only makes sense for enrich mode (it targets
    # already-enriched files whose stream rows lack the new columns).
    if backfill_streams and scan_mode != ScanMode.enrich:
        typer.echo("--backfill-streams requires --mode enrich", err=True)
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
                    disks_bootstrapped = cli_compat._bootstrap_disks_from_config(conn, cfg.disks)
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
                        backfill_streams=backfill_streams,
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

                # --- Apply soft-deletes (per disk, post-walk) ---
                # Files that exceeded the miss-strike threshold during the
                # walk are now finalised: deleted_at is set, a deleted_item
                # tombstone is inserted (atomic via SAVEPOINT in
                # drift.apply_soft_deletes).  Skipped on dry_run, on
                # verify mode (which by contract does NOT soft-delete),
                # and on quick mode (no strikes accumulated this walk).
                soft_deleted = 0
                if not dry_run and scan_mode in (ScanMode.full, ScanMode.incremental):
                    from personalscraper.indexer.drift import apply_soft_deletes  # noqa: PLC0415

                    n_strikes = int(cfg.indexer.scan.n_strikes_for_softdelete)
                    for d in filtered_disks:
                        try:
                            soft_deleted += apply_soft_deletes(conn, d.id, n_strikes)
                        except sqlite3.Error as soft_exc:
                            log.warning(
                                "indexer.cli.index.soft_delete_failed",
                                disk_id=d.id,
                                error=str(soft_exc),
                                error_type=type(soft_exc).__name__,
                            )
                    if soft_deleted:
                        conn.commit()

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
                    "soft_deleted": soft_deleted,
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


def library_reconcile_command(
    *,
    scopes: Sequence[str] | None = None,
    enqueue_repairs: bool = False,
    config_path: Path | None = None,
) -> int:
    """Detect index ↔ filesystem divergences without a full rescan.

    Runs the DB-only checks in :mod:`personalscraper.indexer.reconcile`
    and prints a JSON summary of findings.  When ``enqueue_repairs`` is
    True, every divergence is also pushed into ``repair_queue`` so that
    ``library-repair`` can drain them with a wall-clock budget.  The
    partial UNIQUE INDEX from migration 003 deduplicates findings the
    last reconcile already enqueued, so re-running is safe.

    Args:
        scopes: Subset of detector scopes to run.  ``None`` runs all six
            (``merkle``, ``dispatch_path``, ``enrich``, ``release``,
            ``season``, ``item``).
        enqueue_repairs: When True, push findings into ``repair_queue``.
        config_path: Optional explicit path to config.json5 or config dir.

    Returns:
        ``0`` on success, ``1`` on infrastructure error.
    """
    import json  # noqa: PLC0415
    from typing import cast  # noqa: PLC0415

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
    from personalscraper.indexer.reconcile import (  # noqa: PLC0415
        ReconcileScope,
        reconcile,
    )

    log.info("indexer.cli.reconcile", scopes=list(scopes) if scopes else None, enqueue=enqueue_repairs)

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

        # Type cast: typer hands us Sequence[str], reconcile() requires the
        # narrower Literal-typed list.  The detector itself silently ignores
        # unknown scope strings so the cast is safe at runtime — invalid
        # values surface as "no detector ran" rather than a TypeError.
        report = reconcile(
            conn,
            scopes=cast("list[ReconcileScope]", list(scopes)) if scopes else None,
            enqueue_repairs=enqueue_repairs,
        )
        if enqueue_repairs:
            conn.commit()

        summary = {
            "merkle_drift": report.merkle_drift,
            "dispatch_path_missing_count": len(report.dispatch_path_missing),
            "dispatch_path_missing_sample": report.dispatch_path_missing[:10],
            "enrich_stale": report.enrich_stale,
            "release_orphans_count": len(report.release_orphans),
            "release_orphans_sample": report.release_orphans[:10],
            "files_without_release": report.files_without_release,
            "season_count_drift_count": len(report.season_count_drift),
            "season_count_drift_sample": report.season_count_drift[:10],
            "items_without_files_count": len(report.items_without_files),
            "items_without_files_sample": report.items_without_files[:10],
            "total_findings": report.total_findings,
            "enqueued_repairs": report.enqueued_repairs,
        }
        typer.echo(json.dumps(summary, indent=2))
        return 0


# ---------------------------------------------------------------------------
# library-repair
# ---------------------------------------------------------------------------
