"""Scan-mode → per-disk driver table dispatch.

Replaces the historical ``if mode == ScanMode.full: … elif …`` chain that lived
inline in :func:`personalscraper.indexer.scanner._scan_orchestrator._scan_one_disk`.
Each :class:`ScanMode` maps to a single handler in :data:`_MODE_DISPATCH`;
**adding a new mode is one registry entry plus its driver** — no new branch arm.

Every handler receives one immutable :class:`_DiskDispatch` bundle and resolves
its concrete driver (``_scan_disk_full`` etc.) through the scanner **package**
namespace carried on ``_DiskDispatch.scanner_pkg`` so the ``unittest.mock`` seams
that patch ``scanner._scan_disk_*`` / ``scanner._walk_dir`` still intercept. Modes
absent from the table fall through to :func:`_dispatch_skeleton` (the bare walk).
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from personalscraper.indexer._fs_capability import FilesystemCapability
from personalscraper.indexer.scanner._db_writes import _upsert_path_row
from personalscraper.indexer.scanner._types import ScanMode
from personalscraper.indexer.schema import DiskRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from types import ModuleType

    from personalscraper.indexer.scanner._scan_orchestrator import _DiskWalkContext

log = get_logger("indexer.scan")


@dataclass(frozen=True)
class _DiskDispatch:
    """Immutable bundle of everything a per-mode driver needs for one disk.

    Groups the worker connection, the resolved :class:`DiskRow` + mount point,
    the per-disk :class:`FilesystemCapability` and effective dir-mtime-reliable
    flag, the shared ``_DiskWalkContext``, and the worker-local counters so the
    mode-dispatch handlers keep a single-parameter signature.

    ``scanner_pkg`` is the ``personalscraper.indexer.scanner`` package module,
    passed through so handlers resolve their driver (``_scan_disk_full`` etc.)
    via the package namespace — this preserves the ``unittest.mock`` seams that
    patch ``scanner._scan_disk_*`` / ``scanner._walk_dir`` on the package.
    """

    scanner_pkg: "ModuleType"
    worker_conn: sqlite3.Connection
    disk: DiskRow
    mount: str
    capability: FilesystemCapability
    dir_mtime_reliable: bool
    ctx: "_DiskWalkContext"
    local_files: list[int]
    local_dirs: list[int]
    local_skipped: list[int]
    local_resume_from: list[str | None]
    local_files_since_ckpt: list[int]
    local_exhausted: list[bool]


def _recompute_root_path(d: _DiskDispatch) -> None:
    """Upsert the disk-root ``path`` row after a full / skeleton walk.

    The root directory (``"."``) is not visited by the recursive walk itself,
    so full and skeleton modes stamp its current mtime here once the walk
    returns. Skipped when the time budget was exhausted mid-walk (the root
    mtime would be recorded on the next resumed run).
    """
    if d.local_exhausted[0]:
        return
    try:
        root_st = os.stat(d.mount, follow_symlinks=False)
        _upsert_path_row(d.worker_conn, d.disk.id, ".", root_st.st_mtime_ns)
        d.local_dirs[0] += 1
    except OSError as exc:
        log.warning(
            "indexer.scan.root_stat_failed",
            mount_path=d.mount,
            errno=exc.errno,
            error=exc.strerror or str(exc),
            exc_info=True,
        )


def _dispatch_full(d: _DiskDispatch) -> None:
    """Full-scan driver: fingerprint every file, then stamp the root path row."""
    d.scanner_pkg._scan_disk_full(
        d.worker_conn,
        d.disk,
        d.mount,
        d.local_files,
        d.local_dirs,
        d.ctx.generation,
        d.ctx.drop_indexes,
        d.local_resume_from,
        d.local_files_since_ckpt,
        d.local_exhausted,
        d.ctx.started_at_monotonic,
        d.ctx.budget_seconds,
        d.ctx.scan_run_id,
        d.ctx.checkpoint_every_n_files,
    )
    _recompute_root_path(d)


def _dispatch_quick(d: _DiskDispatch) -> None:
    """Quick-scan driver: Merkle short-circuit then dir-mtime subtree walk."""
    d.scanner_pkg._scan_disk_quick(
        d.worker_conn,
        d.disk,
        d.mount,
        d.local_files,
        d.local_dirs,
        d.ctx.generation,
        d.local_skipped,
        d.dir_mtime_reliable,
        d.local_resume_from,
        d.local_files_since_ckpt,
        d.local_exhausted,
        d.ctx.started_at_monotonic,
        d.ctx.budget_seconds,
        d.ctx.scan_run_id,
        d.ctx.checkpoint_every_n_files,
        confirm_bulk_change=d.ctx.confirm_bulk_change,
        merkle_delta_freeze_threshold=d.ctx.merkle_delta_freeze_threshold,
        paranoia_window_seconds=d.ctx.paranoia_window_seconds,
        capability=d.capability,
    )


def _dispatch_incremental(d: _DiskDispatch) -> None:
    """Incremental-scan driver: dir-mtime delta walk with Merkle short-circuit."""
    d.scanner_pkg._scan_disk_incremental(
        d.worker_conn,
        d.disk,
        d.mount,
        d.local_files,
        d.local_dirs,
        d.ctx.generation,
        d.local_skipped,
        d.dir_mtime_reliable,
        d.local_resume_from,
        d.local_files_since_ckpt,
        d.local_exhausted,
        d.ctx.started_at_monotonic,
        d.ctx.budget_seconds,
        d.ctx.scan_run_id,
        d.ctx.checkpoint_every_n_files,
        confirm_bulk_change=d.ctx.confirm_bulk_change,
        merkle_delta_freeze_threshold=d.ctx.merkle_delta_freeze_threshold,
        capability=d.capability,
    )


def _dispatch_enrich(d: _DiskDispatch) -> None:
    """Enrich driver: targeted stream backfill or the full enrich pass."""
    if d.ctx.backfill_streams:
        d.scanner_pkg._scan_disk_enrich_backfill(
            d.worker_conn,
            d.disk,
            d.ctx.budget_seconds,
            d.ctx.started_at_monotonic,
            d.local_exhausted,
            d.ctx.scan_run_id,
            quick_enrich=d.ctx.quick_enrich,
        )
    else:
        d.scanner_pkg._scan_disk_enrich(
            d.worker_conn,
            d.disk,
            d.ctx.budget_seconds,
            d.ctx.started_at_monotonic,
            d.local_exhausted,
            d.ctx.scan_run_id,
            quick_enrich=d.ctx.quick_enrich,
        )


def _dispatch_verify(d: _DiskDispatch) -> None:
    """Verify driver: re-stat every indexed file, enqueue repair on drift."""
    d.scanner_pkg._scan_disk_verify(
        d.worker_conn,
        d.disk,
        d.local_files,
        d.ctx.generation,
        d.ctx.budget_seconds,
        d.ctx.started_at_monotonic,
        d.local_exhausted,
        d.ctx.scan_run_id,
        no_enqueue=d.ctx.no_enqueue,
        capability=d.capability,
    )


def _dispatch_skeleton(d: _DiskDispatch) -> None:
    """Fallback driver for any future mode: bare walk, then stamp the root row."""
    d.scanner_pkg._walk_dir(
        d.worker_conn,
        d.disk,
        d.mount,
        d.local_files,
        d.local_dirs,
        d.ctx.generation,
        d.local_resume_from,
        d.local_files_since_ckpt,
        d.local_exhausted,
        d.ctx.started_at_monotonic,
        d.ctx.budget_seconds,
        d.ctx.scan_run_id,
        d.ctx.checkpoint_every_n_files,
    )
    _recompute_root_path(d)


# Table dispatch: mode → driver. Adding a new :class:`ScanMode` is one entry
# here plus its driver — no new ``if/elif`` arm. Modes absent from the table
# fall through to :func:`_dispatch_skeleton` (the bare walk).
_MODE_DISPATCH: dict[ScanMode, Callable[[_DiskDispatch], None]] = {
    ScanMode.full: _dispatch_full,
    ScanMode.quick: _dispatch_quick,
    ScanMode.incremental: _dispatch_incremental,
    ScanMode.enrich: _dispatch_enrich,
    ScanMode.verify: _dispatch_verify,
}
