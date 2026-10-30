"""Post-dispatch index maintenance hook.

After ``dispatch`` moves media onto the storage disks, the indexer database
lags reality: new ``media_file`` rows have ``release_id IS NULL`` and season
``episode_count`` may be stale.  This module provides a single reusable
function that runs a scoped, sequential index-maintenance sequence so the
library index is coherent without a manual operator step.
"""

from __future__ import annotations

import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper._fs_utils import name_key, name_variants
from personalscraper.indexer.repos.item_repo import _ATTR_DISPATCH_PATH
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus
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
    """Return every stored spelling of *rel_path*: NFC/NFD (macFUSE stores NFD) × « ? »/U+F025.

    Args:
        rel_path: A path string relative to a disk mount.

    Returns:
        The distinct spellings.
    """
    return name_variants(rel_path)


@dataclass(frozen=True)
class _Scope:
    """One subtree a targeted refresh is restricted to.

    Attributes:
        disk_id: PK of the owning ``disk`` row.
        mount: The disk's scan root (``disk.mount_path``), to build absolute paths.
        rel_variants: Every spelling of the subtree root relative to *mount* under which
            ``path.rel_path`` may be stored (NFC/NFD × « ? »/U+F025).
    """

    disk_id: int
    mount: str
    rel_variants: frozenset[str]


def _scope_sql(scopes: list[_Scope], path_alias: str = "p") -> tuple[str, list[object]]:
    """Build the SQL condition selecting the ``path`` rows at or below any of *scopes*.

    Prefix tests use ``substr`` rather than ``LIKE`` so a ``_`` or ``%`` in a folder name
    is a plain character.

    Args:
        scopes: The subtrees; must not be empty.
        path_alias: The alias of the ``path`` table in the surrounding query.

    Returns:
        ``(sql, params)`` — a parenthesised condition and its positional parameters.
    """
    clauses: list[str] = []
    params: list[object] = []
    for scope in scopes:
        for variant in sorted(scope.rel_variants):
            clauses.append(
                f"({path_alias}.disk_id = ? AND ({path_alias}.rel_path = ? OR substr({path_alias}.rel_path, 1, ?) = ?))"
            )
            params.extend([scope.disk_id, variant, len(variant) + 1, variant + "/"])
    return "(" + " OR ".join(clauses) + ")", params


def _scope_abs_sql(scopes: list[_Scope], column: str) -> tuple[str, list[object]]:
    """Build the SQL condition selecting absolute-path values at or below any of *scopes*.

    Args:
        scopes: The subtrees; must not be empty.
        column: The qualified column holding an absolute path (``item_attribute.value``).

    Returns:
        ``(sql, params)`` — a parenthesised condition and its positional parameters.
    """
    clauses: list[str] = []
    params: list[object] = []
    for scope in scopes:
        for variant in sorted(scope.rel_variants):
            absolute = str(Path(scope.mount) / variant)
            clauses.append(f"({column} = ? OR substr({column}, 1, ?) = ?)")
            params.extend([absolute, len(absolute) + 1, absolute + "/"])
    return "(" + " OR ".join(clauses) + ")", params


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


