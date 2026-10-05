"""Unit tests for ``personalscraper.app.store`` — the environment's ``app`` store and its baseline."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from personalscraper.app.accounts.repository import AccountRow
from personalscraper.app.accounts.sessions import SessionService
from personalscraper.app.store import store as store_module
from personalscraper.app.store.store import AppStore, build_app_store
from personalscraper.conf.models.config import Config


def _config(test_config: Config, data_dir: Path) -> Config:
    """Return *test_config* with ``paths.data_dir`` pointed at *data_dir*.

    Args:
        test_config: The synthetic Config fixture.
        data_dir: The data directory the store derives its path from.

    Returns:
        A copy of the Config over *data_dir*.
    """
    return test_config.model_copy(update={"paths": test_config.paths.model_copy(update={"data_dir": data_dir})})


def _user_version(db_path: Path) -> int:
    """Read ``PRAGMA user_version`` of the database at *db_path*.

    Args:
        db_path: The SQLite file.

    Returns:
        The schema version.
    """
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def test_first_use_creates_app_db_at_baseline(test_config: Config, tmp_path: Path) -> None:
    """The first access opens ``app.db``: baseline applied, ``push_subscription`` present."""
    data_dir = tmp_path / "data"
    store = build_app_store(_config(test_config, data_dir))
    try:
        store.push.live_for("nobody")
    finally:
        store.close()

    db_path = data_dir / "app.db"
    assert db_path.is_file()
    assert _user_version(db_path) == 6
    conn = sqlite3.connect(db_path)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()
    assert "push_subscription" in tables


def test_the_environment_names_the_file(test_config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Under ``PERSONALSCRAPER_ENV=dev`` the store is ``app-dev.db``, never ``app.db``."""
    monkeypatch.setenv("PERSONALSCRAPER_ENV", "dev")
    data_dir = tmp_path / "data"
    store = build_app_store(_config(test_config, data_dir))
    try:
        store.push.live_for("nobody")
    finally:
        store.close()

    assert (data_dir / "app-dev.db").is_file()
    assert not (data_dir / "app.db").exists()


def test_building_the_store_creates_no_file(test_config: Config, tmp_path: Path) -> None:
    """``build_app_store`` is inert: no directory, no file, no lock until first use."""
    data_dir = tmp_path / "data"
    store = build_app_store(_config(test_config, data_dir))
    try:
        assert isinstance(store, AppStore)
        assert not data_dir.exists()
    finally:
        store.close()


def test_reopening_applies_nothing(test_config: Config, tmp_path: Path) -> None:
    """A second open of a migrated file leaves ``user_version`` at 5 and keeps its rows."""
    cfg = _config(test_config, tmp_path / "data")
    first = build_app_store(cfg)
    try:
        first.accounts.insert_account(
            AccountRow(
                id="alice",
                name="Alice",
                email="alice@example.org",
                avatar="",
                role_id="local-guest",
                password_hash=None,
                created_at=0.0,
                updated_at=0.0,
            )
        )
        first.push.upsert(account_id="alice", token="t1", platform="ios", user_agent=None, now=1.0)
    finally:
        first.close()

    second = build_app_store(cfg)
    try:
        assert [s.token for s in second.push.live_for("alice")] == ["t1"]
    finally:
        second.close()
    assert _user_version(tmp_path / "data" / "app.db") == 6


def test_concurrent_first_accesses_open_one_connection(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Threads racing on a fresh store's first access open exactly one connection, closed by ``close``."""
    threads_count = 12
    opened: list[sqlite3.Connection] = []
    real_open_db = store_module.open_db

    def counting_open_db(db_path: Path) -> sqlite3.Connection:
        """Open through the real ``open_db`` and record the connection.

        Args:
            db_path: The file to open.

        Returns:
            The open connection.
        """
        conn = real_open_db(db_path)
        opened.append(conn)
        return conn

    monkeypatch.setattr(store_module, "open_db", counting_open_db)
    store = AppStore(tmp_path / "app.db")
    barrier = threading.Barrier(threads_count)
    errors: list[BaseException] = []

    def first_access() -> None:
        """Wait for every thread, then touch the store; record what it raises."""
        barrier.wait()
        try:
            store.accounts  # noqa: B018 — the accessor itself opens the store
        except BaseException as exc:  # noqa: BLE001 — a thread's failure is asserted by the test
            errors.append(exc)

    workers = [threading.Thread(target=first_access) for _ in range(threads_count)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    store.close()

    assert errors == []
    assert len(opened) == 1
    still_open = 0
    for conn in opened:
        try:
            conn.execute("SELECT 1")
        except sqlite3.ProgrammingError:
            continue
        still_open += 1
    assert still_open == 0


def test_concurrent_queries_share_the_one_connection_safely(tmp_path: Path) -> None:
    """Threads querying one open store at once each read the right rows; none crashes the process."""
    threads_count = 12
    store = AppStore(tmp_path / "app.db")
    store.accounts.insert_account(
        AccountRow(
            id="alice",
            name="Alice",
            email="alice@example.org",
            avatar="",
            role_id="household",
            password_hash=None,
            created_at=0.0,
            updated_at=0.0,
        )
    )
    sessions = SessionService(lambda: store.accounts, idle_days=1)
    barrier = threading.Barrier(threads_count)
    errors: list[BaseException] = []
    results: list[bool] = []

    def query(index: int) -> None:
        """Wait for every thread, then read a role, or open, resolve and close a session.

        Args:
            index: The thread's number; even ones read a role, odd ones run a session.
        """
        barrier.wait()
        try:
            for _ in range(20):
                if index % 2 == 0:
                    role = store.accounts.role("admin")
                    results.append(role is not None and role.id == "admin")
                else:
                    token = sessions.open("alice", user_agent=None)
                    actor = sessions.resolve(token)
                    sessions.close(token)
                    results.append(
                        actor is not None and actor.account_id == "alice" and sessions.resolve(token) is None
                    )
        except BaseException as exc:  # noqa: BLE001 — a thread's failure is asserted by the test
            errors.append(exc)

    workers = [threading.Thread(target=query, args=(index,)) for index in range(threads_count)]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
    finally:
        store.close()

    assert errors == []
    assert len(results) == threads_count * 20
    assert all(results)
