"""Unit tests for the unified :func:`walk` skeleton (Phase 7 / T8).

The five legacy walkers collapsed into one :func:`walk` skeleton driving
:class:`ScanVisitor` callbacks. These tests pin the traversal-control contract
that :func:`walk` OWNS (independent of any mode's per-file DB writes):

- per-directory callback order: ``enter_dir`` → recurse → ``leave_dir``;
- deterministic sorted-by-name entry order;
- system-name / AppleDouble exclusion;
- crash-resume skip below the resume cursor;
- the UNIFIED SIGTERM check at every file boundary (the drift gap the
  refactor closes) producing a clean ``scan_run.last_path`` checkpoint.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Callable
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import disk_repo, log_repo
from personalscraper.indexer.scanner._walker import (
    ScanVisitor,
    WalkBudget,
    WalkCheckpoint,
    walk,
)
from personalscraper.indexer.schema import DiskRow, ScanRunRow

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Open an in-memory SQLite connection with the indexer migrations applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection, mount: str, label: str = "WalkDisk") -> DiskRow:
    """Insert a minimal disk row rooted at *mount* and return the populated row."""
    now = int(time.time())
    row = DiskRow(
        id=0,
        uuid=f"uuid-{label}",
        label=label,
        mount_path=mount,
        last_seen_at=now,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    disk_id = disk_repo.insert(conn, row)
    return DiskRow(
        id=disk_id,
        uuid=row.uuid,
        label=row.label,
        mount_path=row.mount_path,
        last_seen_at=row.last_seen_at,
        merkle_root=row.merkle_root,
        is_mounted=row.is_mounted,
        unreachable_strikes=row.unreachable_strikes,
    )


def _insert_scan_run(conn: sqlite3.Connection) -> int:
    """Insert a ``running`` scan_run row and return its PK (checkpoint FK target)."""
    return log_repo.insert_scan_run(
        conn,
        ScanRunRow(
            id=0,
            generation=1,
            mode="full",
            disk_filter=None,
            started_at=int(time.time()),
            finished_at=None,
            last_path=None,
            status="running",
            stats_json=None,
        ),
    )


class _RecordingVisitor(ScanVisitor):
    """Visitor that records every callback (and writes no DB rows of its own)."""

    def __init__(self, conn: sqlite3.Connection, disk: DiskRow) -> None:
        super().__init__(conn, disk, generation=1, files_visited=[0], dirs_visited=[0])
        self.events: list[tuple[str, str]] = []

    def enter_dir(self, entry, st, rel) -> bool:  # noqa: ANN001 — DirEntry/stat_result
        """Record the directory entry and always recurse (skeleton default)."""
        self.events.append(("enter_dir", entry.name))
        return True

    def leave_dir(self, entry, st, rel) -> None:  # noqa: ANN001
        """Record the subtree exit (skip the path-row write — not under test)."""
        self.events.append(("leave_dir", entry.name))

    def visit_file(self, entry, st, parent_rel) -> None:  # noqa: ANN001
        """Record the file visit (no DB write)."""
        self.events.append(("visit_file", entry.name))


def _budget() -> WalkBudget:
    """Return an unbounded budget with a fresh exhausted flag."""
    return WalkBudget(budget_seconds=None, started_at_monotonic=time.monotonic(), budget_exhausted=[False])


def _checkpoint(scan_run_id: int, *, every: int = 100, resume: str | None = None) -> WalkCheckpoint:
    """Return a checkpoint context for *scan_run_id*."""
    return WalkCheckpoint(
        scan_run_id=scan_run_id,
        checkpoint_every=every,
        files_since_checkpoint=[0],
        resume_from=[resume],
    )


def _never() -> bool:
    """Shutdown predicate that never fires."""
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWalkCallbackOrder:
    """walk() drives enter_dir → visit_file* → leave_dir in sorted order."""

    def test_visits_files_then_recurses_and_writes_through(self, tmp_path: Path) -> None:
        """Files sort before the subdir; the subtree closes with leave_dir."""
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")
        sub = tmp_path / "zsub"
        sub.mkdir()
        (sub / "c.txt").write_text("c")

        conn = _open_db()
        disk = _insert_disk(conn, str(tmp_path))
        run_id = _insert_scan_run(conn)
        visitor = _RecordingVisitor(conn, disk)

        walk(str(tmp_path), visitor, budget=_budget(), shutdown=_never, checkpoint=_checkpoint(run_id))

        assert visitor.events == [
            ("visit_file", "a.txt"),
            ("visit_file", "b.txt"),
            ("enter_dir", "zsub"),
            ("visit_file", "c.txt"),
            ("leave_dir", "zsub"),
        ]
        assert visitor.files_visited[0] == 3
        assert visitor.dirs_visited[0] == 1

    def test_entries_visited_in_sorted_name_order(self, tmp_path: Path) -> None:
        """Sibling files are visited in ascending name order regardless of FS order."""
        for name in ["m.txt", "a.txt", "z.txt", "c.txt"]:
            (tmp_path / name).write_text("x")

        conn = _open_db()
        disk = _insert_disk(conn, str(tmp_path))
        run_id = _insert_scan_run(conn)
        visitor = _RecordingVisitor(conn, disk)

        walk(str(tmp_path), visitor, budget=_budget(), shutdown=_never, checkpoint=_checkpoint(run_id))

        names = [name for kind, name in visitor.events if kind == "visit_file"]
        assert names == ["a.txt", "c.txt", "m.txt", "z.txt"]


class TestWalkExclusion:
    """walk() skips system names and AppleDouble sidecars."""

    def test_excludes_system_and_appledouble_names(self, tmp_path: Path) -> None:
        """``.DS_Store`` and ``._x`` are never handed to the visitor."""
        (tmp_path / "film.mkv").write_text("v")
        (tmp_path / ".DS_Store").write_text("junk")
        (tmp_path / "._film.mkv").write_text("junk")

        conn = _open_db()
        disk = _insert_disk(conn, str(tmp_path))
        run_id = _insert_scan_run(conn)
        visitor = _RecordingVisitor(conn, disk)

        walk(str(tmp_path), visitor, budget=_budget(), shutdown=_never, checkpoint=_checkpoint(run_id))

        assert [name for kind, name in visitor.events if kind == "visit_file"] == ["film.mkv"]


class TestWalkResumeSkip:
    """walk() honours the crash-resume cursor before visiting a file."""

    def test_files_at_or_before_cursor_are_skipped(self, tmp_path: Path) -> None:
        """With a resume cursor at ``a.txt`` only ``b.txt`` / ``c.txt`` are visited."""
        for name in ["a.txt", "b.txt", "c.txt"]:
            (tmp_path / name).write_text("x")

        conn = _open_db()
        disk = _insert_disk(conn, str(tmp_path), label="ResumeDisk")
        run_id = _insert_scan_run(conn)
        visitor = _RecordingVisitor(conn, disk)

        # Cursor string format is "<label>/<parent_rel>/<filename>"; root files
        # have an empty parent_rel, so the cursor for a.txt is "ResumeDisk//a.txt".
        cursor = "ResumeDisk//a.txt"
        walk(str(tmp_path), visitor, budget=_budget(), shutdown=_never, checkpoint=_checkpoint(run_id, resume=cursor))

        assert [name for kind, name in visitor.events if kind == "visit_file"] == ["b.txt", "c.txt"]
        assert visitor.files_visited[0] == 2


class TestWalkShutdown:
    """walk() checks SIGTERM at EVERY file boundary and checkpoints cleanly."""

    def test_mid_walk_shutdown_stops_and_writes_checkpoint(self, tmp_path: Path) -> None:
        """A shutdown after two files stops the walk with a persisted last_path.

        This is the drift gap the refactor closes: the unified boundary check
        applies to every mode, and the checkpoint (``checkpoint_every=1``) has
        already been written for the last processed file before the walk bails.
        """
        for i in range(10):
            (tmp_path / f"f{i:02d}.txt").write_text("x")

        conn = _open_db()
        disk = _insert_disk(conn, str(tmp_path), label="ShutDisk")
        run_id = _insert_scan_run(conn)
        visitor = _RecordingVisitor(conn, disk)

        def _shutdown_after_two() -> bool:
            """Fire the shutdown once two files have been visited."""
            return visitor.files_visited[0] >= 2

        budget = _budget()
        walk(
            str(tmp_path),
            visitor,
            budget=budget,
            shutdown=_shutdown_after_two,
            checkpoint=_checkpoint(run_id, every=1),
        )

        # Exactly two files were processed before the boundary check bailed.
        assert visitor.files_visited[0] == 2
        # Budget-exhausted mirrors the clean-shutdown contract.
        assert budget.budget_exhausted[0] is True
        # A checkpoint was committed for the last processed file (f01.txt).
        run = log_repo.get_scan_run_by_id(conn, run_id)
        assert run is not None
        assert run.last_path is not None
        assert run.last_path.endswith("f01.txt")


class TestWalkShutdownCallable:
    """The shutdown predicate is injectable (defaults to the module SIGTERM flag)."""

    def test_shutdown_predicate_never_stops_a_clean_walk(self, tmp_path: Path) -> None:
        """A never-firing predicate lets every file through."""
        for i in range(5):
            (tmp_path / f"g{i}.txt").write_text("x")

        conn = _open_db()
        disk = _insert_disk(conn, str(tmp_path))
        run_id = _insert_scan_run(conn)
        visitor = _RecordingVisitor(conn, disk)
        shutdown: Callable[[], bool] = _never

        budget = _budget()
        walk(str(tmp_path), visitor, budget=budget, shutdown=shutdown, checkpoint=_checkpoint(run_id))

        assert visitor.files_visited[0] == 5
        assert budget.budget_exhausted[0] is False
