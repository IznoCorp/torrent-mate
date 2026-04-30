"""Public types exported by the scanner package.

Provides:
- :class:`IndexerConfigError` — raised for invalid configuration.
- :class:`IndexerScanActiveError` — raised when a concurrent scan is detected.
- :class:`ScanMode` — enum of the four scan modes.
- :class:`ScanRunResult` — lightweight result returned by :func:`scan`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

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
