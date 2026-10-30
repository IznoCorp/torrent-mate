"""Retiring the items whose media folder is gone (``indexer.ghost_items``).

Each guard is proved on its own: a disk whose mount is not confirmed, a folder
still present, a file still live, an open item repair, and the per-disk cap.
"""

from __future__ import annotations

import errno
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ghost_items import GHOST_REASON, configured_disks, retire_ghost_items
from personalscraper.indexer.merkle import DiskMountStatus
from personalscraper.indexer.schema import DiskRow

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "indexer" / "migrations"
_MOUNTED = DiskMountStatus.MOUNTED_AND_VERIFIED


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory store with the full schema and foreign keys on."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _disk(conn: sqlite3.Connection, root: Path) -> DiskRow:
    """Insert the disk scanned at *root*; return its row."""
    disk_id = conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, is_mounted, unreachable_strikes) VALUES ('u', 'medias1', ?, 1, 0)",
        (str(root),),
    ).lastrowid
    return DiskRow(
        id=int(disk_id),  # type: ignore[arg-type]
        uuid="u",
        label="medias1",
        mount_path=str(root),
        last_seen_at=None,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )


def _item(conn: sqlite3.Connection, folder: Path, *, title: str = "Gone", kind: str = "movie") -> int:
    """Insert an item on *folder*; return its id."""
    item_id = int(
        conn.execute(  # type: ignore[arg-type]
            "INSERT INTO media_item (kind, title, title_sort, year, category_id, date_created, date_modified) "
            "VALUES (?, ?, ?, 2020, 'movies', 1, 1)",
            (kind, title, title),
        ).lastrowid
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)", (item_id, str(folder))
    )
    return item_id


def _file(conn: sqlite3.Connection, item_id: int, disk: DiskRow, *, deleted_at: int | None) -> None:
    """Give *item_id* a release holding one file, tombstoned or live."""
    release_id = conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (item_id,)).lastrowid
    path_id = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES (?, ?)", (disk.id, f"movies/{item_id}")
    ).lastrowid
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at, deleted_at) VALUES (?, ?, 'f.mkv', 1, 1, 'h', 1, 1, ?)",
        (release_id, path_id, deleted_at),
    )


def _items(conn: sqlite3.Connection) -> list[int]:
    """Return the ids of the items left."""
    return [r[0] for r in conn.execute("SELECT id FROM media_item ORDER BY id")]


@pytest.fixture()
def library(tmp_path: Path) -> tuple[sqlite3.Connection, DiskRow, Path]:
    """A store and a disk with nine present folders, so one ghost stays under the cap.

    Returns:
        ``(conn, disk, root)``.
    """
    conn = _make_conn()
    root = tmp_path / "medias"
    disk = _disk(conn, root)
    for n in range(9):
        folder = root / "movies" / f"Present {n} (2020)"
        folder.mkdir(parents=True)
        _item(conn, folder, title=f"Present {n}")
    return conn, disk, root


def test_a_ghost_with_its_files_tombstoned_is_retired_with_a_tombstone(
    library: tuple[sqlite3.Connection, DiskRow, Path],
) -> None:
    """The item, its release and its dead file go; the tombstone keeps a snapshot.

    Design: docs/production/indexer.md#ghost-items
    Contract: an item whose folder is gone and whose files are all tombstoned is
        hard-deleted with its children, after a ``deleted_item`` tombstone
        (``reason='dispatch_path_gone'``) holding a snapshot of the row.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")
    _file(conn, ghost, disk, deleted_at=100)

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, now_s=5000)

    assert report.retired == 1 and ghost not in _items(conn)
    assert conn.execute("SELECT COUNT(*) FROM media_release WHERE item_id = ?", (ghost,)).fetchone() == (0,)
    original_id, reason, payload = conn.execute(
        "SELECT original_id, reason, payload_json FROM deleted_item WHERE kind = 'item'"
    ).fetchone()
    assert (original_id, reason) == (ghost, GHOST_REASON)
    assert json.loads(payload)["dispatch_path"].endswith("Gone (2020)")
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_a_dry_run_reports_the_ghost_and_writes_nothing(library: tuple[sqlite3.Connection, DiskRow, Path]) -> None:
    """The dry run names the ghost with its reason; the store is unchanged.

    Design: docs/production/indexer.md#ghost-items
    Contract: a dry run lists the ghosts and writes nothing.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")
    before = list(conn.iterdump())

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=True)

    assert [(g.item_id, g.reason) for g in report.ghosts] == [(ghost, GHOST_REASON)]
    assert report.retired == 0 and list(conn.iterdump()) == before


