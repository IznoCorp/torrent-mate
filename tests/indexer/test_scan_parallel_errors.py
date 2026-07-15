"""Tests for error propagation in the parallel disk-walk dispatcher.

Covers ``_run_disks_in_parallel`` (personalscraper.indexer.scanner._concurrency):

- A worker raising :class:`DiskBulkChangeDetected` must surface the TYPED
  exception to the caller (not a stringified ``RuntimeError``), so the CLI's
  freeze handling (actionable message + exit code 3) engages in parallel mode
  exactly as it does in sequential mode (2026-07-15 freeze incident: the CLI
  crashed with a raw ``RuntimeError`` traceback instead).
- A worker raising any other exception keeps the existing contract: the error
  is collected as a string and the remaining workers proceed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.indexer.merkle import DiskBulkChangeDetected
from personalscraper.indexer.scanner._concurrency import _run_disks_in_parallel

# Each worker normally opens its own file-backed connection; the dispatcher
# tests only exercise error propagation, so in-memory connections avoid
# cross-worker lock contention on a freshly created DB file.
_OPEN_CONN_PATCH = "personalscraper.indexer.scanner._concurrency._open_worker_conn"


def _memory_conn(_db_path: Path) -> sqlite3.Connection:
    """Return a throwaway in-memory connection (one per worker)."""
    return sqlite3.connect(":memory:")


def _factory_raising(exc: Exception):
    """Return a worker factory whose worker raises *exc*."""

    def _factory(
        lf: list[int],
        ld: list[int],
        ls: list[int],
        le: list[bool],
    ):
        def _worker(conn: sqlite3.Connection) -> None:
            raise exc

        return _worker

    return _factory


def _factory_ok(files: int = 3):
    """Return a worker factory whose worker succeeds and counts *files*."""

    def _factory(
        lf: list[int],
        ld: list[int],
        ls: list[int],
        le: list[bool],
    ):
        def _worker(conn: sqlite3.Connection) -> None:
            lf[0] += files

        return _worker

    return _factory


def _run(factories, db_path: Path) -> tuple[list[str], list[int]]:
    """Invoke ``_run_disks_in_parallel`` with fresh shared counters."""
    shared_files: list[int] = [0]
    with patch(_OPEN_CONN_PATCH, side_effect=_memory_conn):
        errors = _run_disks_in_parallel(
            factories,
            db_path,
            max_workers=2,
            shared_files_visited=shared_files,
            shared_dirs_visited=[0],
            shared_disks_skipped=[0],
            shared_budget_exhausted=[False],
        )
    return errors, shared_files


class TestParallelBulkChangePropagation:
    """`DiskBulkChangeDetected` must cross the thread-pool boundary typed."""

    def test_bulk_change_reraised_typed(self, tmp_path: Path) -> None:
        """A frozen disk raises DiskBulkChangeDetected, not RuntimeError."""
        freeze = DiskBulkChangeDetected(delta=0.86, disk_uuid="UUID-FROZEN")
        with pytest.raises(DiskBulkChangeDetected) as excinfo:
            _run([_factory_raising(freeze)], tmp_path / "lib.db")
        assert excinfo.value.disk_uuid == "UUID-FROZEN"
        assert excinfo.value.delta == 0.86

    def test_bulk_change_waits_for_other_workers(self, tmp_path: Path) -> None:
        """Healthy sibling workers complete (and merge counters) before the re-raise."""
        freeze = DiskBulkChangeDetected(delta=0.86, disk_uuid="UUID-FROZEN")
        shared_files: list[int] = [0]
        with patch(_OPEN_CONN_PATCH, side_effect=_memory_conn), pytest.raises(DiskBulkChangeDetected):
            _run_disks_in_parallel(
                [_factory_raising(freeze), _factory_ok(files=7)],
                tmp_path / "lib.db",
                max_workers=2,
                shared_files_visited=shared_files,
                shared_dirs_visited=[0],
                shared_disks_skipped=[0],
                shared_budget_exhausted=[False],
            )
        assert shared_files[0] == 7, "the healthy disk's counters must still merge"

    def test_other_exceptions_keep_string_contract(self, tmp_path: Path) -> None:
        """Non-freeze worker failures stay collected as error strings."""
        errors, shared_files = _run(
            [_factory_raising(ValueError("boom")), _factory_ok(files=5)],
            tmp_path / "lib.db",
        )
        assert len(errors) == 1
        assert "boom" in errors[0]
        assert shared_files[0] == 5
