"""Dispatch step runner: entry point for the dispatch pipeline step.

Instantiates the Dispatcher and MediaIndex, processes verified items,
and converts DispatchResult to StepReport. In standalone mode (no
verified list provided), runs verify first to obtain dispatchable items.

staging_dir is passed explicitly from Config.paths; Settings no longer
carries disk paths.
"""

from dataclasses import asdict
from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.delete_permit import AllowAllPermit, DeletePermit, SeedObligationRecorder
from personalscraper.core.event_bus import EventBus
from personalscraper.dispatch._types import DispatchResult
from personalscraper.dispatch.crash_recovery import DryRunPolicy, RootKind, SweepRoot, sweep_orphans
from personalscraper.dispatch.disk_scanner import get_disk_configs
from personalscraper.dispatch.dispatcher import Dispatcher
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.logger import get_logger
from personalscraper.models import StepReport
from personalscraper.pipeline_events import ItemProgressed
from personalscraper.pipeline_protocol import record
from personalscraper.reports.dispatch import DispatchDetails
from personalscraper.verify.verifier import VerifyResult

log = get_logger("dispatch_run")


def _sweep_dispatch_orphans(
    config: Config,
    staging_dir: Path,
    *,
    dry_run: bool,
    recover_orphans: bool,
) -> int:
    """Sweep dispatch orphans via the single-owner crash-recovery sweep.

    Standalone ``personalscraper dispatch`` (``recover_orphans=True``) is the
    dispatch step's own crash-recovery entry point, so it sweeps both the
    staging categories (``.merge_backup/`` + ``_tmp_dispatch_*``) and the
    storage disks. In a full pipeline run the boot-time
    :meth:`Pipeline._recover_from_previous_run` already owns that sweep, so the
    :class:`~personalscraper.pipeline_steps.DispatchStep` passes
    ``recover_orphans=False`` and this returns 0 (no double-execution).

    Staging roots carry ``SKIP`` (invisible in dry-run, matching the historical
    ``_cleanup_staging_orphans`` gate); storage roots carry ``REPORT`` so
    ``dispatch --dry-run`` stays side-effect-free yet lists what it would clean.

    Args:
        config: Application config providing the storage disks.
        staging_dir: Absolute path to the staging area (from ``Config.paths``).
        dry_run: Whether the dispatch step is a preview.
        recover_orphans: When False, boot already swept — do nothing.

    Returns:
        Number of orphan directories removed (or counted in dry-run REPORT).
    """
    if not recover_orphans:
        return 0
    roots = [SweepRoot(staging_dir, RootKind.MEDIA_TREE, DryRunPolicy.SKIP)]
    roots.extend(SweepRoot(disk.path, RootKind.MEDIA_TREE, DryRunPolicy.REPORT) for disk in get_disk_configs(config))
    return sweep_orphans(roots, dry_run=dry_run)


