"""Indexer event catalog.

Hosts the indexer-domain event classes emitted by:

- :func:`personalscraper.indexer.db.check_free_space` and
  :func:`personalscraper.indexer._disk_guard.handle_disk_full` →
  :class:`DiskFullWarning` when a disk-check call discovers free
  space below the safety threshold (or a mid-scan ``OperationalError``
  confirms the disk is full).
- :func:`personalscraper.indexer.scanner.scan` →
  :class:`LibraryScanCompleted` emitted from the function's outer
  ``finally`` block, so every termination path (success, error,
  budget-exhaustion) reports exactly once.

The module is eagerly imported by :mod:`personalscraper.events` so
``Event.__init_subclass__`` registers every concrete class before any
consumer calls ``event_from_envelope``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from personalscraper.core.event_bus import Event


@dataclass(frozen=True, kw_only=True)
class DiskFullWarning(Event):
    """Emitted by the disk-guard when free space falls below the threshold.

    Attributes:
        disk_path: Filesystem path that triggered the warning (the DB file
            path for SQLite-bound checks, or the staging directory for
            ingest-time checks).
        free_bytes: Currently free bytes on the disk hosting ``disk_path``.
            ``0`` is a valid sentinel when the precise value is unavailable
            (e.g. mid-scan ``OperationalError`` paths where SQLite has
            already reported "disk is full" without exposing the byte count).
        threshold_bytes: Bytes required for the call that triggered the
            warning to succeed (typically ``2 × expected_growth_bytes``).
            ``0`` is the convention when no explicit threshold was set.
    """

    disk_path: Path
    free_bytes: int
    threshold_bytes: int


@dataclass(frozen=True, kw_only=True)
class LibraryScanCompleted(Event):
    """Emitted by the indexer scanner at the end of every scan-mode invocation.

    Fires exactly once per ``scan()`` call regardless of exit path
    (success / partial failure / mid-scan exception / pre-item exception)
    — the emit lives in a ``finally`` block. On the failure path, the
    locked formula ``errors = max(scanned - successful, 1)`` guarantees
    ``errors ≥ 1`` so subscribers filtering on ``errors > 0`` always fire.

    Attributes:
        mode: Scan mode string (``"quick"`` | ``"incremental"`` |
            ``"enrich"`` | ``"full"`` | ``"verify"`` | ``"backfill"``).
        scanned: Number of files visited before the scan ended (success
            or exception).
        errors: Count of error conditions encountered. Always ``≥ 0`` on
            the success path; always ``≥ 1`` on the failure path (a scan
            that exits via exception has at least one error: itself).
        elapsed_s: Wall-clock seconds since ``scan()`` was entered
            (``time.monotonic`` delta). Always populated, even on
            failure paths.
    """

    mode: str
    scanned: int
    errors: int
    elapsed_s: float


__all__ = ["DiskFullWarning", "LibraryScanCompleted"]
