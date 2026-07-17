"""Scanner orchestration helpers — extracted from :mod:`scanner.__init__`.

Sub-phase 11.6 / S4 decomposes the ~775-line monolithic :func:`scan` into a
thin orchestration shell that delegates setup, per-disk walking, parallel /
sequential dispatch, OK-path finalization, and the
:class:`~personalscraper.indexer.events.LibraryScanCompleted` emission to
small, well-typed helpers in this module.

Design rules:

* These helpers are **private** (``_`` prefix); the only public entry point
  remains :func:`personalscraper.indexer.scanner.scan`.
* No module-level mutable state — all per-run state travels through the
  explicit :class:`_ScanState` dataclass which preserves the
  single-element-list aliasing used by the inner walk helpers
  (``_walk_dir`` and friends mutate ``state.files_visited[0]`` in place).
* The :class:`_DiskWalkContext` dataclass groups the read-only parameters
  derived from :func:`scan`'s public signature so :func:`_scan_one_disk`
  can be invoked from both the parallel worker factories and the
  sequential fallback loop without a 20-argument call site.
"""

from __future__ import annotations

import errno
import json
import platform
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.indexer._fs_capability import NTFS_MACFUSE, FilesystemCapability, resolve_capability
from personalscraper.indexer._fs_probe import _build_mount_table, _run_mount
from personalscraper.indexer.breaker import (
    DiskCircuitBreaker,
    bind_global_disk_breaker_to_bus,
    get_global_disk_breaker,
)
from personalscraper.indexer.events import LibraryScanCompleted
from personalscraper.indexer.merkle import (
    DiskBulkChangeDetected,
    DiskMismatchError,
    DiskMountStatus,
    DiskUnmountedError,
    compute_merkle_root,
)
from personalscraper.indexer.release_linker import recompute_season_episode_counts
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner._concurrency import (
    DiskWorkerFactory,
)
from personalscraper.indexer.scanner._mode_dispatch import (
    _MODE_DISPATCH,
    _DiskDispatch,
    _dispatch_skeleton,
)
from personalscraper.indexer.scanner._spotlight import SpotlightChangeDetector
from personalscraper.indexer.scanner._types import ScanMode, ScanRunResult
from personalscraper.indexer.schema import DiskRow, ScanEventRow, ScanRunRow
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.core.event_bus import EventBus

log = get_logger("indexer.scan")


# Flags that should be present on every macFUSE-mounted NTFS disk for optimal
# I/O behaviour.  These are macOS-specific — nodiratime is Linux-only and
# intentionally excluded from this set.
_RECOMMENDED_MOUNT_FLAGS: frozenset[str] = frozenset(
    {
        "noatime",
        "noappledouble",
        "noapplexattr",
        "defer_permissions",
        "allow_other",
    }
)


# ----------------------------------------------------------------------------
# Pre-walk probes + post-walk finalization
# ----------------------------------------------------------------------------


def _check_mount_flags(disks: list[DiskRow]) -> None:
    """Parse ``mount`` output and warn about missing recommended flags.

    Runs ``mount`` once and inspects the flags reported for each disk's
    :attr:`~personalscraper.indexer.schema.DiskRow.mount_path`.  For every
    flag in :data:`_RECOMMENDED_MOUNT_FLAGS` that is absent, a single
    ``indexer.disk.mount_flags_missing`` warning is emitted at ``WARNING``
    level via structlog.

    The check is:

    * **macOS-only** — skipped (no-op) on any platform where
      ``platform.system() != "Darwin"``.
    * **Non-fatal** — any subprocess failure or unexpected output format
      is caught and logged at ``DEBUG`` level; the scan continues regardless.
    * **Per disk** — each disk with a ``mount_path`` is checked independently.

    Args:
        disks: List of :class:`~personalscraper.indexer.schema.DiskRow` objects
            whose ``mount_path`` fields should be inspected.  Disks whose
            ``mount_path`` is ``None`` are silently skipped.
    """
    # Only applicable on macOS (macFUSE is Darwin-only in this stack).
    if platform.system() != "Darwin":
        return

    # Delegate the mount shell-out + line parsing to the shared FsProbe module
    # (single cached ``mount`` call).  The recommendation logic (which flags to
    # check) stays here.
    mount_output = _run_mount()
    if not mount_output:
        return

    mount_table = _build_mount_table(mount_output)
    # MountInfo.flags holds the option tokens after the fs-type token, which is
    # exactly the set the recommended-flag check needs (noatime, allow_other, …).
    mount_flags: dict[str, frozenset[str]] = {mp: info.flags for mp, info in mount_table.items()}

    # Warn once per disk for each missing recommended flag.
    for disk in disks:
        if disk.mount_path is None:
            continue
        # Normalise: strip trailing slash for comparison (mount output varies).
        mount_point = disk.mount_path.rstrip("/")
        disk_flags: frozenset[str] | None = mount_flags.get(mount_point)
        if disk_flags is None:
            # mount point not found in output — cannot determine flags.
            log.debug(
                "indexer.disk.mount_flags_unknown",
                disk_label=disk.label,
                mount_path=disk.mount_path,
            )
            continue
        missing = _RECOMMENDED_MOUNT_FLAGS - disk_flags
        if missing:
            log.warning(
                "indexer.disk.mount_flags_missing",
                disk_label=disk.label,
                mount_path=disk.mount_path,
                missing_flags=sorted(missing),
                present_flags=sorted(disk_flags),
            )


