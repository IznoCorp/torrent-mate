"""``connect_read_only``: a read-only open that survives a WAL database no process holds.

SQLite refuses ``mode=ro`` on a WAL database whose ``-shm`` is absent (« unable to open database
file »), which is the state of every store whose last writer closed cleanly. The helper retries
once ``mode=rw`` with ``query_only`` on exactly that failure, when the file exists; an absent file
and a file that is no database stay errors.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

import pytest

from personalscraper.core.sqlite import connect_read_only
from tests._doubles.idle_wal import leave_wal_database, refuse_idle_wal_read_only


def _idle_wal_db(path: Path) -> None:
    """Leave a one-row WAL database that no process holds: its writer closed cleanly.

    Args:
        path: Where the database is written.
    """
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    leave_wal_database(path)


@pytest.fixture(autouse=True)
def _old_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test under an SQLite that refuses a ``mode=ro`` open of an idle WAL database.

    Args:
        monkeypatch: The test's monkeypatch.
    """
    refuse_idle_wal_read_only(monkeypatch)


def test_a_plain_read_only_open_cannot_read_an_idle_wal_database(tmp_path: Path) -> None:
    """The defect itself, as SQLite 3.51 shows it: ``mode=ro`` alone is refused, which the helper exists for."""
    path = tmp_path / "idle.db"
    _idle_wal_db(path)

    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def test_an_idle_wal_database_is_read(tmp_path: Path) -> None:
    """The retry reads the rows a clean writer left."""
    path = tmp_path / "idle.db"
    _idle_wal_db(path)

    with connect_read_only(path) as conn:
        assert conn.execute("SELECT x FROM t").fetchall() == [(1,)]


def test_the_retry_connection_can_write_nothing(tmp_path: Path) -> None:
    """The retry is read-write at the file only: ``query_only`` refuses every write."""
    path = tmp_path / "idle.db"
    _idle_wal_db(path)

    conn = connect_read_only(path)
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        conn.execute("INSERT INTO t VALUES (2)")
    conn.close()
    assert sqlite3.connect(path).execute("SELECT COUNT(*) FROM t").fetchone() == (1,)


def test_a_database_that_opens_read_only_is_not_retried(tmp_path: Path) -> None:
    """A rollback-journal database opens ``mode=ro`` at once and the helper writes no side file."""
    path = tmp_path / "plain.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.commit()
    conn.close()

    with connect_read_only(path) as reader:
        assert reader.execute("SELECT COUNT(*) FROM t").fetchone() == (0,)
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("INSERT INTO t VALUES (1)")
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["plain.db"]


def test_an_absent_file_stays_an_error_and_is_never_created(tmp_path: Path) -> None:
    """No retry for a file that is not there: ``rw`` never creates it."""
    path = tmp_path / "absent.db"

    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        connect_read_only(path)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("content", [b"not a database at all, just bytes" * 64])
def test_a_file_that_is_no_database_stays_an_error(tmp_path: Path, content: bytes) -> None:
    """The retry answers one failure only: a file that is no database is refused as before."""
    path = tmp_path / "junk.db"
    path.write_bytes(content)

    with pytest.raises(sqlite3.DatabaseError, match="not a database"):
        connect_read_only(path)

    assert path.read_bytes() == content
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["junk.db"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_a_directory_that_cannot_take_side_files_keeps_the_original_error(tmp_path: Path) -> None:
    """When the retry cannot create ``-shm`` either, the caller gets the first error."""
    folder = tmp_path / "frozen"
    folder.mkdir()
    path = folder / "idle.db"
    _idle_wal_db(path)
    folder.chmod(0o555)
    try:
        with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
            connect_read_only(path)
    finally:
        folder.chmod(0o755)


def test_connect_arguments_reach_sqlite(tmp_path: Path) -> None:
    """``check_same_thread`` and ``isolation_level`` are forwarded to both opens."""
    path = tmp_path / "idle.db"
    _idle_wal_db(path)
    conn = connect_read_only(path, check_same_thread=False, isolation_level=None, timeout=1.0)
    seen: list[tuple[int, ...]] = []

    worker = threading.Thread(target=lambda: seen.extend(conn.execute("SELECT x FROM t").fetchall()))
    worker.start()
    worker.join()
    isolation_level = conn.isolation_level
    conn.close()

    assert seen == [(1,)]
    assert isolation_level is None


def test_an_idle_wal_database_is_read_with_the_real_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Whatever the SQLite build refuses or accepts, the helper reads an idle WAL database."""
    monkeypatch.undo()
    path = tmp_path / "idle.db"
    _idle_wal_db(path)

    with connect_read_only(path) as conn:
        assert conn.execute("SELECT x FROM t").fetchall() == [(1,)]
