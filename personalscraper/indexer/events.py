"""Indexer event catalog — Sub-phase 4.2b + 4.5.

Hosts the indexer-domain event classes emitted by:

- :func:`personalscraper.indexer.db.check_free_space` and
  :func:`personalscraper.indexer._disk_guard.handle_disk_full` →
  :class:`DiskFullWarning` when a disk-check call discovers free
  space below the safety threshold (or a mid-scan ``OperationalError``
  confirms the disk is full).
- :mod:`personalscraper.indexer.scanner._modes` orchestrator →
  :class:`LibraryScanCompleted` (added in Sub-phase 4.5).

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


__all__ = ["DiskFullWarning"]
