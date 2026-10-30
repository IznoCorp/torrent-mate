"""Retiring the items whose media folder is gone (``indexer.ghost_items``).

Each guard is proved on its own: a disk whose mount is not confirmed, a folder
still present, a file still live, an open item repair, and the per-disk cap.
"""

from __future__ import annotations

import json
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