def _finalize_disk_after_walk(
    conn: sqlite3.Connection,
    disk: DiskRow,
    scan_run_id: int,
    files_visited: int,
    dirs_visited: int,
    capability: FilesystemCapability = NTFS_MACFUSE,
) -> None:
    """Persist post-walk per-disk state: ``merkle_root``, ``last_seen_at``, scan_event.

    Called once per disk after a successful walk (read_success on the circuit
    breaker has already fired).  The function is best-effort: any failure is
    logged at ``warning`` level but does not fail the scan, since the file rows
    have already been committed by the walker.

    Steps:

    1. ``last_seen_at`` is always updated to ``now()`` — the disk was
       observably reachable.
    2. ``merkle_root`` is recomputed only when the on-disk row currently has
       it set to ``NULL`` (i.e. the disk has never been fingerprinted, or a
       previous run cleared it).  Quick/incremental modes already maintain
       merkle_root in their own happy paths via
       :mod:`personalscraper.indexer.scanner._modes`; full scans, which do
       not, fall through to this branch and get their first-ever fingerprint
       written here.  Files with ``oshash IS NULL`` (Stage A only — OSHash
       deferred to ``--mode enrich``) are skipped so a partial Stage A walk
       does not overwrite a real merkle with the empty-set hash.  The
       fingerprints are bucketed by *capability* (via
       :func:`_build_disk_fingerprints`) so the full-scan root is FS-aware and
       byte-equal to what the FIRST incremental/quick scan recomputes — without
       this, the first incremental after a full scan on a coarse FS would see a
       one-version root mismatch.  For NTFS (granularity 1) the bucketing is the
       identity transform, so the stored root is byte-identical to the legacy
       value.
    3. One ``indexer.scan.disk_done`` row is inserted into ``scan_event``
       with the per-disk counters as JSON payload, giving the audit trail a
       durable per-disk endpoint that survives log rotation.

    Args:
        conn: Open SQLite connection.
        disk: The :class:`DiskRow` that was just walked.
        scan_run_id: PK of the active ``scan_run`` row (used as FK on the
            ``scan_event`` insert).
        files_visited: Number of files visited by this walk on this disk.
        dirs_visited: Number of directories visited.
        capability: Per-disk :class:`FilesystemCapability` governing mtime
            bucketing of the recomputed merkle root.  Defaults to
            ``NTFS_MACFUSE`` (granularity 1 → identity), so an un-threaded
            caller stores a byte-identical root.
    """
    # Deferred import so this module's top-level import graph never depends on
    # _walker (avoids any package-init ordering surprise); the walker owns the
    # fingerprint builder.
    from personalscraper.indexer.scanner._walker import _build_disk_fingerprints  # noqa: PLC0415

    now = int(time.time())
    merkle_root: str | None = None

    # Step 1: always touch last_seen_at — the disk responded to the walk.
    disk_repo.update_last_seen_at(conn, disk.id, now)

    # Step 2: recompute merkle_root only when it is currently NULL on the
    # disk row.  Quick/incremental modes already write the right value
    # earlier in their pipeline and we must not clobber it.
    try:
        conn.row_factory = sqlite3.Row
        existing_root_row = conn.execute("SELECT merkle_root FROM disk WHERE id = ?", (disk.id,)).fetchone()
        existing_root: str | None = existing_root_row["merkle_root"] if existing_root_row is not None else None

        if existing_root is None:
            # Reuse the shared fingerprint builder so the full-scan root is
            # bucketed by the disk capability exactly like the quick/incremental
            # short-circuit gates (consistent FS-aware root across all modes).
            fingerprints = _build_disk_fingerprints(conn, disk.id, capability)
            # Only persist a freshly-computed root when at least one file is
            # fully fingerprinted; otherwise leave NULL so the next enrich
            # pass can compute a meaningful value.
            if fingerprints:
                merkle_root = compute_merkle_root(fingerprints)
                disk_repo.update_merkle_root(conn, disk.id, merkle_root)
        else:
            merkle_root = existing_root
    except sqlite3.Error as exc:
        log.warning(
            "indexer.scan.merkle_root_failed",
            disk_id=disk.id,
            label=disk.label,
            error=str(exc),
            error_type=type(exc).__name__,
        )

    # Step 4: emit a structured scan_event row so the audit trail of "which
    # disk got scanned in which run" survives in the DB beyond log files.
    try:
        log_repo.insert_scan_event(
            conn,
            ScanEventRow(
                id=0,
                scan_id=scan_run_id,
                ts=now,
                item_id=None,
                file_id=None,
                event="indexer.scan.disk_done",
                payload_json=json.dumps(
                    {
                        "disk_id": disk.id,
                        "label": disk.label,
                        "files_visited": files_visited,
                        "dirs_visited": dirs_visited,
                        "merkle_root": merkle_root,
                    }
                ),
            ),
        )
    except sqlite3.Error as exc:
        log.warning(
            "indexer.scan.event_insert_failed",
            disk_id=disk.id,
            scan_event="indexer.scan.disk_done",
            error=str(exc),
            error_type=type(exc).__name__,
        )


