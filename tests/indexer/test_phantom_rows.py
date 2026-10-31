"""0-file phantom rows: chosen from the provider-id duplicate groups, removed from the index only.

A phantom is a row holding no live file beside a row of the same provider id that
holds some. Removing it deletes the index row (and its empty seasons by cascade),
journals it, and never touches a file nor a row that holds one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.duplicates import DuplicateGroup, DuplicateRow, find_provider_id_duplicates
from personalscraper.indexer.phantom_rows import phantom_rows, remove_phantom_rows

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Create a migrated indexer database file with one disk.

    Args:
        tmp_path: Per-test directory.

    Returns:
        The database path (the journal writes through its own connection, so a file is needed).
    """
    path = tmp_path / "library.db"
    c = sqlite3.connect(str(path), isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, _MIGRATIONS_DIR)
    c.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1', 'Disk1', '/d1', 1)")
    c.close()
    return path


@pytest.fixture()
def conn(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Open the migrated database with foreign keys on.

    Args:
        db_path: The migrated database.

    Yields:
        An open connection in autocommit mode, closed after the test.
    """
    c = sqlite3.connect(str(db_path), isolation_level=None)
    c.execute("PRAGMA foreign_keys=ON")
    yield c
    c.close()


def _show(conn: sqlite3.Connection, title: str, tvdb: str) -> int:
    """Insert one show row carrying *tvdb* and return its id.

    Args:
        conn: Open connection.
        title: Row title.
        tvdb: TVDB series id.

    Returns:
        The new ``media_item.id``.
    """
    ids = json.dumps({"tvdb": {"series_id": tvdb, "episode_id": None}})
    cur = conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, category_id, date_created, date_modified,"
        " external_ids_json) VALUES ('show', ?, ?, 'tv_shows', 0, 0, ?)",
        (title, title, ids),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _movie(conn: sqlite3.Connection, title: str, tmdb: str, *, files: bool) -> int:
    """Insert one movie row carrying *tmdb*, with one live file through its own release when *files*.

    Args:
        conn: Open connection.
        title: Row title.
        tmdb: TMDB movie id.
        files: Whether the movie's release holds a live file.

    Returns:
        The new ``media_item.id``.
    """
    ids = json.dumps({"tmdb": {"series_id": tmdb}})
    item_id = conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, category_id, date_created, date_modified,"
        " external_ids_json) VALUES ('movie', ?, ?, 'movies', 0, 0, ?)",
        (title, title, ids),
    ).lastrowid
    if files:
        folder = f"movies/{title}"
        conn.execute("INSERT OR IGNORE INTO path(disk_id, rel_path) VALUES (1, ?)", (folder,))
        path_id = conn.execute("SELECT id FROM path WHERE rel_path = ?", (folder,)).fetchone()[0]
        release = conn.execute("INSERT INTO media_release(item_id) VALUES (?)", (item_id,)).lastrowid
        conn.execute(
            "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
            " scan_generation, last_verified_at, deleted_at) VALUES (?, ?, 'movie.mkv', 1, 1, '0', 1, 1, NULL)",
            (release, path_id),
        )
    assert item_id is not None
    return item_id


def _episodes(conn: sqlite3.Connection, item_id: int, folder: str, count: int, *, deleted: bool = False) -> None:
    """Give *item_id* one season of *count* episodes, each with one file in *folder*.

    Args:
        conn: Open connection.
        item_id: Owning show row.
        folder: The season folder (``series/X (2022)/Saison 01``).
        count: Number of episodes (and files).
        deleted: Whether the files are tombstoned.
    """
    conn.execute("INSERT OR IGNORE INTO path(disk_id, rel_path) VALUES (1, ?)", (folder,))
    path_id = conn.execute("SELECT id FROM path WHERE rel_path = ?", (folder,)).fetchone()[0]
    season = conn.execute("INSERT INTO season(item_id, number) VALUES (?, 1)", (item_id,)).lastrowid
    for number in range(1, count + 1):
        episode = conn.execute("INSERT INTO episode(season_id, number) VALUES (?, ?)", (season, number)).lastrowid
        release = conn.execute("INSERT INTO media_release(episode_id) VALUES (?)", (episode,)).lastrowid
        conn.execute(
            "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
            " scan_generation, last_verified_at, deleted_at) VALUES (?, ?, ?, 1, 1, '0', 1, 1, ?)",
            (release, path_id, f"e{number:02d}.mkv", 5 if deleted else None),
        )


def _empty_season(conn: sqlite3.Connection, item_id: int) -> None:
    """Give *item_id* a season with one episode and no release, as the 09-02 phantoms have.

    Args:
        conn: Open connection.
        item_id: Owning show row.
    """
    season = conn.execute("INSERT INTO season(item_id, number) VALUES (?, 1)", (item_id,)).lastrowid
    conn.execute("INSERT INTO episode(season_id, number) VALUES (?, 1)", (season,))


def _row(item_id: int, live_files: int) -> DuplicateRow:
    """Build a group row with *live_files* files.

    Args:
        item_id: Row id.
        live_files: Its live-file count.

    Returns:
        The :class:`DuplicateRow`.
    """
    folders = (f"Disk1:series/{item_id}",) if live_files else ()
    return DuplicateRow(item_id=item_id, title=str(item_id), live_files=live_files, folders=folders)


def _group(*rows: DuplicateRow) -> DuplicateGroup:
    """Build a show group over *rows*.

    Args:
        rows: The group's rows.

    Returns:
        The :class:`DuplicateGroup`.
    """
    return DuplicateGroup(provider="tvdb", provider_id="1", kind="show", rows=rows)


def _journal(conn: sqlite3.Connection) -> list[tuple[str, str, str, str]]:
    """Return the journal's ``(op, path, actor, run_uid)`` rows in insertion order.

    Args:
        conn: Open connection.

    Returns:
        The rows.
    """
    return conn.execute("SELECT op, path, actor, run_uid FROM destructive_op ORDER BY id").fetchall()


def test_phantom_rows_picks_the_zero_file_rows_beside_a_row_with_files() -> None:
    """In a group holding a row with files, every 0-file row is a phantom; the row with files never is."""
    groups = [_group(_row(1, 70), _row(2, 0)), _group(_row(3, 5), _row(4, 0), _row(5, 2), _row(6, 0))]

    assert phantom_rows(groups) == [2, 4, 6]


def test_phantom_rows_never_empties_an_id() -> None:
    """A group whose every row holds no file gives no phantom (the id would be left with no row)."""
    assert phantom_rows([_group(_row(1, 0), _row(2, 0))]) == []


def test_phantom_rows_leaves_a_group_of_rows_that_all_hold_files() -> None:
    """Two rows that both hold files, or one row in two folders, give no phantom."""
    assert phantom_rows([_group(_row(1, 807), _row(2, 729)), _group(_row(3, 20))]) == []


def test_remove_deletes_the_phantom_and_keeps_the_row_with_files(conn: sqlite3.Connection, db_path: Path) -> None:
    """The House of the Dragon (2022) row (70 files) + its 0-file twin: one row stays, files unchanged."""
    real = _show(conn, "House of the Dragon (2022)", "371572")
    phantom = _show(conn, "House of the Dragon", "371572")
    _episodes(conn, real, "series/House of the Dragon (2022)/Saison 01", 70)
    _empty_season(conn, phantom)
    files_before = conn.execute("SELECT id, release_id, path_id, deleted_at FROM media_file ORDER BY id").fetchall()

    removed = remove_phantom_rows(
        conn, phantom_rows(find_provider_id_duplicates(conn)), db_path=db_path, run_uid="r1", dry_run=False
    )

    assert removed == 1
    assert [r[0] for r in conn.execute("SELECT id FROM media_item")] == [real]
    assert conn.execute("SELECT id, release_id, path_id, deleted_at FROM media_file ORDER BY id").fetchall() == (
        files_before
    )
    assert conn.execute("SELECT COUNT(*) FROM season WHERE item_id = ?", (phantom,)).fetchone()[0] == 0
    assert _journal(conn) == [("delete", f"index:media_item/{phantom}", "maintenance", "r1")]


def test_remove_leaves_an_item_tombstone_with_the_row_snapshot(conn: sqlite3.Connection, db_path: Path) -> None:
    """Each removed row leaves a ``deleted_item`` tombstone carrying its columns, so it can be read back."""
    real = _show(conn, "Slow Horses (2022)", "372264")
    phantom = _show(conn, "Slow Horses", "372264")
    _episodes(conn, real, "series/Slow Horses (2022)/Saison 01", 1)

    remove_phantom_rows(conn, [phantom], db_path=db_path, run_uid="r6", dry_run=False)

    ((kind, original_id, reason, payload),) = conn.execute(
        "SELECT kind, original_id, reason, payload_json FROM deleted_item"
    ).fetchall()
    snapshot = json.loads(payload)
    assert (kind, original_id, reason) == ("item", phantom, "phantom_row_removed")
    assert snapshot["kind"] == "item"
    assert snapshot["snapshot"]["title"] == "Slow Horses"
    assert json.loads(snapshot["snapshot"]["external_ids_json"])["tvdb"]["series_id"] == "372264"


def test_remove_journals_every_deleted_row(conn: sqlite3.Connection, db_path: Path) -> None:
    """Each deleted row has its own journal row, and only the deleted rows have one."""
    real = _show(conn, "Rick et Morty", "275274")
    phantom_a = _show(conn, "Rick and Morty", "275274")
    phantom_b = _show(conn, "Rick and Morty (2013)", "275274")
    _episodes(conn, real, "series/Rick et Morty/Saison 01", 3)

    removed = remove_phantom_rows(conn, [phantom_a, phantom_b], db_path=db_path, run_uid="r2", dry_run=False)

    assert removed == 2
    assert _journal(conn) == [
        ("delete", f"index:media_item/{phantom_a}", "maintenance", "r2"),
        ("delete", f"index:media_item/{phantom_b}", "maintenance", "r2"),
    ]


def test_dry_run_deletes_and_journals_nothing(conn: sqlite3.Connection, db_path: Path) -> None:
    """A dry run counts the rows it would remove and writes nothing."""
    real = _show(conn, "Silo (2023)", "403245")
    phantom = _show(conn, "Silo", "403245")
    _episodes(conn, real, "series/Silo (2023)/Saison 01", 2)

    removed = remove_phantom_rows(conn, [phantom], db_path=db_path, run_uid="r3", dry_run=True)

    assert removed == 1
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 2
    assert _journal(conn) == []


def test_remove_never_deletes_a_row_holding_live_files(conn: sqlite3.Connection, db_path: Path) -> None:
    """An id passed by mistake whose row holds live files is kept and not journaled."""
    friends = _show(conn, "Friends", "79168")
    uncut = _show(conn, "Friends [UNCUT]", "79168")
    _episodes(conn, friends, "series/Friends (1994)/Saison 01", 2)
    _episodes(conn, uncut, "series/Friends [UNCUT] (1994)/Saison 01", 2)

    removed = remove_phantom_rows(conn, [friends, uncut], db_path=db_path, run_uid="r4", dry_run=False)

    assert removed == 0
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 2
    assert _journal(conn) == []


def test_a_row_with_only_tombstoned_files_is_a_phantom(conn: sqlite3.Connection, db_path: Path) -> None:
    """Tombstoned files are not live: their row is removed, and their index rows go with it."""
    real = _show(conn, "Ted Lasso (2020)", "383203")
    phantom = _show(conn, "Ted Lasso", "383203")
    _episodes(conn, real, "series/Ted Lasso (2020)/Saison 01", 2)
    _episodes(conn, phantom, "series/Ted Lasso/Saison 01", 1, deleted=True)

    ids = phantom_rows(find_provider_id_duplicates(conn))
    removed = remove_phantom_rows(conn, ids, db_path=db_path, run_uid="r5", dry_run=False)

    assert (ids, removed) == ([phantom], 1)
    assert [r[0] for r in conn.execute("SELECT id FROM media_item")] == [real]


def test_remove_keeps_the_movie_row_holding_a_live_file(conn: sqlite3.Connection, db_path: Path) -> None:
    """A movie duplicate group: the row whose release holds a live file is kept, the 0-file twin removed."""
    real = _movie(conn, "Dune (2021)", "438631", files=True)
    phantom = _movie(conn, "Dune", "438631", files=False)

    ids = phantom_rows(find_provider_id_duplicates(conn))
    removed = remove_phantom_rows(conn, [real, *ids], db_path=db_path, run_uid="r7", dry_run=False)

    assert (ids, removed) == ([phantom], 1)
    assert [r[0] for r in conn.execute("SELECT id FROM media_item")] == [real]
    assert _journal(conn) == [("delete", f"index:media_item/{phantom}", "maintenance", "r7")]


def test_remove_deletes_nothing_when_the_row_with_files_lost_them_after_the_plan(
    conn: sqlite3.Connection, db_path: Path
) -> None:
    """Two phantoms planned beside a row with files; a scan tombstones its files before the apply: nothing goes."""
    real = _show(conn, "Andor (2022)", "393189")
    phantom_a = _show(conn, "Andor", "393189")
    phantom_b = _show(conn, "Andor (2022) [dup]", "393189")
    _episodes(conn, real, "series/Andor (2022)/Saison 01", 2)
    ids = phantom_rows(find_provider_id_duplicates(conn))
    assert ids == [phantom_a, phantom_b]
    conn.execute("UPDATE media_file SET deleted_at = 5")

    removed = remove_phantom_rows(conn, ids, db_path=db_path, run_uid="r8", dry_run=False)

    assert removed == 0
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 3
    assert _journal(conn) == []


def test_remove_rolls_back_and_closes_the_transaction_on_any_exception(
    conn: sqlite3.Connection, db_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-sqlite error inside the loop leaves nothing deleted and no transaction open."""
    real = _show(conn, "Severance (2022)", "371980")
    phantom_a = _show(conn, "Severance", "371980")
    phantom_b = _show(conn, "Severance [dup]", "371980")
    _episodes(conn, real, "series/Severance (2022)/Saison 01", 1)
    calls: list[int] = []

    def boom(_conn: sqlite3.Connection, item_id: int, _now: int) -> None:
        calls.append(item_id)
        if len(calls) == 2:
            raise RuntimeError("boom")

    monkeypatch.setattr("personalscraper.indexer.phantom_rows._tombstone", boom)

    with pytest.raises(RuntimeError, match="boom"):
        remove_phantom_rows(conn, [phantom_a, phantom_b], db_path=db_path, run_uid="r9", dry_run=False)

    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 3
    assert _journal(conn) == []