@pytest.mark.parametrize("status", [DiskMountStatus.UNMOUNTED, DiskMountStatus.MOUNTED_WRONG_DISK])
def test_a_disk_whose_mount_is_not_confirmed_retires_nothing(
    library: tuple[sqlite3.Connection, DiskRow, Path], status: DiskMountStatus
) -> None:
    """An unmounted disk makes every folder look gone: the pass freezes.

    Design: docs/production/indexer.md#ghost-items
    Contract: a disk whose mount is not confirmed is frozen: nothing is retired.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")

    report = retire_ghost_items(conn, disk, status, dry_run=False, max_share=None)

    assert report.frozen and ghost in _items(conn)


def test_an_item_whose_folder_is_present_is_kept(library: tuple[sqlite3.Connection, DiskRow, Path]) -> None:
    """A present folder is never a ghost, files or not.

    Design: docs/production/indexer.md#ghost-items
    Contract: an item whose folder exists is never a ghost.
    """
    conn, disk, _root = library

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert report.ghosts == [] and len(_items(conn)) == 9


@pytest.mark.parametrize("kind", ["movie", "show"])
def test_an_item_with_a_live_file_is_kept(library: tuple[sqlite3.Connection, DiskRow, Path], kind: str) -> None:
    """A live file means the strikes have not finished: the item waits for them.

    Design: docs/production/indexer.md#ghost-items
    Contract: an item with a live file is kept until the strikes tombstone it.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)", kind=kind)
    if kind == "movie":
        _file(conn, ghost, disk, deleted_at=None)
    else:
        season = conn.execute("INSERT INTO season (item_id, number) VALUES (?, 1)", (ghost,)).lastrowid
        episode = conn.execute("INSERT INTO episode (season_id, number) VALUES (?, 1)", (season,)).lastrowid
        release = conn.execute("INSERT INTO media_release (episode_id) VALUES (?)", (episode,)).lastrowid
        path_id = conn.execute("INSERT INTO path (disk_id, rel_path) VALUES (?, 's')", (disk.id,)).lastrowid
        conn.execute(
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
            " last_verified_at) VALUES (?, ?, 'e.mkv', 1, 1, 'h', 1, 1)",
            (release, path_id),
        )

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert [(k.item_id, k.reason) for k in report.kept] == [(ghost, "live_files")]
    assert ghost in _items(conn)