def _scan_disk_incremental(config: Config, disk: str, *, event_bus: EventBus) -> int:
    """Run ``library-index --mode incremental --disk D --no-budget``.

    Uses the programmatic entry point rather than shelling out.

    Args:
        config: Validated application Config.
        disk: Disk label (e.g. ``"disk_1"``) — must exist in ``config.disks``.
        event_bus: The CALLER's process bus, forwarded verbatim to the scan so its
            ``LibraryScanCompleted`` reaches the live subscribers — notably
            ``PostDispatchReconcileSubscriber``, which closes owned ``wanted`` rows.
            Required, never defaulted: this function used to build a fresh
            ``EventBus()`` here, and that throwaway bus silently swallowed every
            post-dispatch reconciliation (D4).

    Returns:
        Exit code (0 = success, non-zero = failure).
    """
    # Warm the cli<->scan circular import chain so the scan import never
    # fails in a cold process (scan.py:13 ↔ cli.py:21 circular dependency).
    import personalscraper.indexer.cli as _cli  # noqa: F401
    from personalscraper.conf.loader import resolve_config_path
    from personalscraper.indexer.commands.scan import library_index_command

    _log.info("post_maintenance_scan_start", disk=disk)
    rc = library_index_command(
        mode="incremental",
        disk=disk,
        no_budget=True,
        event_bus=event_bus,
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


def _run_relink(config: Config, *, scopes: list[_Scope] | None = None) -> dict[str, int]:
    """Relink ``media_file`` rows with ``release_id IS NULL``.

    Opens its own short-lived connection (the scan already released its
    lock).  Mirrors the ``library-relink --apply`` logic in
    :func:`personalscraper.commands.library.audit.library_relink`.

    Args:
        config: Validated application Config.
        scopes: When given, only files under these subtrees are considered; ``None``
            relinks every unlinked file of every mounted disk.

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

        scope_sql, scope_params = _scope_sql(scopes) if scopes else ("1", [])
        rows = list(
            conn.execute(
                f"""
                SELECT mf.id, mf.filename, p.disk_id, p.rel_path
                FROM media_file mf
                JOIN path p ON p.id = mf.path_id
                WHERE mf.release_id IS NULL AND mf.deleted_at IS NULL AND {scope_sql}
                """,  # noqa: S608 — only placeholders are interpolated
                scope_params,
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


def _run_fix_season_counts(config: Config, *, scopes: list[_Scope] | None = None) -> int:
    """Repair ``season.episode_count`` drift.

    Opens its own short-lived connection. Mirrors the
    ``library-fix-season-counts --apply`` logic.

    Args:
        config: Validated application Config.
        scopes: When given, only the seasons of items that own a file under these
            subtrees, or whose ``dispatch_path`` lies under them, are corrected;
            ``None`` corrects every season.

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
        item_filter = ""
        params: list[object] = []
        if scopes:
            path_sql, path_params = _scope_sql(scopes)
            abs_sql, abs_params = _scope_abs_sql(scopes, "ia.value")
            item_filter = f"""
              AND season.item_id IN (
                SELECT mr.item_id FROM media_file mf
                  JOIN path p ON p.id = mf.path_id
                  JOIN media_release mr ON mr.id = mf.release_id
                 WHERE mr.item_id IS NOT NULL AND {path_sql}
                UNION
                SELECT s.item_id FROM media_file mf
                  JOIN path p ON p.id = mf.path_id
                  JOIN media_release mr ON mr.id = mf.release_id
                  JOIN episode e ON e.id = mr.episode_id
                  JOIN season s ON s.id = e.season_id
                 WHERE {path_sql}
                UNION
                SELECT ia.item_id FROM item_attribute ia
                 WHERE ia.key = '{_ATTR_DISPATCH_PATH}' AND {abs_sql}
              )"""
            params = [*path_params, *path_params, *abs_params]
        cur = conn.execute(
            f"""
            UPDATE season
            SET episode_count = (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id)
            WHERE episode_count != (SELECT COUNT(*) FROM episode WHERE episode.season_id = season.id){item_filter}
            """,  # noqa: S608 — only placeholders are interpolated
            params,
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


def _run_repair_drain(config: Config, *, budget_seconds: float = 60.0, scopes: list[_Scope] | None = None) -> int:
    """Drain the ``repair_queue`` within a small wall-clock budget.

    The queue's only historical drainer was the manual ``library-repair``
    CLI, which no cron ever ran — repairs (e.g. ``content_drift`` re-hashes
    enqueued by the scanner) accumulated forever (prod: 25 rows pending for
    6+ days). Post-dispatch is the natural home: the scan that just ran is
    exactly what enqueues them.

    Args:
        config: Validated application Config.
        budget_seconds: Maximum wall-clock seconds to spend draining.
        scopes: When given, only the pending repairs of files and paths under these
            subtrees are drained; the rest of the queue is left alone.

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
        only_ids: set[int] | None = None
        if scopes:
            path_sql, path_params = _scope_sql(scopes)
            only_ids = {
                row[0]
                for row in conn.execute(
                    f"""
                    SELECT rq.id FROM repair_queue rq
                     WHERE rq.status = 'pending' AND (
                       (rq.scope = 'file' AND rq.scope_id IN (
                          SELECT mf.id FROM media_file mf JOIN path p ON p.id = mf.path_id WHERE {path_sql}))
                       OR (rq.scope = 'path' AND rq.scope_id IN (SELECT p.id FROM path p WHERE {path_sql})))
                    """,  # noqa: S608 — only placeholders are interpolated
                    [*path_params, *path_params],
                )
            }
        stats = drain(conn, budget_seconds=budget_seconds, processor=repair_processor, only_ids=only_ids)
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
    event_bus: EventBus,
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
        event_bus: The caller's process bus, forwarded to every per-disk scan so
            ``LibraryScanCompleted`` reaches live subscribers. Required (D4) — a
            defaulted bus reaches nobody and silently disables post-dispatch
            reconciliation.
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
            rc = _scan_disk_incremental(config, disk, event_bus=event_bus)
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
    event_bus: EventBus,
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
        event_bus: The caller's process bus, forwarded to
            :func:`run_post_dispatch_maintenance` and on to every disk scan so
            ``LibraryScanCompleted`` reaches live subscribers. Required (D4).
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
            event_bus=event_bus,
            destinations=collect_touched_destinations(results),
            enabled=maintenance_enabled,
        )


class ScopedRefreshIncomplete(RuntimeError):
    """A targeted refresh's walk was stopped (shutdown or budget) before it finished.

    Raised after the transaction is rolled back: a half-seen subtree is never committed,
    since what the walk did not reach would otherwise look gone.
    """


@dataclass
class ScopedRefreshReport:
    """What a targeted refresh did (or, on a dry run, would do).

    Attributes:
        scanned: Existing paths whose subtree was (or would be) rescanned, as resolved on disk.
        removed: Paths gone from the disk whose subtree was (or would be) removed from the index.
        files_scanned: Files visited by the scan (0 on a dry run).
        files_removed: Live ``media_file`` rows soft-deleted (counted, not written, on a dry run).
        relinked: Files newly linked to a release by the scoped relink.
        seasons_fixed: Season rows whose ``episode_count`` was corrected.
        failed_steps: Names of the DB-only passes that raised (logged; the refresh goes on).
    """

    scanned: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    files_scanned: int = 0
    files_removed: int = 0
    relinked: int = 0
    seasons_fixed: int = 0
    failed_steps: list[str] = field(default_factory=list)


def _stored_spellings(conn: sqlite3.Connection, disk_id: int, rel: str) -> list[str]:
    """Return the spellings under which the index stores the folder *rel* (or its descendants' prefix).

    The filesystem ignores case (and macFUSE hands NFD / U+F025 names back as either), the
    index does not: a path typed in another case must be matched against what is stored,
    not against its own spelling. Looked up through every ``path`` row of the disk, whose
    leading components are compared by :func:`name_key` and case-folded.

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk.
        rel: The folder relative to the disk's scan root, as typed.

    Returns:
        The distinct stored spellings, sorted; empty when the index holds nothing there.
    """
    target = name_key(rel).casefold()
    depth = rel.count("/") + 1
    found: set[str] = set()
    for (stored,) in conn.execute("SELECT rel_path FROM path WHERE disk_id = ?", (disk_id,)):
        head = "/".join(stored.split("/")[:depth])
        if name_key(head).casefold() == target:
            found.add(head)
    return sorted(found)


def _disk_spelling(mount: Path, rel: str) -> str:
    """Return *rel* spelled as the filesystem lists it (component by component).

    Used for a folder the index does not know yet, so the path row written for it takes
    the spelling the walk will give its children, never the typed one. Components that do
    not exist are kept as typed.

    Args:
        mount: The disk's scan root.
        rel: The folder relative to *mount*, as typed.

    Returns:
        The relative path with each existing component in its on-disk spelling.
    """
    current = mount
    parts: list[str] = []
    for part in rel.split("/"):
        try:
            listed = os.listdir(current)
        except OSError:
            listed = []
        match = (
            part
            if part in listed
            else next((n for n in listed if name_key(n).casefold() == name_key(part).casefold()), part)
        )
        parts.append(match)
        current = current / match
    return "/".join(parts)


def _require_removable(mount: Path, given: Path, located: Path) -> None:
    """Refuse to retire a vanished path unless the disk is demonstrably there.

    A disk that is not mounted looks exactly like a disk whose folders were all
    deleted: the mount point is empty or absent, so every path "vanished". Removing on
    that evidence would retire the whole subtree of an unmounted disk.

    Args:
        mount: The disk's scan root.
        given: The path as the operator typed it (for the message).
        located: The path that is missing from the disk.

    Raises:
        ValueError: The scan root is missing or empty, or the vanished path's parent
            folder does not exist.
    """
    try:
        mounted = any(mount.iterdir())
    except OSError:
        mounted = False
    if not mounted:
        raise ValueError(f"the scan root {mount} is empty or missing (disk not mounted?); not removing {given}")
    if not located.parent.is_dir():
        raise ValueError(f"the parent folder of {given} does not exist; not removing it from the index")


def run_scoped_refresh(
    config: Config,
    disk_label: str,
    paths: list[Path],
    *,
    dry_run: bool = False,
) -> ScopedRefreshReport:
    """Reconcile the index with the disk for the given subtrees ONLY.

    Unlike :func:`run_post_dispatch_maintenance`, nothing here is disk-wide:

    * a path that exists is re-walked (every directory, no mtime short-circuit — the
      point of a manual refresh is that the filesystem's mtimes cannot be trusted),
      with the incremental visitor, so a rename is detected through the OSHash drift
      logic; existing paths are processed BEFORE vanished ones so a renamed folder's
      rows are moved to their new path before the old path is retired; once every walk
      is done, the live files under it that no walk saw are soft-deleted (they are gone);
    * a path that no longer exists has its live files soft-deleted, with a tombstone,
      like the scanner does once the strikes are served;
    * relink, season-count repair and repair-queue drain are restricted to the same
      subtrees.

    The scan and removals are one transaction under the indexer's writer lock.

    Args:
        config: Validated application Config.
        disk_label: Label of the disk that owns every path (``DiskConfig.id``).
        paths: Absolute paths to refresh, existing or not.
        dry_run: When ``True`` nothing is written; the report says what would happen.

    Returns:
        The :class:`ScopedRefreshReport`.

    Raises:
        ValueError: The disk is unknown or unmounted, a path is not strictly below the
            disk's scan root, or a vanished path cannot be shown to be really gone (empty
            scan root, missing parent), or a path is neither on the disk nor in the index.
        ScopedRefreshIncomplete: A walk was stopped before it finished; the transaction
            is rolled back.
    """
    from personalscraper.indexer._fs_capability import resolve_capability
    from personalscraper.indexer.commands._bootstrap import build_fs_type_overrides
    from personalscraper.indexer.db import _apply_pragmas, indexer_lock
    from personalscraper.indexer.drift import soft_delete_live_files_under
    from personalscraper.indexer.scanner._db_writes import _safe_mtime_ns, _upsert_path_row
    from personalscraper.indexer.scanner._modes.incremental import IncrementalVisitor
    from personalscraper.indexer.scanner._shutdown import is_shutdown_requested
    from personalscraper.indexer.scanner._walker import WalkBudget, WalkCheckpoint, walk
    from personalscraper.indexer.schema import DiskRow

    db_path = config.indexer.db_path
    assert db_path is not None, "indexer.db_path must be resolved"
    if not db_path.exists():
        # sqlite3.connect would create an empty file: a refresh never makes the index.
        raise ValueError(f"the index {db_path} does not exist; run library-index first")
    report = ScopedRefreshReport()

    with indexer_lock(db_path, timeout=0):
        conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
        _apply_pragmas(conn)
        try:
            row = conn.execute(
                "SELECT id, uuid, label, mount_path, last_seen_at, merkle_root, is_mounted, unreachable_strikes "
                "FROM disk WHERE label = ?",
                (disk_label,),
            ).fetchone()
            if row is not None and row[3] is not None:
                disk = DiskRow(
                    id=row[0],
                    uuid=row[1],
                    label=row[2],
                    mount_path=row[3],
                    last_seen_at=row[4],
                    merkle_root=row[5],
                    is_mounted=row[6],
                    unreachable_strikes=row[7],
                )
            elif dry_run and any(d.id == disk_label for d in config.disks):
                # Not indexed yet: a dry run can still say what it would do (nothing to remove).
                configured = next(d for d in config.disks if d.id == disk_label)
                disk = DiskRow(
                    id=-1,
                    uuid="",
                    label=disk_label,
                    mount_path=str(configured.path),
                    last_seen_at=None,
                    merkle_root=None,
                    is_mounted=0,
                    unreachable_strikes=0,
                )
            else:
                raise ValueError(f"disk {disk_label!r} is unknown to the index or has no scan root")
            mount = Path(str(disk.mount_path))

            # Classify first: every path is validated before anything is written.
            to_scan: list[tuple[Path, str, set[str]]] = []
            to_remove: list[tuple[Path, str, set[str]]] = []
            for given in paths:
                try:
                    typed_rel = str(given.relative_to(mount))
                except ValueError:
                    raise ValueError(f"{given} is not under the scan root of disk {disk_label!r} ({mount})") from None
                if typed_rel == ".":
                    raise ValueError(f"{given} is the scan root itself; give a folder below it")
                # The stored spelling wins over the typed one; a spelling that is on disk wins over the others.
                stored = _stored_spellings(conn, disk.id, typed_rel)
                rel = next((r for r in stored if (mount / r).exists()), None)
                if rel is None:
                    rel = stored[0] if stored else _disk_spelling(mount, typed_rel)
                located = mount / rel
                variants = {v for spelling in (*stored, rel) for v in _rel_path_variants(spelling)}
                if located.exists():
                    if not located.is_dir():
                        raise ValueError(f"{given} is not a folder; give the media folder, not a file")
                    to_scan.append((located, rel, variants))
                else:
                    _require_removable(mount, given, located)
                    if not stored:
                        raise ValueError(f"{given} is not on the disk and not indexed; check the path (typo?)")
                    to_remove.append((located, rel, variants))

            report.scanned = [p for p, _, _ in to_scan]
            report.removed = [p for p, _, _ in to_remove]
            scopes = [_Scope(disk.id, str(mount), frozenset(variants)) for _, _, variants in to_scan]

            if dry_run:
                for _, _, variants in to_remove:
                    report.files_removed += _count_live_files_under(conn, disk.id, variants)
                for _, _, variants in to_scan:
                    report.files_removed += _count_live_files_under(
                        conn, disk.id, variants, mount=mount, only_missing=True
                    )
                return report

            capability = resolve_capability(str(mount), build_fs_type_overrides(config.disks).get(disk.label))
            generation = int(conn.execute("SELECT COALESCE(MAX(scan_generation), 0) FROM media_file").fetchone()[0]) + 1
            files_visited = [0]
            dirs_visited = [0]
            conn.execute("BEGIN IMMEDIATE")
            try:
                for located, rel, _ in to_scan:
                    visitor = IncrementalVisitor(conn, disk, generation, files_visited, dirs_visited, False, capability)
                    walk_budget = WalkBudget(None, time.monotonic())
                    walk(
                        str(located),
                        visitor,
                        budget=walk_budget,
                        shutdown=is_shutdown_requested,
                        # Never reached: a checkpoint commits mid-walk and would end the transaction.
                        checkpoint=WalkCheckpoint(scan_run_id=0, checkpoint_every=2**62),
                    )
                    # walk() returns nothing: a stop (shutdown or budget) only sets this flag.
                    if walk_budget.budget_exhausted[0]:
                        raise ScopedRefreshIncomplete(
                            f"the walk of {located} did not finish (stopped); nothing was written, run it again"
                        )
                    _upsert_path_row(conn, disk.id, rel, _safe_mtime_ns(located.stat().st_mtime_ns))
                # Only now: a file moved between two of the given paths was re-pointed by the
                # walk above, so what is still unseen is really gone.
                for _, _, variants in to_scan:
                    report.files_removed += soft_delete_live_files_under(
                        conn, disk.id, variants, reason="refresh_path", unseen_before=generation
                    )
                for _, _, variants in to_remove:
                    report.files_removed += soft_delete_live_files_under(conn, disk.id, variants, reason="refresh_path")
                # The stored disk fingerprint no longer describes the index.
                conn.execute("UPDATE disk SET merkle_root = NULL WHERE id = ?", (disk.id,))
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            report.files_scanned = files_visited[0]
        finally:
            conn.close()

    _log.info(
        "scoped_refresh_scanned",
        disk=disk_label,
        scanned=len(report.scanned),
        removed=len(report.removed),
        files_scanned=report.files_scanned,
        files_removed=report.files_removed,
    )
    if not scopes:
        return report

    # The DB-only passes, fail-soft like the post-dispatch ones, over the same subtrees.
    try:
        report.relinked = _run_relink(config, scopes=scopes).get("linked", 0)
    except Exception as exc:  # noqa: BLE001
        report.failed_steps.append("relink")
        _log.warning("scoped_refresh_relink_exception", error=str(exc), exc_info=True)
    try:
        report.seasons_fixed = _run_fix_season_counts(config, scopes=scopes)
    except Exception as exc:  # noqa: BLE001
        report.failed_steps.append("fix-season-counts")
        _log.warning("scoped_refresh_fix_season_counts_exception", error=str(exc), exc_info=True)
    try:
        _run_repair_drain(config, scopes=scopes)
    except Exception as exc:  # noqa: BLE001
        report.failed_steps.append("repair-drain")
        _log.warning("scoped_refresh_repair_drain_exception", error=str(exc), exc_info=True)
    return report


def _count_live_files_under(
    conn: sqlite3.Connection,
    disk_id: int,
    rel_variants: set[str],
    *,
    mount: Path | None = None,
    only_missing: bool = False,
) -> int:
    """Count the live ``media_file`` rows of a disk subtree (the dry run's removal count).

    Args:
        conn: Open SQLite connection.
        disk_id: PK of the owning disk.
        rel_variants: Spellings of the subtree root relative to the disk's scan root.
        mount: The disk's scan root; required with *only_missing*.
        only_missing: Count only the files that are no longer on the disk (what a real
            refresh of a path that still exists would retire).

    Returns:
        Number of non-deleted files at or below the subtree root.
    """
    scope_sql, params = _scope_sql([_Scope(disk_id, "", frozenset(rel_variants))])
    rows = conn.execute(
        f"SELECT p.rel_path, mf.filename FROM media_file mf JOIN path p ON p.id = mf.path_id "  # noqa: S608
        f"WHERE mf.deleted_at IS NULL AND {scope_sql}",
        params,
    ).fetchall()
    if not only_missing:
        return len(rows)
    assert mount is not None, "only_missing needs the scan root"
    return sum(1 for rel_path, filename in rows if not (mount / rel_path / filename).exists())