def run_dispatch(
    settings: Settings,
    config: "Config",
    dry_run: bool = False,
    verified: list[VerifyResult] | None = None,
    *,
    event_bus: EventBus,
    permit: DeletePermit = AllowAllPermit(),
    recorder: SeedObligationRecorder = AllowAllPermit(),
    recover_orphans: bool = True,
) -> tuple[StepReport, list[DispatchResult]]:
    """Run the dispatch pipeline step.

    Args:
        settings: Pipeline configuration (thresholds, API keys).
        config: Config with disk layout and paths.
        dry_run: If True, preview without transferring files.
        verified: Verified items from the verify step (pipeline mode).
            If None, runs verify first to obtain dispatchable items.
        event_bus: Required in-process EventBus. Each per-item
            lifecycle transition emits an ``ItemProgressed`` event on the bus.
            Also forwarded to ``MediaIndex`` so ``open_db``'s pre-open
            free-space guard emits ``DiskFullWarning`` on the same bus.
        permit: Injected :class:`DeletePermit` forwarded to
            :class:`Dispatcher` (default: ``AllowAllPermit`` — always permit).
        recorder: Injected :class:`SeedObligationRecorder` forwarded to
            :class:`Dispatcher` (default: ``AllowAllPermit`` — no-op).
        recover_orphans: When True (standalone dispatch), run the crash-recovery
            orphan sweep before dispatching. The full-run
            :class:`~personalscraper.pipeline_steps.DispatchStep` passes False
            because boot already swept once per run (PIPELINE-CORE-07).

    Returns:
        ``(StepReport, list[DispatchResult])`` — the step report with
        counts/details for CLI output, and the raw per-item results for
        post-dispatch processing (touched-disk collection).
    """
    staging_dir = config.paths.staging_dir
    # Dispatch must consult the same indexer DB populated by ``library-index``
    # and the outbox publishers.  ``paths.data_dir`` can differ from the
    # indexer storage directory in the split config layout.
    index_path = config.indexer.db_path
    assert index_path is not None, "indexer.db_path must be resolved"

    # Crash-recovery orphan sweep (single owner). Standalone dispatch owns its
    # own sweep; inside a full pipeline run boot already swept
    # (``recover_orphans=False`` ⇒ no double-execution).
    cleaned = _sweep_dispatch_orphans(config, staging_dir, dry_run=dry_run, recover_orphans=recover_orphans)

    report = StepReport(name="dispatch")

    with MediaIndex(index_path, config=config, auto_rebuild=not dry_run, event_bus=event_bus) as index:
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
                disk_configs = get_disk_configs(config)
                count = index.rebuild(disk_configs, categories=config.categories)
                event = "index_rebuilt_on_empty_preview" if dry_run else "index_rebuilt_on_empty"
                log.info(event, entries=count)

            dispatcher = Dispatcher(
                config=config,
                settings=settings,
                index=index,
                dry_run=dry_run,
                event_bus=event_bus,
                permit=permit,
                recorder=recorder,
            )

            if verified is None:
                # Standalone mode: run verify first to get dispatchable items
                from personalscraper.verify.run import run_verify

                _, verified = run_verify(settings, config, dry_run=dry_run, event_bus=event_bus)

            results = dispatcher.process(verified=verified)

            # Terminal per-item progress + report counters. ``started`` is
            # emitted from INSIDE ``Dispatcher.process`` (F8 real lifecycle);
            # here we record only the terminal transition, which drives both the
            # ``ItemProgressed`` payload and the report counters through the
            # shared ``record`` reporter (replaces the old report-conversion helper).
            for r in results:
                _record_dispatch_terminal(report, event_bus, r)

            # Typed details payload (STEP_REPORT_CONTRACT: DispatchDetails).
            # Flattened to a JSON-safe dict here so the report is self-consistent
            # on the standalone CLI path too (the pipeline re-validates it in
            # ``Pipeline._with_details_payload``).
            report.details_payload = asdict(_build_dispatch_details(results))

            # Drain the outbox so that write-through events emitted during
            # dispatch (move/upsert) are applied to the indexer DB immediately
            # rather than waiting for the next nightly scan.
            if not dry_run:
                _drain_dispatch_outbox(config)
                _enrich_after_dispatch(config, results, event_bus=event_bus)
        finally:
            if preview_index:
                index.rollback_preview()

    if cleaned:
        # Honest, French label (§2/§8 — libellé clair, rien en silence). The
        # sweep covers BOTH the staging categories AND the storage disks, so the
        # former "staging orphan(s)" wording mislabelled disk orphans. In dry-run
        # only the storage roots REPORT (staging is SKIP) and nothing is deleted,
        # so the preview says "à nettoyer", not "nettoyé(s)".
        if dry_run:
            report.details.insert(0, f"{cleaned} orphelin(s) de dispatch à nettoyer (aperçu — disques de stockage)")
        else:
            report.details.insert(0, f"{cleaned} orphelin(s) de dispatch nettoyé(s) (staging + disques)")
    return report, results


def _build_dispatch_details(results: list[DispatchResult]) -> DispatchDetails:
    """Build the typed :class:`DispatchDetails` payload from dispatch results.

    Partitions by action: ``moved`` items are grouped under their destination
    disk (``moved_to_disk[disk] -> [name, ...]``); ``merged``/``replaced`` land
    in their own lists; ``error`` items become ``(name, reason)`` pairs. Unknown
    actions are not represented (they touch no counter — see
    ``_record_dispatch_terminal``).

    Args:
        results: Per-item dispatch results from ``Dispatcher.process``.

    Returns:
        A :class:`DispatchDetails` grouping items by dispatch outcome.
    """
    details = DispatchDetails()
    for r in results:
        name = r.source.name
        if r.action == "moved":
            details.moved_to_disk.setdefault(r.disk or "", []).append(name)
        elif r.action == "merged":
            details.merged.append(name)
        elif r.action == "replaced":
            details.replaced.append(name)
        elif r.action == "error":
            details.failed.append((name, r.reason or ""))
    return details


