"""Unit tests for ``personalscraper.app.store`` — the environment's ``app`` store and its baseline."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

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
    assert _user_version(db_path) == 1
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
    """A second open of a migrated file leaves ``user_version`` at 1 and keeps its rows."""
    cfg = _config(test_config, tmp_path / "data")
    first = build_app_store(cfg)
    try:
        first.push.upsert(account_id="alice", token="t1", platform="ios", user_agent=None, now=1.0)
    finally:
        first.close()

    second = build_app_store(cfg)
    try:
        assert [s.token for s in second.push.live_for("alice")] == ["t1"]
    finally:
        second.close()
    assert _user_version(tmp_path / "data" / "app.db") == 1