@pytest.mark.parametrize(("status", "kept"), [("pending", True), ("running", True), ("done", False)])
def test_an_item_an_open_repair_names_is_kept(
    library: tuple[sqlite3.Connection, DiskRow, Path], status: str, kept: bool
) -> None:
    """``repair_queue`` holds item ids with no foreign key: open work keeps the item.

    Design: docs/production/indexer.md#ghost-items
    Contract: a ``pending`` / ``running`` repair naming the item keeps it.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at, status) VALUES ('item', ?, 'r', 1, ?)",
        (ghost, status),
    )

    retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert (ghost in _items(conn)) is kept


def test_more_than_the_cap_retires_none_unless_the_cap_is_lifted(
    library: tuple[sqlite3.Connection, DiskRow, Path],
) -> None:
    """Two ghosts out of eleven items is over a tenth: none go, until the cap is lifted.

    Design: docs/production/indexer.md#ghost-items
    Contract: over ``MAX_RETIRE_SHARE`` of a disk's items nothing is retired, unless
        the cap is lifted.
    """
    conn, disk, root = library
    ghosts = [_item(conn, root / "movies" / f"Gone {n} (2020)", title=f"Gone {n}") for n in range(2)]

    capped = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False)

    assert capped.capped and capped.retired == 0
    assert all(g in _items(conn) for g in ghosts)

    lifted = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert lifted.retired == 2 and not any(g in _items(conn) for g in ghosts)


def test_an_item_on_another_disk_is_not_this_disks_ghost(library: tuple[sqlite3.Connection, DiskRow, Path]) -> None:
    """Only the folders under the disk's root are judged by its pass.

    Design: docs/production/indexer.md#ghost-items
    Contract: a disk's pass judges only the folders under its root.
    """
    conn, disk, root = library
    elsewhere = _item(conn, root.parent / "medias-other" / "movies" / "Gone (2020)")

    retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert elsewhere in _items(conn)


def test_only_configured_disks_are_kept(tmp_path: Path) -> None:
    """A disk row whose root left the configuration is not a disk to judge.

    Design: docs/production/indexer.md#ghost-items
    Contract: only the disks of the configuration are judged.
    """
    conn = _make_conn()
    kept = _disk(conn, tmp_path / "medias")
    stale = DiskRow(
        id=99,
        uuid="x",
        label="old",
        mount_path="/Volumes/Old/medias",
        last_seen_at=None,
        merkle_root=None,
        is_mounted=1,
        unreachable_strikes=0,
    )
    config: Any = SimpleNamespace(disks=[SimpleNamespace(path=tmp_path / "medias")])

    assert configured_disks([kept, stale], config) == [kept]


def test_the_pass_refuses_a_connection_with_an_open_transaction(
    library: tuple[sqlite3.Connection, DiskRow, Path],
) -> None:
    """Committing first would commit the caller's own pending writes; the pass raises instead.

    Design: docs/production/indexer.md#ghost-items
    Contract: ``retire_ghost_items`` never commits nor rolls back a transaction
        it did not open.
    """
    conn, disk, root = library
    _item(conn, root / "movies" / "Gone (2020)")
    conn.execute("BEGIN")
    mine = _item(conn, root / "movies" / "Present 0 (2020)", title="Mine")

    with pytest.raises(RuntimeError, match="open transaction"):
        retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    conn.rollback()
    assert mine not in _items(conn)


def test_a_disk_with_no_sentinel_retires_nothing(library: tuple[sqlite3.Connection, DiskRow, Path]) -> None:
    """A mount with no readable sentinel is not a confirmed disk: a hard delete waits for one.

    Design: docs/production/indexer.md#ghost-items
    Contract: only ``MOUNTED_AND_VERIFIED`` lets a disk's ghosts retire; any
        other status, ``NO_SENTINEL`` included, freezes the disk.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")

    report = retire_ghost_items(conn, disk, DiskMountStatus.NO_SENTINEL, dry_run=False, max_share=None)

    assert report.frozen and report.retired == 0 and ghost in _items(conn)


def test_a_folder_that_cannot_be_stat_ed_freezes_the_disk(
    library: tuple[sqlite3.Connection, DiskRow, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only ``FileNotFoundError`` means gone: an I/O or permission error freezes the disk.

    Design: docs/production/indexer.md#ghost-items
    Contract: a folder whose ``stat`` fails with anything but
        ``FileNotFoundError`` freezes the disk's pass; nothing is retired.
    """
    conn, disk, root = library
    gone = _item(conn, root / "movies" / "Gone (2020)")
    unreadable = root / "movies" / "Unreadable (2020)"
    blocked = _item(conn, unreadable, title="Unreadable")
    real_stat = os.stat

    def _stat(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        if str(path) == str(unreadable):
            raise OSError(errno.EIO, "Input/output error", str(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(os, "stat", _stat)

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert report.frozen and report.retired == 0
    assert {gone, blocked} <= set(_items(conn))


def test_an_item_with_a_live_unlinked_file_under_its_folder_is_kept(
    library: tuple[sqlite3.Connection, DiskRow, Path],
) -> None:
    """A live file with no release, under the item's folder, still waits for its strikes.

    Design: docs/production/indexer.md#ghost-items
    Contract: a live ``media_file`` whose path lies under the item's
        ``dispatch_path`` keeps the item, linked to a release or not.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")
    path_id = conn.execute("INSERT INTO path (disk_id, rel_path) VALUES (?, 'movies/Gone (2020)/extras')", (disk.id,))
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at) VALUES (NULL, ?, 'poster.jpg', 1, 1, 'h', 1, 1)",
        (path_id.lastrowid,),
    )

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert [(k.item_id, k.reason) for k in report.kept] == [(ghost, "live_files")]
    assert ghost in _items(conn)