# ----------------------------------------------------------------------------
# State containers
# ----------------------------------------------------------------------------


@dataclass
class _ScanState:
    """Mutable per-run counters and flags shared with nested walk helpers.

    Each field is a single-element list so the existing walker helpers
    (``_walk_dir``, ``_scan_disk_full``, …) keep mutating in place via
    ``state.files_visited[0] += 1`` without nonlocal declarations. Wall-clock
    fields are scalars because they are read-only after :func:`scan` start.
    """

    files_visited: list[int] = field(default_factory=lambda: [0])
    dirs_visited: list[int] = field(default_factory=lambda: [0])
    disks_skipped: list[int] = field(default_factory=lambda: [0])
    resume_from: list[str | None] = field(default_factory=lambda: [None])
    files_since_checkpoint: list[int] = field(default_factory=lambda: [0])
    budget_exhausted: list[bool] = field(default_factory=lambda: [False])
    emit_raised: list[bool] = field(default_factory=lambda: [False])
    started_at_monotonic: float = 0.0
    emit_started_monotonic: float = 0.0


@dataclass
class _DiskWalkContext:
    """Read-only per-run parameters needed by :func:`_scan_one_disk`.

    Groups the scan-level config knobs forwarded unchanged to the per-disk
    mode dispatch. Bundling them here lets :func:`_scan_one_disk` keep a
    compact signature instead of receiving 15+ positional parameters.

    The ``started_at_monotonic`` field is the run-wide :func:`time.monotonic`
    timestamp captured before any disk is walked; the per-disk mode helpers
    consult it together with ``budget_seconds`` to detect time-budget
    exhaustion.

    ``fs_type_overrides`` maps the STABLE disk identity (``DiskConfig.id``,
    persisted as the immutable ``DiskRow.label``) to the canonical
    ``DiskConfig.fs_type`` override for that disk.  It threads the operator
    override into the scanner so capability resolution is consistent with the
    dispatch (transfer) layer — both route through
    :func:`~personalscraper.indexer._fs_capability.resolve_capability`.  Keying
    on ``label`` rather than the mutable ``mount_path`` (rewritten on remount,
    NULL on unmount) guarantees scan and transfer never diverge.  An empty dict
    (the default) means no overrides → pure auto-detection, preserving the
    historical scanner behaviour.
    """

    mode: ScanMode
    drop_indexes: bool
    generation: int
    scan_run_id: int
    checkpoint_every_n_files: int
    dir_mtime_reliable: bool
    budget_seconds: float | None
    confirm_bulk_change: bool
    merkle_delta_freeze_threshold: float
    paranoia_window_seconds: int
    quick_enrich: bool
    backfill_streams: bool
    no_enqueue: bool
    breaker: DiskCircuitBreaker
    started_at_monotonic: float = 0.0
    fs_type_overrides: dict[str, str] = field(default_factory=dict)


