"""Public types exported by the scanner package.

Provides:
- :class:`IndexerConfigError` — raised for invalid configuration.
- :class:`IndexerScanActiveError` — raised when a concurrent scan is detected.
- :class:`ScanMode` — enum of the four scan modes.
- :class:`ScanRequest` — frozen bundle of every input consumed by :func:`scan`.
- :class:`ScanRunResult` — lightweight result returned by :func:`scan`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from personalscraper.conf.models.config import Config
    from personalscraper.core.event_bus import EventBus
    from personalscraper.indexer.breaker import DiskCircuitBreaker
    from personalscraper.indexer.schema import DiskRow

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class IndexerConfigError(ValueError):
    """Raised when scanner configuration is invalid.

    Typical triggers:
    - ``--disk D`` references a label that is not present in the configured disk list.

    Args:
        message: Human-readable description of the configuration problem.
    """

    def __init__(self, message: str) -> None:
        """Initialize with a human-readable message."""
        super().__init__(message)


class IndexerScanActiveError(RuntimeError):
    """Raised when a scan is already running according to the lock file.

    Callers should catch this to avoid launching a second concurrent scan
    against the same database, which would corrupt generation counters and
    checkpoint state.
    """


# ---------------------------------------------------------------------------
# ScanMode
# ---------------------------------------------------------------------------


class ScanMode(str, Enum):
    """Enumeration of available scan modes.

    Members:
        quick: Merkle short-circuit + dir-mtime subtree skip.
        incremental: Changed-files only based on dir-mtime deltas.
        enrich: Re-run mediainfo / NFO / artwork on un-enriched files.
        full: Walk every file on every disk and (re-)compute tier-1 fingerprints.
        verify: Re-stat every indexed file and escalate mismatches to the repair
            queue without soft-deleting.

    Note:
        The ``scan_run.mode`` SQL CHECK constraint also accepts ``'repair'``
        as a forward-compatibility allowance — currently no scanner mode is
        associated with that value (``library-repair`` drains the outbox
        without launching a scan, so it never writes a ``scan_run`` row).
    """

    quick = "quick"
    incremental = "incremental"
    enrich = "enrich"
    full = "full"
    verify = "verify"


# ---------------------------------------------------------------------------
# ScanRunResult
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanRunResult:
    """Summary result returned by :func:`scan`.

    Frozen so callers cannot mutate a result after the scan has completed —
    the values reflect a snapshot of the scan's outcome.

    Args:
        scan_run_id: PK of the ``scan_run`` row created for this scan.
        files_visited: Number of file entries visited across all disks.
        dirs_visited: Number of directory entries visited (including disk roots).
        status: Final status string — ``'ok'`` or ``'failed'``.
        disks_skipped: Number of disks short-circuited by the Merkle match in
            quick mode (Merkle root matched → zero FS reads for that disk).
        budget_exhausted: ``True`` when the scan was stopped early because
            ``budget_seconds`` was reached before all files were visited.
        error: Human-readable error message; ``None`` on success.
    """

    scan_run_id: int
    files_visited: int
    dirs_visited: int
    status: str
    disks_skipped: int = 0
    budget_exhausted: bool = field(default=False)
    error: str | None = None


# ---------------------------------------------------------------------------
# ScanRequest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class ScanRequest:
    """Immutable, keyword-only bundle of every parameter consumed by :func:`scan`.

    Collapses the historical ~22-argument ``scan()`` signature into a single
    frozen value object so the scan orchestrator and the per-mode visitors
    receive ONE object instead of a long positional argument list. Construct it
    directly and pass it to
    :func:`personalscraper.indexer.scanner.scan_with`; the legacy
    :func:`personalscraper.indexer.scanner.scan` keeps its positional/keyword
    signature and builds a :class:`ScanRequest` internally for backward
    compatibility, so behaviour is byte-identical whichever entry point a caller
    uses.

    Frozen so a request cannot be mutated after construction — the values are a
    snapshot of the scan's inputs. ``event_bus`` is REQUIRED (no default),
    mirroring the required-bus contract enforced directly on ``scan()``.

    See :func:`personalscraper.indexer.scanner.scan` for the exhaustive
    per-field semantics; the one-line summaries below mirror that docstring.

    Attributes:
        disks: Disks to scan; unmounted/mismatched disks are skipped, not fatal.
        mode: The :class:`ScanMode` governing the per-disk walk strategy.
        generation: Monotonic generation counter stamped on visited rows.
        conn: Open autocommit :class:`sqlite3.Connection` (or caller transaction).
        event_bus: Required :class:`EventBus`; exactly one
            ``LibraryScanCompleted`` is emitted per scan.
        disk_filter: Single-disk label scope (``--disk``); ``None`` = all disks.
        drop_indexes: Drop/recreate secondary indexes around full-mode bulk inserts.
        budget_seconds: Wall-clock ceiling in seconds; ``None`` = unlimited.
        db_path: SQLite file path; enables crash-resume + parallel per-disk conns.
        checkpoint_every_n_files: Files processed between checkpoint writes.
        disk_breaker: Per-disk circuit breaker; ``None`` = module-level singleton.
        confirm_bulk_change: Bypass the quick-mode Merkle delta freeze guard.
        merkle_delta_freeze_threshold: Quick-mode freeze threshold (0.0–1.0).
        quick_enrich: Faster/less-complete mediainfo parse in enrich mode.
        backfill_streams: Targeted stream-column backfill in enrich mode.
        max_workers: Max concurrent per-disk worker threads.
        read_rate_mb_per_sec: Shared read-rate ceiling in MB/s; ``None`` = no throttle.
        staging_dir: Staging dir probed for Spotlight in addition to disk mounts.
        spotlight_enabled: Whether the Spotlight change detector may attach.
        paranoia_window_seconds: Quick-mode paranoia look-back window (seconds).
        no_enqueue: Verify mode walks every file but never enqueues repairs.
        fs_type_overrides: Stable-label → canonical ``fs_type`` override map.
        config: Fully-loaded :class:`Config`; full-mode item stage (pass 1) runs
            exactly once when provided, is skipped when ``None``.
    """

    disks: list[DiskRow]
    mode: ScanMode
    generation: int
    conn: sqlite3.Connection
    event_bus: EventBus
    disk_filter: str | None = None
    drop_indexes: bool = False
    budget_seconds: float | None = None
    db_path: Path | None = None
    checkpoint_every_n_files: int = 100
    disk_breaker: DiskCircuitBreaker | None = None
    confirm_bulk_change: bool = False
    merkle_delta_freeze_threshold: float = 0.50
    quick_enrich: bool = False
    backfill_streams: bool = False
    max_workers: int = 4
    read_rate_mb_per_sec: float | None = None
    staging_dir: str | None = None
    spotlight_enabled: bool = False
    paranoia_window_seconds: int = 86400
    no_enqueue: bool = False
    fs_type_overrides: dict[str, str] | None = None
    config: Config | None = None
