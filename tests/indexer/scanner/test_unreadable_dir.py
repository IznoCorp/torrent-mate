"""A directory the walk cannot list keeps its files in the index.

The walk used to log ``indexer.scan.dir_permission_denied`` and go on as if the
directory were empty; the miss strikes and the soft-deletes that run after it then
read every file below as « not seen », hence gone. These tests pin the contract:

- the walk reports the directory (relative path) on the visitor;
- a full scan's strikes and soft-deletes leave the files under it alone, strikes
  neither reset nor raised, while a file really gone elsewhere is still struck;
- a per-file ``PermissionError`` shelters that file like an unreadable directory and
  the walk, the run and the other disks go on.
"""

from __future__ import annotations

import contextlib
import os
import sqlite3
import time
import unicodedata
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

#: The strike count at which ``apply_soft_deletes`` tombstones a file.
_THRESHOLD = 3

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


def _disk(
    conn: sqlite3.Connection, mount: Path, *, label: str = "UnreadableDisk", uuid: str = "uuid-unreadable"
) -> DiskRow:
    row = DiskRow(
        id=0,
        uuid=uuid,
        label=label,
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


def _scan(conn: sqlite3.Connection, disks: list[DiskRow], generation: int):
    """Run one full-mode ``scan()`` over *disks*, the way the index command does."""
    return scan(disks, ScanMode.full, generation=generation, conn=conn, event_bus=EventBus())


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
    """Defect: the files under it took a strike per scan and were soft-deleted past the threshold.

    Drives ``scan()`` (full mode) like the index command does, strikes seeded one below the
    threshold so any strike that lands shows as a soft-delete. A neighbour sharing the
    unreadable directory's name as a prefix is truly gone and must still be struck.
    """
    conn = _conn()
    kept, hidden = _tree(tmp_path)
    extras = hidden.parent / "Season 02 Extras"
    extras.mkdir()
    (extras / "Extras.E01.mkv").write_bytes(b"x" * 2048)
    disk = _disk(conn, tmp_path)
    with patch(_GUARD_PATCH, return_value=None):
        _scan(conn, [disk], 1)
    conn.execute("UPDATE media_file SET miss_strikes = ?", (_THRESHOLD - 1,))
    (kept / "Season 01.E02.mkv").unlink()
    (extras / "Extras.E01.mkv").unlink()

    with _unreadable(hidden), patch(_GUARD_PATCH, return_value=None):
        result = _scan(conn, [disk], 2)
    assert result.budget_exhausted is False
    mark_missed_files(conn, disk.id, 2)
    apply_soft_deletes(conn, disk.id, _THRESHOLD)

    files = _files(conn)
    show = "series/Show (2020)"
    assert files[(f"{show}/Season 02", "Season 02.E01.mkv")] == (_THRESHOLD - 1, None)
    assert files[(f"{show}/Season 02", "Season 02.E02.mkv")] == (_THRESHOLD - 1, None)
    assert files[(f"{show}/Season 01", "Season 01.E01.mkv")][1] is None
    assert files[(f"{show}/Season 01", "Season 01.E02.mkv")][1] is not None
    assert files[(f"{show}/Season 02 Extras", "Extras.E01.mkv")][1] is not None


def test_a_row_stored_in_the_other_normalisation_is_sheltered_too(tmp_path: Path) -> None:
    """Defect: the shelter matched the disk's spelling only; an NFD-stored row was struck."""
    conn = _conn()
    name = unicodedata.normalize("NFC", "Bjo" + chr(0x308) + "rk Season 02")
    hidden = tmp_path / "series" / "Show (2020)" / name
    hidden.mkdir(parents=True)
    (hidden / "Track.E01.mkv").write_bytes(b"x" * 2048)
    disk = _disk(conn, tmp_path)
    _walk(conn, disk, 1)
    nfd_rel = unicodedata.normalize("NFD", f"series/Show (2020)/{name}")
    conn.execute("UPDATE path SET rel_path = ? WHERE rel_path = ?", (nfd_rel, f"series/Show (2020)/{name}"))

    with _unreadable(hidden):
        _walk(conn, disk, 2)
        mark_missed_files(conn, disk.id, 2)
        apply_soft_deletes(conn, disk.id, 1)

    assert _files(conn)[(nfd_rel, "Track.E01.mkv")] == (0, None)


def test_an_unreadable_mount_shelters_every_file_of_the_disk(tmp_path: Path) -> None:
    """Defect: the root was never recognised, so only the root-level files were sheltered."""
    conn = _conn()
    _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    _walk(conn, disk, 1)

    with _unreadable(tmp_path):
        visitor = _walk(conn, disk, 2)
        mark_missed_files(conn, disk.id, 2)
        apply_soft_deletes(conn, disk.id, 1)

    assert visitor.unreadable_dirs == [""]
    assert all(strikes_deleted == (0, None) for strikes_deleted in _files(conn).values())


def test_a_directory_readable_again_is_seen_and_gets_its_path_row(tmp_path: Path) -> None:
    """Once the mode is restored the next walk sees its files and writes its path row."""
    conn = _conn()
    _, hidden = _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    _walk(conn, disk, 1)
    with _unreadable(hidden):
        _walk(conn, disk, 2)

    visitor = _walk(conn, disk, 3)

    assert visitor.unreadable_dirs == []
    generations = {
        r[0]
        for r in conn.execute(
            "SELECT mf.scan_generation FROM media_file mf JOIN path p ON p.id = mf.path_id WHERE p.rel_path LIKE ?",
            ("%Season 02",),
        )
    }
    assert generations == {3}
    rels = {r[0] for r in conn.execute("SELECT rel_path FROM path")}
    assert "series/Show (2020)/Season 02" in rels


def test_an_unreadable_directory_gets_no_path_row(tmp_path: Path) -> None:
    """The skipped directory gets no path row, so a later dir-mtime short-circuit cannot hide it."""
    conn = _conn()
    _, hidden = _tree(tmp_path)
    disk = _disk(conn, tmp_path)
    with _unreadable(hidden):
        _walk(conn, disk, 1)

    rels = {r[0] for r in conn.execute("SELECT rel_path FROM path")}
    assert "series/Show (2020)/Season 02" not in rels


def test_an_unreadable_file_is_sheltered_and_the_other_disks_are_still_scanned(tmp_path: Path) -> None:
    """Defect: a per-file PermissionError flagged the run as budget-exhausted and stopped the disk loop."""
    from personalscraper.indexer.scanner._modes import full

    conn = _conn()
    first, second = tmp_path / "one", tmp_path / "two"
    for mount, names in ((first, ("a.mkv", "b.mkv", "gone.mkv")), (second, ("c.mkv",))):
        mount.mkdir()
        for name in names:
            (mount / name).write_bytes(b"x" * 2048)
    disk_one = _disk(conn, first, label="DiskOne", uuid="uuid-one")
    disk_two = _disk(conn, second, label="DiskTwo", uuid="uuid-two")
    with patch(_GUARD_PATCH, return_value=None):
        _scan(conn, [disk_one, disk_two], 1)
    conn.execute("UPDATE media_file SET miss_strikes = ?", (_THRESHOLD - 1,))
    (first / "gone.mkv").unlink()
    original = full.FullVisitor.visit_file

    def deny_a(self, entry, st, parent_rel):
        if entry.name == "a.mkv":
            raise PermissionError(13, "denied", entry.path)
        return original(self, entry, st, parent_rel)

    with (
        patch(_GUARD_PATCH, return_value=None),
        patch.object(full.FullVisitor, "visit_file", deny_a),
    ):
        result = _scan(conn, [disk_one, disk_two], 2)
    assert result.budget_exhausted is False
    for disk in (disk_one, disk_two):
        mark_missed_files(conn, disk.id, 2)
        apply_soft_deletes(conn, disk.id, _THRESHOLD)

    files = _files(conn)
    assert files[("", "a.mkv")] == (_THRESHOLD - 1, None)  # sheltered: strike and tombstone untouched
    assert files[("", "b.mkv")] == (0, None)  # seen: the sighting reset its strikes
    assert files[("", "gone.mkv")][1] is not None  # truly gone: struck past the threshold
    assert files[("", "c.mkv")] == (0, None)  # the second disk was scanned: seen, strikes reset