# Mapping reused by :func:`_scan_one_disk` when classifying mount-guard
# failures into human-readable reason codes for the warning log line.
_MOUNT_STATUS_TO_REASON: dict[DiskMountStatus, str] = {
    DiskMountStatus.UNMOUNTED: "mount_inaccessible",
    DiskMountStatus.NO_SENTINEL: "sentinel_missing",
    DiskMountStatus.MOUNTED_WRONG_DISK: "sentinel_mismatch",
}


# ----------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------


def _setup_scan_run(
    disks: list[DiskRow],
    mode: ScanMode,
    generation: int,
    conn: sqlite3.Connection,
    disk_filter: str | None,
    started_at: int,
    *,
    spotlight_enabled: bool,
    staging_dir: str | None,
    disk_breaker: DiskCircuitBreaker | None,
    event_bus: "EventBus",
    check_mount_flags: Callable[[list[DiskRow]], None],
) -> tuple[int, DiskCircuitBreaker, SpotlightChangeDetector, bool]:
    """Insert the ``scan_run`` row, run pre-walk probes, resolve the breaker.

    Encapsulates the work historically done inline at the top of
    :func:`scan`: mount-flag inspection, Spotlight availability probe,
    ``scan_run`` insertion (status=running), circuit-breaker resolution,
    and the one-time directory-mtime reliability check for quick /
    incremental modes.

    Args:
        disks: Disks scheduled for the run.
        mode: Active :class:`ScanMode`.
        generation: Generation counter stamped on every visited row.
        conn: Open SQLite connection.
        disk_filter: Optional single-disk label scoping.
        started_at: Epoch seconds — persisted on the ``scan_run`` row.
        spotlight_enabled: Whether to opt-in to Spotlight change detection.
        staging_dir: Optional staging path probed alongside disk mounts.
        disk_breaker: Caller-supplied breaker for test isolation; ``None``
            triggers the module-level singleton.
        event_bus: Bus used to rebind the global breaker when no explicit
            breaker is supplied.
        check_mount_flags: Pre-walk macOS mount-flags inspector.

    Returns:
        Tuple ``(scan_run_id, breaker, spotlight_detector, dir_mtime_reliable)``.
    """
    # Non-fatal mount-flag inspection.
    check_mount_flags(disks)

    # Spotlight probe (sub-phase 4.8) — log availability for every mount and
    # the staging dir; try_attach silently refuses macFUSE paths.
    spotlight_detector = SpotlightChangeDetector()
    probe_paths: list[tuple[str, bool]] = []
    for disk in disks:
        if disk.mount_path is not None:
            probe_paths.append((disk.mount_path, spotlight_enabled))
    if staging_dir is not None:
        probe_paths.append((staging_dir, spotlight_enabled))
    for probe_path, sp_enabled in probe_paths:
        spotlight_detector.try_attach(probe_path, sp_enabled)

    # Insert scan_run row with status=running.
    scan_run_id = log_repo.insert_scan_run(
        conn,
        ScanRunRow(
            id=0,
            generation=generation,
            mode=mode.value,
            disk_filter=disk_filter,
            started_at=started_at,
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )

    # Resolve the circuit breaker: caller-supplied wins for test isolation;
    # otherwise fall back to the module-level singleton and rebind its bus
    # so disk-circuit transitions reach live subscribers (review finding C2).
    if disk_breaker is not None:
        breaker: DiskCircuitBreaker = disk_breaker
    else:
        breaker = get_global_disk_breaker()
        bind_global_disk_breaker_to_bus(event_bus)

    # One-time dir-mtime reliability check for quick and incremental modes.
    # Resolved via the package namespace so tests that patch
    # ``personalscraper.indexer.scanner._verify_dir_mtime_reliable`` reach the
    # live binding (DirMtime test family in tests/indexer/test_scanner.py).
    dir_mtime_reliable: bool = True
    if mode in (ScanMode.quick, ScanMode.incremental):
        from personalscraper.indexer import scanner as _scanner_pkg  # noqa: PLC0415

        dir_mtime_reliable = _scanner_pkg._verify_dir_mtime_reliable()

    return scan_run_id, breaker, spotlight_detector, dir_mtime_reliable


# ----------------------------------------------------------------------------
# Per-disk dispatch
# ----------------------------------------------------------------------------


def _scan_one_disk(
    worker_conn: sqlite3.Connection,
    disk: DiskRow,
    state: _ScanState,
    ctx: _DiskWalkContext,
    finalize_after_walk: Callable[[sqlite3.Connection, DiskRow, int, int, int, FilesystemCapability], None],
    local_files: list[int],
    local_dirs: list[int],
    local_skipped: list[int],
    local_exhausted: list[bool],
    local_resume_from: list[str | None],
    local_files_since_ckpt: list[int],
) -> None:
    """Perform all scan steps for a single disk using *worker_conn*.

    Encapsulates the mount/circuit guards, mode dispatch, and per-disk I/O
    error handling that previously lived inline in :func:`scan`'s
    ``for disk in disks`` body. Invoked either directly (sequential
    fallback) or from within a thread-pool worker (parallel path).

    The ``local_*`` counters are kept separate from ``state.*`` so the
    parallel path can swap in worker-local list aliases while still sharing
    the outer :class:`_ScanState` across threads.

    Args:
        worker_conn: SQLite connection owned by the calling thread.
        disk: :class:`DiskRow` to scan.
        state: Shared :class:`_ScanState` (read-only here).
        ctx: Read-only walk parameters bundled in :class:`_DiskWalkContext`.
        finalize_after_walk: Callback that persists ``merkle_root`` /
            ``last_seen_at`` / ``scan_event`` for the disk after a clean walk.
        local_files: Per-disk file counter.
        local_dirs: Per-disk directory counter.
        local_skipped: Per-disk Merkle-hit skip counter.
        local_exhausted: Per-disk budget-exhausted flag.
        local_resume_from: Per-disk crash-resume path.
        local_files_since_ckpt: Per-disk checkpoint counter.
    """
    del state  # currently unused — kept for forward extensibility

    # Deferred import so tests that patch ``scanner.guard_disk_mounted``,
    # ``scanner.verify_disk_mounted`` or any mode dispatcher (``_scan_disk_full``
    # etc.) keep working — every callable that has a re-export in the scanner
    # package namespace is resolved through ``_scanner_pkg`` so the live
    # (possibly patched) binding wins over the hard module import this file
    # uses for type-checking only.
    from personalscraper.indexer import scanner as _scanner_pkg  # noqa: PLC0415

    if disk.mount_path is None:
        log.warning(
            "indexer.scan.disk_skipped",
            disk_id=disk.id,
            label=disk.label,
            reason="no mount_path",
        )
        return

    # Circuit-breaker guard: skip disks whose circuit is OPEN.
    if ctx.breaker.is_open(disk.uuid):
        log.warning(
            "indexer.disk.breaker_open",
            disk_uuid=disk.uuid,
            label=disk.label,
            reason="circuit_open_skip",
        )
        return

    # Guard: verify disk is mounted and identity sentinel matches. Pre-classify
    # the mount state so the warning carries a human-readable reason code
    # instead of a raw UUID from str(exc).
    mount_status = _scanner_pkg.verify_disk_mounted(disk)
    try:
        _scanner_pkg.guard_disk_mounted(disk)
    except DiskUnmountedError:
        log.warning(
            "indexer.disk.skipped_unmounted",
            disk_id=disk.id,
            label=disk.label,
            reason=_MOUNT_STATUS_TO_REASON.get(mount_status, "mount_inaccessible"),
            disk_uuid=disk.uuid,
        )
        return
    except DiskMismatchError as exc:
        log.warning(
            "indexer.disk.skipped_unmounted",
            disk_id=disk.id,
            label=disk.label,
            reason=_MOUNT_STATUS_TO_REASON.get(mount_status, "sentinel_mismatch"),
            disk_uuid=disk.uuid,
            expected_uuid=exc.expected,
            found_uuid=exc.found,
        )
        return

    mount = disk.mount_path
    log.info("indexer.scan.disk_start", disk_id=disk.id, label=disk.label, mount_path=mount)

    # Resolve the per-disk FilesystemCapability via the SHARED resolver so the
    # scanner honours the ``DiskConfig.fs_type`` operator override exactly like
    # the dispatch (transfer) layer — one knob, one behaviour. When no override
    # is supplied for this mount the resolver auto-detects via the read-time
    # mount probe (authoritative for drift); an unrecognised / unprobeable mount
    # falls back to the NTFS-safe "unknown" superset (full ctime + exact mtime),
    # which is byte-identical to the legacy behaviour.
    # Look the override up by the STABLE ``DiskRow.label`` (== ``DiskConfig.id``),
    # NOT the mutable ``mount`` path: ``mount_path`` is rewritten on remount and
    # NULL on unmount, so keying on it would silently drop the operator override
    # while the transfer layer (which resolves from the DiskConfig directly) kept
    # it. The label is set once at bootstrap and never changes, so the scan and
    # transfer capability resolutions stay in lock-step.
    disk_capability = resolve_capability(mount, ctx.fs_type_overrides.get(disk.label))

    # The capability may hard-wire dir-mtime reliability (APFS/HFS+ default True);
    # otherwise fall back to the session-wide runtime probe. NTFS leaves this at
    # None → effective value equals the session probe (ctx.dir_mtime_reliable),
    # so the NTFS path is unchanged.
    if disk_capability.dir_mtime_reliable_default is not None:
        effective_dir_mtime_reliable = disk_capability.dir_mtime_reliable_default
    else:
        effective_dir_mtime_reliable = ctx.dir_mtime_reliable

    # Mode dispatch via the registry table: one entry per :class:`ScanMode`
    # (see :data:`_MODE_DISPATCH`). The driver is resolved through the scanner
    # package namespace inside each handler so ``unittest.mock`` patches on
    # ``scanner._scan_disk_*`` / ``scanner._walk_dir`` still intercept. Modes
    # not in the table fall through to the bare-walk skeleton driver.
    dispatch = _DiskDispatch(
        scanner_pkg=_scanner_pkg,
        worker_conn=worker_conn,
        disk=disk,
        mount=mount,
        capability=disk_capability,
        dir_mtime_reliable=effective_dir_mtime_reliable,
        ctx=ctx,
        local_files=local_files,
        local_dirs=local_dirs,
        local_skipped=local_skipped,
        local_resume_from=local_resume_from,
        local_files_since_ckpt=local_files_since_ckpt,
        local_exhausted=local_exhausted,
    )

    try:
        _MODE_DISPATCH.get(ctx.mode, _dispatch_skeleton)(dispatch)

    except DiskBulkChangeDetected:
        # Merkle delta exceeded the freeze threshold — re-raise so the caller
        # (sequential loop or parallel wrapper) can surface it.
        raise
    except PermissionError as perm_exc:
        # Per-file EACCES: log a warning and return (no strike against the disk).
        # PermissionError is a subclass of OSError so it MUST be matched first;
        # otherwise the OSError clause below would always win.
        log.warning(
            "indexer.file.permission_denied",
            disk_uuid=disk.uuid,
            label=disk.label,
            error=str(perm_exc),
        )
        return
    except OSError as io_exc:
        # I/O error: roll back, mark unmounted, increment unreachable strikes,
        # let the circuit breaker decide whether to open. Scan continues on
        # remaining disks.
        if io_exc.errno in (errno.EIO, errno.ENOENT, errno.ENOTCONN, errno.ETIMEDOUT):
            worker_conn.rollback()
            disk_repo.update_is_mounted(worker_conn, disk.id, is_mounted=0)
            new_strikes = disk.unreachable_strikes + 1
            disk_repo.update_unreachable_strikes(worker_conn, disk.id, new_strikes)
            ctx.breaker.record_failure(disk.uuid)
            log.warning(
                "indexer.disk.io_error",
                disk_uuid=disk.uuid,
                label=disk.label,
                errno=io_exc.errno,
                error=str(io_exc),
                unreachable_strikes=new_strikes,
            )
            return
        raise
    else:
        # Walk completed without I/O error — record success so the breaker
        # can transition HALF_OPEN → CLOSED if it was recovering.
        ctx.breaker.record_success(disk.uuid)

    log.info(
        "indexer.scan.disk_done",
        disk_id=disk.id,
        label=disk.label,
        files_visited=local_files[0],
        dirs_visited=local_dirs[0],
    )

    # Persist post-walk per-disk state (merkle_root, last_seen_at, scan_event).
    # Thread the resolved capability so the full-scan merkle root store is
    # FS-aware (bucketed) and byte-equal to what the first incremental/quick
    # short-circuit recomputes for this disk.
    finalize_after_walk(
        worker_conn,
        disk,
        ctx.scan_run_id,
        local_files[0],
        local_dirs[0],
        disk_capability,
    )


# ----------------------------------------------------------------------------
# Walk dispatch
# ----------------------------------------------------------------------------


def _run_parallel_walk(
    disks: list[DiskRow],
    db_path: Path,
    state: _ScanState,
    ctx: _DiskWalkContext,
    finalize_after_walk: Callable[[sqlite3.Connection, DiskRow, int, int, int, FilesystemCapability], None],
    max_workers: int,
) -> None:
    """Spawn one worker per disk and run :func:`_scan_one_disk` concurrently.

    Each worker owns its own SQLite connection (opened by
    :func:`_run_disks_in_parallel`). Per-disk crash-resume and checkpoint
    counters are kept worker-local so progress on one disk doesn't bleed
    into another; the file / dir / skipped / budget counters in *state*
    are shared across threads through the single-element-list aliasing.
    """

    def _make_factory(d: DiskRow) -> DiskWorkerFactory:
        """Build a :class:`DiskWorkerFactory` closure for disk *d*."""

        def _factory(
            lf: list[int],
            ld: list[int],
            ls: list[int],
            le: list[bool],
        ) -> Callable[[sqlite3.Connection], None]:
            """Return the per-disk scan callable bound to *d*."""
            local_rf: list[str | None] = [state.resume_from[0]]
            local_fc: list[int] = [0]

            def _worker(wc: sqlite3.Connection) -> None:
                _scan_one_disk(
                    wc,
                    d,
                    state,
                    ctx,
                    finalize_after_walk,
                    lf,
                    ld,
                    ls,
                    le,
                    local_rf,
                    local_fc,
                )

            return _worker

        return _factory

    factories: list[DiskWorkerFactory] = [_make_factory(d) for d in disks]
    # Deferred lookup so tests that patch ``scanner._run_disks_in_parallel``
    # (see tests/indexer/test_scan_completed_events.py) reach the patched
    # binding through the package namespace.
    from personalscraper.indexer import scanner as _scanner_pkg  # noqa: PLC0415

    worker_errors = _scanner_pkg._run_disks_in_parallel(
        factories,
        db_path,
        max_workers=max_workers,
        shared_files_visited=state.files_visited,
        shared_dirs_visited=state.dirs_visited,
        shared_disks_skipped=state.disks_skipped,
        shared_budget_exhausted=state.budget_exhausted,
    )
    if worker_errors:
        raise RuntimeError("; ".join(worker_errors))


def _run_sequential_walk(
    disks: list[DiskRow],
    conn: sqlite3.Connection,
    state: _ScanState,
    ctx: _DiskWalkContext,
    finalize_after_walk: Callable[[sqlite3.Connection, DiskRow, int, int, int, FilesystemCapability], None],
) -> None:
    """Walk every disk on the calling thread using the shared *conn*.

    Used when the database lives in memory (no per-thread connection
    possible), when only one effective worker is wanted, or when a
    single-disk filter is active (DESIGN §11.8).
    """
    for disk in disks:
        _scan_one_disk(
            conn,
            disk,
            state,
            ctx,
            finalize_after_walk,
            state.files_visited,
            state.dirs_visited,
            state.disks_skipped,
            state.budget_exhausted,
            state.resume_from,
            state.files_since_checkpoint,
        )
        # Stop iterating disks if the budget was exhausted mid-walk.
        if state.budget_exhausted[0]:
            break


# ----------------------------------------------------------------------------
# Finalization + emission
# ----------------------------------------------------------------------------


def _finalize_ok_scan_run(
    conn: sqlite3.Connection,
    mode: ScanMode,
    scan_run_id: int,
    state: _ScanState,
    *,
    budget_seconds: float | None,
) -> ScanRunResult:
    """Mark ``scan_run`` ok, persist stats, return the :class:`ScanRunResult`.

    Handles both the budget-exhausted early-return and the all-disks-clean
    completion paths. Enrich mode also triggers
    :func:`recompute_season_episode_counts` here so per-show counters reflect
    the just-finished pass.
    """
    if state.budget_exhausted[0]:
        if mode == ScanMode.enrich:
            recompute_season_episode_counts(conn)
        finished_at = int(time.time())
        stats: dict[str, int] = {
            "files_visited": state.files_visited[0],
            "dirs_visited": state.dirs_visited[0],
        }
        conn.execute(
            "UPDATE scan_run SET stats_json = ?, status = 'ok', finished_at = ? WHERE id = ?",
            (json.dumps(stats), finished_at, scan_run_id),
        )
        conn.commit()
        log.info(
            "indexer.scan.budget_exhausted",
            scan_run_id=scan_run_id,
            files_visited=state.files_visited[0],
            budget_seconds=budget_seconds,
        )
        return ScanRunResult(
            scan_run_id=scan_run_id,
            files_visited=state.files_visited[0],
            dirs_visited=state.dirs_visited[0],
            status="ok",
            disks_skipped=state.disks_skipped[0],
            budget_exhausted=True,
        )

    # All disks processed — mark scan_run ok via the repo helper so all status
    # transitions share one write path.
    if mode == ScanMode.enrich:
        recompute_season_episode_counts(conn)
    finished_at = int(time.time())
    final_stats: dict[str, int] = {
        "files_visited": state.files_visited[0],
        "dirs_visited": state.dirs_visited[0],
        "disks_skipped": state.disks_skipped[0],
    }
    log_repo.update_scan_run_status(
        conn,
        scan_run_id,
        "ok",
        finished_at=finished_at,
        stats_json=json.dumps(final_stats),
    )
    return ScanRunResult(
        scan_run_id=scan_run_id,
        files_visited=state.files_visited[0],
        dirs_visited=state.dirs_visited[0],
        status="ok",
        disks_skipped=state.disks_skipped[0],
    )


def _mark_scan_run_failed(conn: sqlite3.Connection, scan_run_id: int) -> None:
    """Best-effort update of ``scan_run`` to ``status='failed'`` on error paths.

    Shared by the :class:`DiskBulkChangeDetected` and generic ``Exception``
    branches in :func:`scan` so neither path leaves a dangling ``running``
    row behind.
    """
    finished_at = int(time.time())
    log_repo.update_scan_run_status(conn, scan_run_id, "failed", finished_at=finished_at)


def _emit_completion(
    event_bus: "EventBus",
    source: str,
    mode: ScanMode,
    state: _ScanState,
) -> None:
    """Emit the :class:`LibraryScanCompleted` event in the scan's finally block.

    Fires exactly once per :func:`scan` invocation regardless of exit path:
    success, partial failure, or mid-scan exception. Applies the locked
    formula ``errors = max(scanned - successful, 1)`` which simplifies to
    ``max(disks_skipped, 1)`` on the failure path (we don't track a
    separate "successful" counter; ``disks_skipped`` is the proxy error
    count). On success, ``errors == disks_skipped`` (which is ``0`` when
    every disk processed cleanly).
    """
    emit_errors = max(state.disks_skipped[0], 1) if state.emit_raised[0] else state.disks_skipped[0]
    event_bus.emit(
        LibraryScanCompleted(
            source=source,
            mode=mode.value,
            scanned=state.files_visited[0],
            errors=emit_errors,
            elapsed_s=time.monotonic() - state.emit_started_monotonic,
        ),
    )