class _LateWriter:
    """A connection whose ``BEGIN IMMEDIATE`` first runs a write, as another process would."""

    def __init__(self, conn: sqlite3.Connection, write: str, params: tuple[Any, ...]) -> None:
        object.__setattr__(self, "_conn", conn)
        object.__setattr__(self, "_write", (write, params))

    def execute(self, sql: str, params: Any = ()) -> sqlite3.Cursor:
        if sql == "BEGIN IMMEDIATE":
            self._conn.execute(*self._write)
        return self._conn.execute(sql, params)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._conn, name, value)


def test_a_file_appearing_between_the_check_and_the_write_keeps_the_item(
    library: tuple[sqlite3.Connection, DiskRow, Path],
) -> None:
    """The guards are asked again inside the write transaction, before each delete.

    Design: docs/production/indexer.md#ghost-items
    Contract: an item that stops being a ghost between the pass's reading and
        its write transaction is kept.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")
    other = _item(conn, root / "movies" / "Also Gone (2020)", title="Also Gone")
    release = conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (ghost,)).lastrowid
    path_id = conn.execute("INSERT INTO path (disk_id, rel_path) VALUES (?, 'movies/x')", (disk.id,)).lastrowid
    late = _LateWriter(
        conn,
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at) VALUES (?, ?, 'late.mkv', 1, 1, 'h', 1, 1)",
        (release, path_id),
    )

    report = retire_ghost_items(late, disk, _MOUNTED, dry_run=False, max_share=None)  # type: ignore[arg-type]

    assert ghost in _items(conn) and other not in _items(conn)
    assert report.retired == 1
    assert [(k.item_id, k.reason) for k in report.kept] == [(ghost, "live_files")]


def test_any_error_while_retiring_rolls_back_and_re_raises(
    library: tuple[sqlite3.Connection, DiskRow, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not only ``sqlite3.Error``: whatever fails mid-pass, the transaction is not left open.

    Design: docs/production/indexer.md#ghost-items
    Contract: any exception during the deletes rolls the pass back and is
        re-raised; no ``BEGIN IMMEDIATE`` is left open.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")

    def _broken(*_args: Any) -> None:
        raise TypeError("row is None")

    monkeypatch.setattr("personalscraper.indexer.ghost_items._retire", _broken)

    with pytest.raises(TypeError):
        retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert not conn.in_transaction
    assert ghost in _items(conn)


@pytest.mark.parametrize("scope", ["release", "file"])
def test_an_open_repair_on_a_release_or_a_file_of_the_item_keeps_it(
    library: tuple[sqlite3.Connection, DiskRow, Path], scope: str
) -> None:
    """A repair on a row the cascade would delete is open work on the item too.

    Design: docs/production/indexer.md#ghost-items
    Contract: a ``pending`` / ``running`` repair naming one of the item's
        releases or files keeps the item, like an item repair.
    """
    conn, disk, root = library
    ghost = _item(conn, root / "movies" / "Gone (2020)")
    _file(conn, ghost, disk, deleted_at=100)
    release_id, file_id = conn.execute(
        "SELECT mr.id, mf.id FROM media_release mr JOIN media_file mf ON mf.release_id = mr.id WHERE mr.item_id = ?",
        (ghost,),
    ).fetchone()
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at) VALUES (?, ?, 'r', 1)",
        (scope, release_id if scope == "release" else file_id),
    )

    report = retire_ghost_items(conn, disk, _MOUNTED, dry_run=False, max_share=None)

    assert [(k.item_id, k.reason) for k in report.kept] == [(ghost, "pending_repair")]
    assert ghost in _items(conn)