def _record_dispatch_terminal(report: StepReport, bus: EventBus, r: DispatchResult) -> None:
    """Record one dispatch result's terminal ``ItemProgressed`` + report counter.

    Preserves the exact counter/details/warning semantics of the former
    the former report-conversion helper + post-hoc event loop:

    * ``replaced`` / ``merged`` / ``moved`` → ``success_count``; detail
      ``action=<pad8> <name> → <disk>``; event payload ``{dest, disk}``.
    * ``skipped`` → ``skip_count``; detail ``action=skipped  <name>: <reason>``;
      warning appended only when a reason is present; event payload ``{reason}``.
    * ``error`` → ``error_count``; detail ``action=error    <name>: <reason>``;
      warning always appended; event payload ``{action, reason}``.
    * any other (unknown) action → emits an ``error`` event WITHOUT touching any
      counter (matches the former report-conversion helper.s fall-through).

    Args:
        report: Dispatch step report mutated in place.
        bus: Required in-process EventBus.
        r: One dispatch result.
    """
    name = r.source.name
    # Action tags use a leading "action=" prefix (not "[action]") because
    # Rich console.print() would silently swallow bracketed tokens as markup.
    if r.action in ("replaced", "merged", "moved"):
        record(
            report,
            bus,
            step="dispatch",
            item=name,
            status=r.action,
            detail=f"action={r.action:<8} {name} → {r.disk}",
            event_details={"dest": str(r.destination) if r.destination else "", "disk": r.disk or ""},
        )
    elif r.action == "skipped":
        record(
            report,
            bus,
            step="dispatch",
            item=name,
            status="skipped",
            detail=f"action=skipped  {name}: {r.reason}",
            warning=f"{name}: {r.reason}" if r.reason else None,
            event_details={"reason": r.reason or ""},
        )
    elif r.action == "error":
        record(
            report,
            bus,
            step="dispatch",
            item=name,
            status="error",
            detail=f"action=error    {name}: {r.reason}",
            warning=f"{name}: {r.reason or 'unknown error'}",
            event_details={"action": r.action, "reason": r.reason or ""},
        )
    else:
        # Unknown action: surface an error event but leave every counter
        # untouched (the former report-conversion helper had no branch for it).
        bus.emit(
            ItemProgressed(
                step="dispatch",
                item=name,
                status="error",
                details={"action": r.action, "reason": r.reason or ""},
            )
        )


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

    from personalscraper.indexer.db import _apply_pragmas
    from personalscraper.indexer.outbox._drain import drain_if_present
    from personalscraper.indexer.repos.disk_repo import update_merkle_root

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
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


def _enrich_after_dispatch(config: Config, results: list[DispatchResult], *, event_bus: EventBus) -> None:
    """Run an enrich scan on every disk that received files during dispatch.

    Newly dispatched files land in the indexer DB with ``enriched_at=NULL``.
    Without this pass the indexer would lack stream metadata, release linkage
    (season/episode rows), NFO status, and artwork inventory until the next
    scheduled ``library-index --mode enrich`` run — a temporal gap that breaks
    the contract of "the index is always up-to-date after dispatch."

    Args:
        config: Application config providing the indexer DB path.
        results: Dispatch results from the current step; affected disk IDs
            are derived from the ``moved`` / ``replaced`` / ``merged``
            entries.
        event_bus: Required :class:`EventBus` forwarded to the indexer
            ``scan`` call so its breaker emits + ``LibraryScanCompleted``
            event reach subscribers (Sub-phase 5.2).
    """
    import sqlite3

    from personalscraper.indexer.db import _apply_pragmas
    from personalscraper.indexer.repos import disk_repo
    from personalscraper.indexer.scanner import ScanMode, ScanRequest, scan_with
    from personalscraper.indexer.schema import DiskRow

    affected_ids: set[str] = {r.disk for r in results if r.disk and r.action in ("replaced", "merged", "moved")}
    if not affected_ids:
        return

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
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
        result = scan_with(
            ScanRequest(
                disks=disk_rows,
                mode=ScanMode.enrich,
                generation=next_generation,
                conn=conn,
                event_bus=event_bus,
            )
        )
        log.info(
            "dispatch_post_enrich_done",
            files_visited=result.files_visited,
            status=result.status,
        )
    finally:
        conn.close()
