"""Each reader of a store opens it through ``connect_read_only``: an idle WAL store is read.

A store whose last writer closed cleanly has no ``-shm``; an SQLite that refuses ``mode=ro`` then
(``tests/_doubles/idle_wal.py``) must not make these readers answer « unavailable ». The helper's own
cases are in ``test_sqlite_read_only.py`` and the library view's in ``tests/indexer/test_library_view.py``.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import pytest

from personalscraper.acquire.catalogue import CatalogueEpisode, CatalogueStore
from personalscraper.commands.run_follow import _read_only
from personalscraper.core.sqlite import db_lock
from personalscraper.indexer.db import IndexerLockError, ensure_library_schema
from tests._doubles.idle_wal import leave_wal_database, refuse_idle_wal_read_only


@pytest.fixture(autouse=True)
def _old_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test under an SQLite that refuses a ``mode=ro`` open of an idle WAL database.

    Args:
        monkeypatch: The test's monkeypatch.
    """
    refuse_idle_wal_read_only(monkeypatch)


def test_the_catalogue_reads_an_idle_wal_store(tmp_path: Path) -> None:
    """``CatalogueStore.read_only`` reads what the writable store left, once the writer closed."""
    path = tmp_path / "acquire.db"
    episode = CatalogueEpisode(season=1, episode=1, air_date=date(2020, 1, 1), title=None)
    writer = CatalogueStore(path)
    writer.replace_show("tvdb", "1", "Continuing", [episode], 1_700_000_000.0)
    writer.close()
    leave_wal_database(path)

    reader = CatalogueStore.read_only(path)
    try:
        assert reader.episodes("tvdb", "1") == [episode]
    finally:
        reader.close()


def test_the_schema_probe_sees_an_idle_wal_store_at_head(tmp_path: Path) -> None:
    """A library at head whose writer closed is a no-op: the probe reads it, so no migration lock is taken."""
    path = tmp_path / "library.db"
    ensure_library_schema(path)
    leave_wal_database(path)

    with db_lock(path, timeout=0):  # a held lock refuses any ensure that decides to migrate
        ensure_library_schema(path)


def test_the_schema_probe_still_migrates_what_is_behind(tmp_path: Path) -> None:
    """An empty store is not at head: the ensure goes on to migrate it under the lock."""
    path = tmp_path / "library.db"
    sqlite3.connect(path).close()

    with db_lock(path, timeout=0), pytest.raises(IndexerLockError):
        ensure_library_schema(path)


def test_the_follower_reads_an_idle_wal_indexer(tmp_path: Path) -> None:
    """The run follower's indexer connection reads a library no process holds, and still writes nothing."""
    path = tmp_path / "library.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE pipeline_run (run_uid TEXT)")
    conn.execute("INSERT INTO pipeline_run VALUES ('r1')")
    conn.commit()
    conn.close()
    leave_wal_database(path)

    with _read_only(path) as reader:
        assert reader.execute("SELECT run_uid FROM pipeline_run").fetchall() == [("r1",)]
        with pytest.raises(sqlite3.OperationalError):
            reader.execute("DELETE FROM pipeline_run")
