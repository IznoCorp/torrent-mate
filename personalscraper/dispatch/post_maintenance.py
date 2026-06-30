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


def _scan_disk_incremental(config: Config, disk: str) -> int:
    """Run ``library-index --mode incremental --disk D --no-budget``.

    Uses the programmatic entry point rather than shelling out.

    Args:
        config: Validated application Config.
        disk: Disk label (e.g. ``"disk_1"``) — must exist in ``config.disks``.

    Returns:
        Exit code (0 = success, non-zero = failure).
    """
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer.commands.scan import library_index_command

    _log.info("post_maintenance_scan_start", disk=disk)
    rc = library_index_command(
        mode="incremental",
        disk=disk,
        no_budget=True,
        event_bus=EventBus(),
        # wait_for_lock: 0 means fail immediately if locked — consistent
        # with the CLI default. The dispatch command already holds
        # pipeline.lock so no concurrent indexer should be running.
    )
    if rc != 0:
        _log.warning("post_maintenance_scan_failed", disk=disk, exit_code=rc)
    else:
        _log.info("post_maintenance_scan_done", disk=disk)
    return rc


def _count_unlinked_files_for_disk(config: Config, disk_label: str) -> int:
    """Count media_file rows with release_id=NULL on a specific disk.

    Args:
        config: Validated application Config.
        disk_label: Disk label (e.g. ``"disk_1"``).

    Returns:
        Number of unlinked media_file rows (release_id IS NULL and not
        soft-deleted) that live on the given disk.
    """
    import sqlite3

    from personalscraper.indexer.db import _apply_pragmas

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    _apply_pragmas(conn)
    try:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM media_file mf
            JOIN path p ON p.id = mf.path_id
            JOIN disk d ON d.id = p.disk_id
            WHERE d.label = ? AND mf.release_id IS NULL AND mf.deleted_at IS NULL
            """,
            (disk_label,),
        ).fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


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

    conn = sqlite3.connect(str(db_path))
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


def run_post_dispatch_maintenance(
    config: Config,
    touched_disks: set[str],
    *,
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

    # Per-disk incremental scan — sequential (parallel dies on SQLite writer lock).
    scan_failures: list[str] = []
    for disk in sorted(touched_disks):
        try:
            rc = _scan_disk_incremental(config, disk)
            if rc != 0:
                scan_failures.append(disk)
                continue
            # Fallback: if items on this disk still have 0 linked files,
            # incremental might have missed them → re-run full.
            # (DESIGN index-sync Risk §1)
            unlinked = _count_unlinked_files_for_disk(config, disk)
            if unlinked > 0:
                _log.warning(
                    "post_maintenance_incremental_missed",
                    disk=disk,
                    unlinked_files=unlinked,
                )
                from personalscraper.core.event_bus import EventBus
                from personalscraper.indexer.commands.scan import library_index_command

                rc_full = library_index_command(
                    mode="full",
                    disk=disk,
                    no_budget=True,
                    event_bus=EventBus(),
                )
                if rc_full != 0:
                    scan_failures.append(disk)
        except Exception as exc:
            scan_failures.append(disk)
            _log.warning("post_maintenance_scan_exception", disk=disk, error=str(exc))

    # Global relink — fast, DB-only.
    try:
        relink_counts = _run_relink(config)
    except Exception as exc:
        relink_counts = {"linked": 0, "unmatched": 0, "errors": 0}
        _log.warning("post_maintenance_relink_exception", error=str(exc))

    # Global fix-season-counts — fast, DB-only.
    try:
        fixed_seasons = _run_fix_season_counts(config)
    except Exception as exc:
        fixed_seasons = 0
        _log.warning("post_maintenance_fix_season_counts_exception", error=str(exc))

    # Print manual fallback if anything failed.
    if scan_failures or relink_counts.get("errors", 0) > 0:
        disks_str = " ".join("--disk " + d for d in scan_failures) if scan_failures else ""
        _log.warning(
            "post_maintenance_incomplete",
            failed_disks=scan_failures,
            relink_errors=relink_counts.get("errors", 0),
            manual_fallback=(
                f"library-index --mode full {disks_str} --no-budget && "
                f"library-relink --apply && library-fix-season-counts --apply"
            ).strip(),
        )

    _log.info(
        "post_maintenance_complete",
        disks_scanned=len(touched_disks) - len(scan_failures),
        scan_failures=len(scan_failures),
        relinked=relink_counts.get("linked", 0),
        seasons_fixed=fixed_seasons,
    )
