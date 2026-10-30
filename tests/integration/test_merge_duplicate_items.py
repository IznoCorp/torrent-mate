"""End-to-end tests for the ``library-merge-duplicate-items`` CLI command.

Covers:
- dry-run: lists each group sharing a ``dispatch_path`` and writes nothing.
- run: folds the younger item into the oldest, its release and files re-pointed.
- idempotence: a second run finds nothing left to merge.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.commands._e2e_helpers import json_from_result, make_synthetic_db, run_cli

_DISPATCH = "/Volumes/Disk1/movies/The Gentlemen (2020)"


def _insert_item(conn: sqlite3.Connection, title: str, created: int) -> int:
    """Insert a movie on the shared folder with one release holding one file.

    Args:
        conn: Open SQLite connection.
        title: Title stored verbatim.
        created: ``date_created`` epoch, which decides the keeper.

    Returns:
        The new ``media_item.id``.
    """
    item_id = int(
        conn.execute(  # type: ignore[arg-type]
            "INSERT INTO media_item (kind, title, title_sort, year, category_id, date_created, date_modified) "
            "VALUES ('movie', ?, ?, 2020, 'movies', ?, ?)",
            (title, title, created, created),
        ).lastrowid
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)", (item_id, _DISPATCH)
    )
    release_id = conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (item_id,)).lastrowid
    conn.execute(
        "INSERT INTO disk (uuid, label, mount_path, is_mounted, unreachable_strikes) "
        "VALUES ('u', 'd', '/Volumes/Disk1', 1, 0) ON CONFLICT DO NOTHING"
    )
    path_id = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES ((SELECT id FROM disk), 'movies/The Gentlemen (2020)') "
        "ON CONFLICT(disk_id, rel_path) DO UPDATE SET rel_path = excluded.rel_path RETURNING id"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash, scan_generation,"
        " last_verified_at) VALUES (?, ?, ?, 1, 1, 'h', 1, 1)",
        (release_id, path_id, f"{title}.mkv"),
    )
    return item_id


@pytest.fixture()
def split_db(tmp_path: Path) -> tuple[Path, int, int]:
    """A store where a re-dispatch split one folder into two items.

    Returns:
        ``(db_path, keeper_id, duplicate_id)``.
    """
    db_path = make_synthetic_db(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    keeper = _insert_item(conn, "The Gentlemen (2020)", created=100)
    duplicate = _insert_item(conn, "The Gentlemen", created=200)
    conn.commit()
    conn.close()
    return db_path, keeper, duplicate


def _dump(db_path: Path) -> list[str]:
    """Return the store's full SQL dump."""
    conn = sqlite3.connect(str(db_path))
    try:
        return list(conn.iterdump())
    finally:
        conn.close()


def test_dry_run_lists_the_pair_and_writes_nothing(split_db: tuple[Path, int, int]) -> None:
    """``--dry-run`` names the keeper and the merged id; the store is unchanged."""
    db_path, keeper, duplicate = split_db
    before = _dump(db_path)

    result = run_cli(["--format", "json", "library-merge-duplicate-items", "--db", str(db_path), "--dry-run"])

    assert result.exit_code == 0, result.output
    payload = json_from_result(result, source_attr="stdout")
    assert payload["dry_run"] is True
    assert [(g["dispatch_path"], g["keeper_id"], g["merged_ids"]) for g in payload["groups"]] == [
        (_DISPATCH, keeper, [duplicate])
    ]
    assert payload["would_merge"] == 1
    assert _dump(db_path) == before


def test_run_merges_into_the_oldest_and_a_second_run_finds_nothing(split_db: tuple[Path, int, int]) -> None:
    """The run leaves one item holding both files; the next run is a no-op."""
    db_path, keeper, duplicate = split_db

    result = run_cli(["--format", "json", "library-merge-duplicate-items", "--db", str(db_path)])

    assert result.exit_code == 0, result.output
    assert json_from_result(result, source_attr="stdout")["merged"] == 1
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT id, title FROM media_item").fetchall() == [(keeper, "The Gentlemen")]
        assert conn.execute(
            "SELECT COUNT(*) FROM media_file mf JOIN media_release mr ON mr.id = mf.release_id WHERE mr.item_id = ?",
            (keeper,),
        ).fetchone() == (2,)
        assert conn.execute(
            "SELECT reason FROM deleted_item WHERE kind = 'item' AND original_id = ?", (duplicate,)
        ).fetchone() == ("merged_duplicate",)
    finally:
        conn.close()

    again = run_cli(["--format", "json", "library-merge-duplicate-items", "--db", str(db_path)])

    assert again.exit_code == 0, again.output
    payload = json_from_result(again, source_attr="stdout")
    assert payload["groups"] == [] and payload["merged"] == 0
