"""``AcquireRequesters``: who asked for a follow, read from ``acquire.db`` as the file stands."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from personalscraper.acquire.store import build_acquire_store
from personalscraper.app.supervisor.requesters import AcquireRequesters
from personalscraper.conf.models.config import Config


def test_it_reads_the_requesters_of_a_follow_from_a_migrated_store(tmp_path: Path, test_config: Config) -> None:
    """A real ``acquire.db``: the accounts of each follow, and nobody for another."""
    config = test_config.acquire.model_copy(update={"db_path": tmp_path / "acquire.db"})
    store = build_acquire_store(config)
    try:
        store.follow.list_active()  # opens and migrates the file
    finally:
        store.close()
    conn = sqlite3.connect(tmp_path / "acquire.db")
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executemany(
            "INSERT INTO acquisition_requester (followed_id, account_id, via, floor, paused, since) "
            "VALUES (?, ?, 'follow', NULL, 0, 1)",
            [(7, "account-a"), (7, "account-b"), (8, "account-c")],
        )
        conn.commit()
    finally:
        conn.close()
    requesters = AcquireRequesters(tmp_path / "acquire.db")

    assert sorted(requesters.requesters_of(7)) == ["account-a", "account-b"]
    assert list(requesters.requesters_of(8)) == ["account-c"]
    assert list(requesters.requesters_of(9)) == []


def test_an_absent_file_reads_as_nobody_and_is_not_created(tmp_path: Path) -> None:
    """The web process never creates ``acquire.db``: a missing file is an empty answer, and stays missing."""
    path = tmp_path / "acquire.db"

    assert list(AcquireRequesters(path).requesters_of(7)) == []
    assert not path.exists()


def test_a_store_without_the_table_reads_as_nobody(tmp_path: Path) -> None:
    """A file that predates the requesters (no table) fails closed: nobody asked."""
    path = tmp_path / "acquire.db"
    sqlite3.connect(path).close()

    assert list(AcquireRequesters(path).requesters_of(7)) == []
