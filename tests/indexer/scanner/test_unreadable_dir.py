"""A directory the walk cannot list keeps its files in the index.

The walk used to log ``indexer.scan.dir_permission_denied`` and go on as if the
directory were empty; the miss strikes and the soft-deletes that run after it then
read every file below as « not seen », hence gone. These tests pin the contract:

- the walk reports the directory (relative path) on the visitor;
- a full scan's strikes and soft-deletes leave the files under it alone, strikes
  neither reset nor raised, while a file really gone elsewhere is still struck;
- a per-file ``PermissionError`` that stops the walk early counts as a truncated
  run, so its strikes are skipped.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from personalscraper.core.event_bus import EventBus
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.drift import apply_soft_deletes, mark_missed_files
from personalscraper.indexer.repos import disk_repo
from personalscraper.indexer.scanner import ScanMode, scan
from personalscraper.indexer.scanner._walker import SkeletonVisitor, WalkBudget, WalkCheckpoint, walk
from personalscraper.indexer.schema import DiskRow

_MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "personalscraper" / "indexer" / "migrations"
_GUARD_PATCH = "personalscraper.indexer.scanner.guard_disk_mounted"

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root reads every directory")


@contextlib.contextmanager
def _unreadable(path: Path) -> Iterator[None]:
    """Make *path* unlistable for the block, restoring its mode whatever happens."""
    path.chmod(0o000)
    try:
        yield
    finally:
        path.chmod(0o755)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, _MIGRATIONS_DIR)
    return conn


def _disk(conn: sqlite3.Connection, mount: Path) -> DiskRow:
    row = DiskRow(
        id=0,
        uuid="uuid-unreadable",
        label="UnreadableDisk",
        mount_path=str(mount),
        last_seen_at=int(time.time()),
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    return replace(row, id=disk_repo.insert(conn, row))


def _tree(mount: Path) -> tuple[Path, Path]:
    """Two seasons of one show; returns (readable season, season to make unreadable)."""
    kept = mount / "series" / "Show (2020)" / "Season 01"
    hidden = mount / "series" / "Show (2020)" / "Season 02"
    for season in (kept, hidden):
        season.mkdir(parents=True)
        (season / f"{season.name}.E01.mkv").write_bytes(b"x" * 2048)
        (season / f"{season.name}.E02.mkv").write_bytes(b"x" * 2048)
    return kept, hidden


def _walk(conn: sqlite3.Connection, disk: DiskRow, generation: int) -> SkeletonVisitor:
    visitor = SkeletonVisitor(conn, disk, generation, [0], [0])
    walk(
        str(disk.mount_path),
        visitor,
        budget=WalkBudget(None, time.monotonic()),
        shutdown=lambda: False,
        checkpoint=WalkCheckpoint(scan_run_id=0, checkpoint_every=2**62),
    )
    return visitor


def _files(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[int, int | None]]:
    rows = conn.execute(
        "SELECT p.rel_path, mf.filename, mf.miss_strikes, mf.deleted_at "
        "FROM media_file mf JOIN path p ON p.id = mf.path_id"
    ).fetchall()
    return {(r[0], r[1]): (r[2], r[3]) for r in rows}


def test_walk_reports_the_directory_it_could_not_list(tmp_path: Path) -> None:
    """The unreadable directory is on the visitor, by relative path."""
    conn = _conn()
    _, hidden = _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    with _unreadable(hidden):
        visitor = _walk(conn, disk, 1)

    assert visitor.unreadable_dirs == ["series/Show (2020)/Season 02"]


def test_strikes_and_soft_deletes_leave_an_unreadable_directory_alone(tmp_path: Path) -> None:
    """Defect: the files under it took a strike per scan and were soft-deleted past the threshold."""
    conn = _conn()
    kept, hidden = _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    _walk(conn, disk, 1)
    conn.execute("UPDATE media_file SET miss_strikes = 1 WHERE filename LIKE 'Season 02%'")
    (kept / "Season 01.E02.mkv").unlink()

    with _unreadable(hidden):
        _walk(conn, disk, 2)
        mark_missed_files(conn, disk.id, 2)
        apply_soft_deletes(conn, disk.id, 2)

    files = _files(conn)
    assert files[("series/Show (2020)/Season 02", "Season 02.E01.mkv")] == (1, None)
    assert files[("series/Show (2020)/Season 02", "Season 02.E02.mkv")] == (1, None)
    assert files[("series/Show (2020)/Season 01", "Season 01.E01.mkv")] == (0, None)
    assert files[("series/Show (2020)/Season 01", "Season 01.E02.mkv")] == (1, None)


def test_an_unreadable_directory_gets_no_path_row(tmp_path: Path) -> None:
    """The skipped directory gets no path row, so a later dir-mtime short-circuit cannot hide it."""
    conn = _conn()
    _, hidden = _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    with _unreadable(hidden):
        _walk(conn, disk, 1)

    rels = {r[0] for r in conn.execute("SELECT rel_path FROM path")}
    assert "series/Show (2020)/Season 02" not in rels


def test_a_walk_stopped_by_a_file_permission_error_is_a_truncated_run(tmp_path: Path) -> None:
    """Defect: the stop was silent, the run read as complete and struck everything unwalked."""
    from personalscraper.indexer.scanner._modes import full

    conn = _conn()
    _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    calls = {"n": 0}
    original = full.FullVisitor.visit_file

    def deny_second(self, entry, st, parent_rel):
        calls["n"] += 1
        if calls["n"] == 2:
            raise PermissionError(13, "denied", entry.path)
        return original(self, entry, st, parent_rel)

    with (
        patch(_GUARD_PATCH, return_value=None),
        patch.object(full.FullVisitor, "visit_file", deny_second),
    ):
        result = scan([disk], ScanMode.full, generation=1, conn=conn, event_bus=EventBus())

    assert result.budget_exhausted is True
