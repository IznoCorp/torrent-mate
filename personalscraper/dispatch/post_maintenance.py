"""Post-dispatch index maintenance hook.

After ``dispatch`` moves media onto the storage disks, the indexer database
lags reality: new ``media_file`` rows have ``release_id IS NULL`` and season
``episode_count`` may be stale.  This module provides a single reusable
function that runs a scoped, sequential index-maintenance sequence so the
library index is coherent without a manual operator step.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.dispatch._types import DispatchResult

_log = get_logger("dispatch.post_maintenance")


def collect_touched_disks(results: list) -> set[str]:  # type: ignore[type-arg]
    """Collect distinct, non-None disk labels from dispatch results.

    Extracts the ``disk`` attribute from every :class:`DispatchResult` whose
    ``action`` is ``moved``, ``merged``, or ``replaced``.

    Args:
        results: Raw per-item dispatch results from :func:`run_dispatch`.

    Returns:
        Distinct set of disk labels (e.g. ``{"disk_1", "disk_2"}``). Empty
        set if no items were actually dispatched.
    """
    return {r.disk for r in results if r.disk is not None and r.action in ("moved", "merged", "replaced")}


def collect_touched_destinations(results: list) -> dict[str, set[Path]]:  # type: ignore[type-arg]
    """Collect dispatched destination paths per disk label.

    Args:
        results: Raw per-item dispatch results from :func:`run_dispatch`.

    Returns:
        Mapping ``disk label -> set of destination paths`` for every result
        whose ``action`` is ``moved``/``merged``/``replaced`` and that carries
        both a disk and a destination.
    """
    touched: dict[str, set[Path]] = {}
    for r in results:
        if r.disk is not None and r.destination is not None and r.action in ("moved", "merged", "replaced"):
            touched.setdefault(r.disk, set()).add(Path(r.destination))
    return touched


def _rel_path_variants(rel_path: str) -> set[str]:
    """Return the NFC and NFD spellings of *rel_path* (macFUSE stores NFD).

    Args:
        rel_path: A path string relative to a disk mount.

    Returns:
        The distinct normalization variants (1 or 2 strings).
    """
    import unicodedata

    return {unicodedata.normalize("NFC", rel_path), unicodedata.normalize("NFD", rel_path)}


def _invalidate_dispatched_subtrees(config: Config, destinations: dict[str, set[Path]]) -> int:
    """Force the next scan to re-walk every dispatched destination subtree.

    The incremental scan short-circuits a subtree whose recorded ``dir_mtime``
    is unchanged — and on NTFS/macFUSE, MERGING files into an existing show
    folder does not reliably bump the parent chain's mtimes, so freshly
    dispatched episodes stayed invisible to the index (prod: American Dad
    S22E10/E11 unindexed for 11 days; HotD S03E04 unindexed right after its
    run). Resetting ``dir_mtime_ns`` + ``last_walked_at`` on the destination
    subtree AND its ancestors (and clearing the disk merkle root) removes
    every short-circuit on the exact branches dispatch just touched.

    Fail-soft: any error is logged and 0 is returned — the scans still run.

    Args:
        config: Validated application Config.
        destinations: Mapping ``disk label -> destination paths`` from
            :func:`collect_touched_destinations`.

    Returns:
        Number of ``path`` rows invalidated.
    """
    from personalscraper.indexer.db import _apply_pragmas

    db_path = config.indexer.db_path
    if db_path is None or not destinations:
        return 0

    invalidated = 0
    try:
        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    except sqlite3.Error as exc:
        _log.warning("post_maintenance_invalidate_open_failed", error=str(exc))
        return 0
    try:
        _apply_pragmas(conn)
        conn.execute("BEGIN IMMEDIATE")
        disk_rows = {
            label: (disk_id, Path(mount))
            for disk_id, label, mount in conn.execute(
                "SELECT id, label, mount_path FROM disk WHERE mount_path IS NOT NULL"
            )
        }
        for label, dests in destinations.items():
            row = disk_rows.get(label)
            if row is None:
                _log.warning("post_maintenance_invalidate_unknown_disk", disk=label)
                continue
            disk_id, mount = row
            for dest in dests:
                try:
                    rel = str(Path(dest).relative_to(mount))
                except ValueError:
                    _log.warning("post_maintenance_invalidate_outside_mount", disk=label, dest=str(dest))
                    continue
                # In both unicode normalizations (macFUSE yields NFD): the
                # destination SUBTREE is reset by prefix, its ANCESTORS exactly
                # (a prefix reset on an ancestor would needlessly re-walk every
                # sibling show on the disk).
                for variant in _rel_path_variants(rel):
                    cur = conn.execute(
                        "UPDATE path SET dir_mtime_ns = NULL, last_walked_at = NULL "
                        "WHERE disk_id = ? AND (rel_path = ? OR rel_path LIKE ? || '/%')",
                        (disk_id, variant, variant),
                    )
                    invalidated += cur.rowcount if cur.rowcount > 0 else 0
                    ancestors: set[str] = set()
                    parent = Path(variant).parent
                    while str(parent) not in (".", "/"):
                        ancestors.add(str(parent))
                        parent = parent.parent
                    for ancestor in ancestors:
                        cur = conn.execute(
                            "UPDATE path SET dir_mtime_ns = NULL, last_walked_at = NULL "
                            "WHERE disk_id = ? AND rel_path = ?",
                            (disk_id, ancestor),
                        )
                        invalidated += cur.rowcount if cur.rowcount > 0 else 0
            # Clear the disk-level merkle short-circuit too.
            conn.execute("UPDATE disk SET merkle_root = NULL WHERE id = ?", (disk_id,))
        conn.commit()
        _log.info("post_maintenance_invalidated_subtrees", rows=invalidated)
    except Exception as exc:  # noqa: BLE001 — fail-soft: the scans still run
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
        _log.warning("post_maintenance_invalidate_failed", error=str(exc))
    finally:
        conn.close()
    return invalidated


def _scan_disk_incremental(config: Config, disk: str) -> int:
    """Run ``library-index --mode incremental --disk D --no-budget``.

    Uses the programmatic entry point rather than shelling out.

    Args:
        config: Validated application Config.
        disk: Disk label (e.g. ``"disk_1"``) — must exist in ``config.disks``.

    Returns:
        Exit code (0 = success, non-zero = failure).
    """
    # Warm the cli<->scan circular import chain so the scan import never
    # fails in a cold process (scan.py:13 ↔ cli.py:21 circular dependency).
    import personalscraper.indexer.cli as _cli  # noqa: F401
    from personalscraper.conf.loader import resolve_config_path
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer.commands.scan import library_index_command

    _log.info("post_maintenance_scan_start", disk=disk)
    rc = library_index_command(
        mode="incremental",
        disk=disk,
        no_budget=True,
        event_bus=EventBus(),
        config_path=resolve_config_path(),
        # wait_for_lock: 0 means fail immediately if locked — consistent
        # with the CLI default. The dispatch command already holds
        # pipeline.lock so no concurrent indexer should be running.
    )
    if rc != 0:
        _log.warning("post_maintenance_scan_failed", disk=disk, exit_code=rc)
    else:
        _log.info("post_maintenance_scan_done", disk=disk)
    return rc


def _run_relink(config: Config) -> dict[str, int]:
    """Relink ``media_file`` rows with ``release_id IS NULL``.

    Opens its own short-lived connection (the scan already released its
    lock).  Mirrors the ``library-relink --apply`` logic in
    :func:`personalscraper.commands.library.audit.library_relink`.

    Args:
        config: Validated application Config.

    Returns:
        Dict with ``linked``, ``unmatched``, ``errors`` counts.
    """
    from personalscraper.indexer.db import _apply_pragmas
    from personalscraper.indexer.release_linker import link_file_to_release

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
    linked = unmatched = errors = 0
    try:
        conn.execute("BEGIN IMMEDIATE")
        disks = {did: Path(mp) for did, mp in conn.execute("SELECT id, mount_path FROM disk WHERE is_mounted = 1")}
        if not disks:
            _log.info("post_maintenance_relink_no_disks")
            return {"linked": 0, "unmatched": 0, "errors": 0}

        rows = list(
            conn.execute(
                """
                SELECT mf.id, mf.filename, p.disk_id, p.rel_path
                FROM media_file mf
                JOIN path p ON p.id = mf.path_id
                WHERE mf.release_id IS NULL AND mf.deleted_at IS NULL
                """
            )
        )
        if not rows:
            conn.rollback()
            _log.info("post_maintenance_relink_nothing_to_do")
            return {"linked": 0, "unmatched": 0, "errors": 0}

        for mf_id, filename, disk_id, rel_path in rows:
            mount = disks.get(disk_id)
            if mount is None:
                continue
            abs_path = mount / rel_path / filename
            try:
                result = link_file_to_release(conn, mf_id, str(abs_path))
                if result is not None:
                    linked += 1
                else:
                    unmatched += 1
            except Exception as exc:
                errors += 1
                _log.warning(
                    "post_maintenance_relink_failed",
                    file_id=mf_id,
                    path=str(abs_path),
                    error=str(exc),
                )

        conn.commit()
        _log.info("post_maintenance_relink_done", linked=linked, unmatched=unmatched, errors=errors)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {"linked": linked, "unmatched": unmatched, "errors": errors}


def _run_fix_season_counts(config: Config) -> int:
    """Repair ``season.episode_count`` drift.

    Opens its own short-lived connection. Mirrors the
    ``library-fix-season-counts --apply`` logic.

    Args:
        config: Validated application Config.

    Returns:
        Number of season rows whose ``episode_count`` was corrected.
    """
    from personalscraper.indexer.db import _apply_pragmas

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            """
            UPDATE season
            SET episode_count = (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
            WHERE episode_count != (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
            """
        )
        fixed = cur.rowcount if cur.rowcount >= 0 else 0
        conn.commit()
        _log.info("post_maintenance_fix_season_counts_done", fixed=fixed)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return fixed


def _run_repair_drain(config: Config, *, budget_seconds: float = 60.0) -> int:
    """Drain the ``repair_queue`` within a small wall-clock budget.

    The queue's only historical drainer was the manual ``library-repair``
    CLI, which no cron ever ran — repairs (e.g. ``content_drift`` re-hashes
    enqueued by the scanner) accumulated forever (prod: 25 rows pending for
    6+ days). Post-dispatch is the natural home: the scan that just ran is
    exactly what enqueues them.

    Args:
        config: Validated application Config.
        budget_seconds: Maximum wall-clock seconds to spend draining.

    Returns:
        Number of rows processed (0 on any failure — fail-soft).
    """
    from personalscraper.indexer.db import _apply_pragmas
    from personalscraper.indexer.repair import drain, repair_processor

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"

    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
    try:
        stats = drain(conn, budget_seconds=budget_seconds, processor=repair_processor)
        _log.info(
            "post_maintenance_repair_drain_done",
            processed=stats.processed,
            succeeded=stats.succeeded,
            failed=stats.failed,
            budget_exhausted=stats.budget_exhausted,
        )
        return stats.processed
    finally:
        conn.close()


def run_post_dispatch_maintenance(
    config: Config,
    touched_disks: set[str],
    *,
    destinations: dict[str, set[Path]] | None = None,
    enabled: bool = True,
) -> None:
    """Run post-dispatch index maintenance for disks touched by dispatch.

    Sequentially scans each touched disk (incremental mode), then runs
    a global relink pass and season-episode-count repair.  Fail-soft:
    exceptions are caught, logged as warnings, and the manual fallback
    command is printed — the function never raises.

    Args:
        config: Validated application Config.
        touched_disks: Distinct, non-None disk labels from ``DispatchResult.disk``
            for items whose action was ``moved | merged | replaced``.
        destinations: Dispatched destination paths per disk
            (:func:`collect_touched_destinations`) — their subtrees are
            invalidated so the incremental scan re-walks them even when the
            filesystem did not bump the parent mtimes (NTFS/macFUSE merge).
        enabled: Feature toggle. When ``False``, the function is a no-op.
            Callers should resolve ``flag > config > default(true)`` before
            passing this parameter.
    """
    if not enabled:
        _log.info("post_maintenance_disabled")
        return

    if not touched_disks:
        _log.info("post_maintenance_no_touched_disks")
        return

    _log.info("post_maintenance_start", disks=sorted(touched_disks))

    # Force-invalidate the dispatched subtrees FIRST: a merge into an existing
    # show folder does not reliably bump parent mtimes on NTFS/macFUSE, so the
    # incremental short-circuit would skip exactly the branches dispatch just
    # wrote (prod: AD S22E10/E11 invisible 11 days; HotD S03E04 missed in-run).
    if destinations:
        _invalidate_dispatched_subtrees(config, destinations)

    # Per-disk incremental scan — sequential (parallel dies on SQLite writer lock).
    # Fallback: if items remain unlinked after incremental, the fail-soft
    # warning + manual fallback command is logged for the operator (no
    # automatic full scan — operator decision, 2026-06-30).
    scan_failures: list[str] = []
    for disk in sorted(touched_disks):
        try:
            rc = _scan_disk_incremental(config, disk)
            if rc != 0:
                scan_failures.append(disk)
        except Exception as exc:
            scan_failures.append(disk)
            _log.warning("post_maintenance_scan_exception", disk=disk, error=str(exc))

    # Global relink — fast, DB-only.
    relink_failed = False
    try:
        relink_counts = _run_relink(config)
    except Exception as exc:
        relink_counts = {"linked": 0, "unmatched": 0, "errors": 0}
        relink_failed = True
        _log.warning("post_maintenance_relink_exception", error=str(exc))

    # Global fix-season-counts — fast, DB-only.
    fix_failed = False
    try:
        fixed_seasons = _run_fix_season_counts(config)
    except Exception as exc:
        fixed_seasons = 0
        fix_failed = True
        _log.warning("post_maintenance_fix_season_counts_exception", error=str(exc))

    # Repair-queue drain — the scans above are what enqueue content repairs;
    # drain them here so the queue never silently accumulates (fail-soft).
    try:
        _run_repair_drain(config)
    except Exception as exc:  # noqa: BLE001 — a drain failure must not fail dispatch
        _log.warning("post_maintenance_repair_drain_exception", error=str(exc))

    # Print manual fallback if anything failed.
    # DESIGN Decision #2: surface manual fallback on ANY maintenance error,
    # including total _run_relink or _run_fix_season_counts exceptions.
    if scan_failures or relink_failed or fix_failed or relink_counts.get("errors", 0) > 0:
        if scan_failures:
            disks_str = " ".join("--disk " + d for d in scan_failures)
            manual_fallback = (
                f"library-index --mode full {disks_str} --no-budget && "
                f"library-relink --apply && library-fix-season-counts --apply"
            )
        else:
            manual_fallback = "library-relink --apply && library-fix-season-counts --apply"
        _log.warning(
            "post_maintenance_incomplete",
            failed_disks=scan_failures,
            relink_errors=relink_counts.get("errors", 0),
            manual_fallback=manual_fallback,
        )

    _log.info(
        "post_maintenance_complete",
        disks_scanned=len(touched_disks) - len(scan_failures),
        scan_failures=len(scan_failures),
        relinked=relink_counts.get("linked", 0),
        seasons_fixed=fixed_seasons,
    )


def maybe_run_post_dispatch_maintenance(
    config: Config,
    results: list[DispatchResult],
    *,
    dry_run: bool,
    no_post_maintenance: bool = False,
) -> None:
    """Resolve the post-dispatch maintenance policy from *results*, then run it.

    Single owner of the trigger/guard logic that was duplicated in the full-run
    :class:`~personalscraper.pipeline_steps.DispatchStep` and the standalone
    ``personalscraper dispatch`` CLI command (PIPELINE-CORE-01 — the two copies
    had drifted). Both entry points call THIS with the raw ``run_dispatch``
    results and their flag state, so enablement resolution, touched-disk /
    destination collection, and the dry-run guard stay byte-identical across the
    two paths.

    Enablement resolves ``flag > config > default(true)``: the operator opt-out
    ``no_post_maintenance`` wins, otherwise
    ``config.indexer.post_dispatch_maintenance.enabled`` decides. Maintenance is
    triggered only when dispatch actually touched a disk and the run is not a
    preview; a disabled-but-touched run still calls
    :func:`run_post_dispatch_maintenance` with ``enabled=False`` (a logged
    no-op), preserving the standalone command's historical call shape that its
    e2e regressions assert.

    Args:
        config: Validated application Config.
        results: Raw per-item dispatch results from :func:`run_dispatch`.
        dry_run: When True the maintenance is skipped entirely — a preview must
            never mutate the index.
        no_post_maintenance: Operator opt-out flag (``--no-post-maintenance`` /
            ``ctx.extras['no_post_maintenance']``). Defaults to False.
    """
    maintenance_enabled = not no_post_maintenance
    if maintenance_enabled:
        maintenance_enabled = config.indexer.post_dispatch_maintenance.enabled

    touched_disks = collect_touched_disks(results)
    if touched_disks and not dry_run:
        run_post_dispatch_maintenance(
            config,
            touched_disks,
            destinations=collect_touched_destinations(results),
            enabled=maintenance_enabled,
        )
