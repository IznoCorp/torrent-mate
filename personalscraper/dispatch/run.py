"""Dispatch step runner: entry point for the dispatch pipeline step.

Instantiates the Dispatcher and MediaIndex, processes verified items,
and converts DispatchResult to StepReport. In standalone mode (no
verified list provided), runs verify first to obtain dispatchable items.

staging_dir is passed explicitly from Config.paths; Settings no longer
carries disk paths.
"""

import shutil
from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.pipeline_observer import PipelineObserver
from personalscraper.sorter.file_type import FileType
from personalscraper.verify.verifier import VerifyResult

log = get_logger("dispatch_run")


def _cleanup_staging_orphans(settings: Settings, config: Config, staging_dir: Path) -> int:
    """Remove orphaned dispatch temp dirs from staging categories.

    Cleans up _tmp_dispatch_* directories and .merge_backup/
    subdirectories that were left behind by interrupted dispatches.

    Args:
        settings: Pipeline configuration (provides dir name attributes).
        config: Application config for category-based dir name resolution.
        staging_dir: Absolute path to the staging area (from Config.paths).

    Returns:
        Number of orphan directories removed.
    """
    cleaned = 0
    staging = staging_dir
    for dir_name in (
        folder_name(find_by_file_type(config, FileType.MOVIE)),
        folder_name(find_by_file_type(config, FileType.TVSHOW)),
    ):
        cat_dir = staging / dir_name
        if not cat_dir.exists():
            continue
        for item in cat_dir.iterdir():
            if not item.is_dir():
                continue
            # Clean _tmp_dispatch_* orphans
            if item.name.startswith("_tmp_dispatch_"):
                try:
                    shutil.rmtree(item)
                    log.warning("staging_orphan_cleaned", name=item.name)
                    cleaned += 1
                except OSError as exc:
                    log.warning("staging_orphan_cleanup_failed", name=item.name, error=str(exc))
            # Clean .merge_backup/ inside media dirs
            backup = item / ".merge_backup"
            if backup.exists() and backup.is_dir():
                try:
                    shutil.rmtree(backup)
                    log.warning("staging_backup_cleaned", media=item.name, backup=backup.name)
                    cleaned += 1
                except OSError as exc:
                    log.warning("staging_backup_cleanup_failed", path=str(backup), error=str(exc))
    return cleaned


def run_dispatch(
    settings: Settings,
    config: "Config",
    dry_run: bool = False,
    verified: list[VerifyResult] | None = None,
    observers: tuple[PipelineObserver, ...] = (),
) -> StepReport:
    """Run the dispatch pipeline step.

    Args:
        settings: Pipeline configuration (thresholds, API keys).
        config: Config with disk layout and paths.
        dry_run: If True, preview without transferring files.
        verified: Verified items from the verify step (pipeline mode).
            If None, runs verify first to obtain dispatchable items.

    Returns:
        StepReport with dispatch counts and details.
    """
    staging_dir = config.paths.staging_dir
    # Dispatch must consult the same indexer DB populated by ``library-index``
    # and the outbox publishers.  ``paths.data_dir`` can differ from the
    # indexer storage directory in the split config layout.
    index_path = config.indexer.db_path
    assert index_path is not None, "indexer.db_path must be resolved"

    # Clean orphaned temp dirs from staging area
    cleaned = 0
    if not dry_run:
        cleaned = _cleanup_staging_orphans(settings, config, staging_dir)

    with MediaIndex(index_path, config=config, auto_rebuild=not dry_run) as index:
        preview_index = False
        if dry_run:
            index.begin_preview()
            preview_index = True

        try:
            # Log index freshness at entry so dry-run reviews know whether the plan
            # is computed against a fresh or cached index.
            index_source = "cache" if index.count > 0 else "empty"
            log.info("dispatch_index_state", entries=index.count, source=index_source, path=str(index_path))

            # Rebuild index if empty (first run or corrupted) to detect existing media
            # on all disks. Without this, all items are treated as "new" and sent
            # to the disk with most free space, ignoring existing series/movies.
            # Dry-run rebuilds are wrapped in a savepoint and rolled back so
            # preview commands never persist cache mutations.
            if index.count == 0:
                from personalscraper.dispatch.disk_scanner import get_disk_configs

                disk_configs = get_disk_configs(config)
                count = index.rebuild(disk_configs, categories=config.categories)
                event = "index_rebuilt_on_empty_preview" if dry_run else "index_rebuilt_on_empty"
                log.info(event, entries=count)

            dispatcher = Dispatcher(config=config, settings=settings, index=index, dry_run=dry_run)

            if verified is None:
                # Standalone mode: run verify first to get dispatchable items
                from personalscraper.verify.run import run_verify

                _, verified = run_verify(settings, config, dry_run=dry_run)

            results = dispatcher.process(verified=verified)

            # Drain the outbox so that write-through events emitted during
            # dispatch (move/upsert) are applied to the indexer DB immediately
            # rather than waiting for the next nightly scan.
            if not dry_run:
                _drain_dispatch_outbox(config)
                _enrich_after_dispatch(config, results)
        finally:
            if preview_index:
                index.rollback_preview()

    report = _to_step_report(results)
    if cleaned:
        report.details.insert(0, f"Cleaned {cleaned} staging orphan(s)")
    return report


def _drain_dispatch_outbox(config: Config) -> None:
    """Drain the indexer outbox and refresh Merkle roots after dispatch.

    Opens a short-lived connection to ``config.indexer.db_path``, drains
    any pending outbox rows, then resets ``disk.merkle_root`` to NULL for
    every mounted disk.  The next ``library-index --mode quick`` will
    recompute each root from the current DB state instead of detecting a
    bulk change and freezing (the dispatch intentionally modifies every
    disk, so a high delta is expected).

    Args:
        config: Validated Config with a resolved ``indexer.db_path``.
    """
    import sqlite3

    from personalscraper.indexer.outbox._drain import drain_if_present
    from personalscraper.indexer.repos.disk_repo import update_merkle_root

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    conn = sqlite3.connect(str(db_path))
    try:
        applied = drain_if_present(conn, config.indexer)
        if applied:
            log.info("dispatch_outbox_drained", applied=applied)

        # Reset Merkle roots so the next quick scan recomputes from the
        # (now up-to-date) DB rather than detecting a spurious bulk change.
        disk_ids = conn.execute("SELECT id FROM disk WHERE is_mounted = 1").fetchall()
        for (disk_id,) in disk_ids:
            update_merkle_root(conn, disk_id, None)
        if disk_ids:
            log.info("dispatch_merkle_reset", disk_count=len(disk_ids))
    finally:
        conn.close()


def _enrich_after_dispatch(config: Config, results: list[DispatchResult]) -> None:
    """Run an enrich scan on every disk that received files during dispatch.

    Newly dispatched files land in the indexer DB with ``enriched_at=NULL``.
    Without this pass the indexer would lack stream metadata, release linkage
    (season/episode rows), NFO status, and artwork inventory until the next
    scheduled ``library-index --mode enrich`` run — a temporal gap that breaks
    the contract of "the index is always up-to-date after dispatch."

    Args:
        config: Validated Config with a resolved ``indexer.db_path``.
        results: Dispatch results from the just-completed run.
    """
    import sqlite3

    from personalscraper.indexer.repos import disk_repo
    from personalscraper.indexer.scanner import scan as _indexer_scan
    from personalscraper.indexer.schema import DiskRow

    affected_ids: set[str] = {r.disk for r in results if r.disk and r.action in ("replaced", "merged", "moved")}
    if not affected_ids:
        return

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    conn = sqlite3.connect(str(db_path))
    try:
        disk_rows: list[DiskRow] = []
        for disk_id in affected_ids:
            row = disk_repo.get_by_uuid(conn, disk_id)
            if row is not None:
                disk_rows.append(row)
        if not disk_rows:
            return

        gen_row = conn.execute("SELECT COALESCE(MAX(generation), 0) FROM scan_run").fetchone()
        next_generation: int = (gen_row[0] or 0) + 1

        log.info(
            "dispatch_post_enrich_start",
            disks=[d.label for d in disk_rows],
            affected_item_count=len(affected_ids),
        )
        result = _indexer_scan(
            disks=disk_rows,
            mode="enrich",  # type: ignore[arg-type]
            generation=next_generation,
            conn=conn,
        )
        log.info(
            "dispatch_post_enrich_done",
            files_visited=result.files_visited,
            status=result.status,
        )
    finally:
        conn.close()


def _to_step_report(results: list[DispatchResult]) -> StepReport:
    """Convert DispatchResult list to StepReport.

    Args:
        results: List of dispatch results.

    Returns:
        StepReport with aggregated counts.
    """
    success = 0
    skipped = 0
    errors = 0
    warnings: list[str] = []
    details: list[str] = []

    # Action tags use a leading "action=" prefix (not "[action]") because
    # Rich console.print() would silently swallow bracketed tokens as markup.
    for r in results:
        name = r.source.name
        if r.action in ("replaced", "merged", "moved"):
            success += 1
            details.append(f"action={r.action:<8} {name} → {r.disk}")
        elif r.action == "skipped":
            skipped += 1
            details.append(f"action=skipped  {name}: {r.reason}")
            if r.reason:
                warnings.append(f"{name}: {r.reason}")
        elif r.action == "error":
            errors += 1
            details.append(f"action=error    {name}: {r.reason}")
            warnings.append(f"{name}: {r.reason or 'unknown error'}")

    return StepReport(
        name="dispatch",
        success_count=success,
        skip_count=skipped,
        error_count=errors,
        warnings=warnings,
        details=details,
    )
