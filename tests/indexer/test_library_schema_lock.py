"""Every library DB migration takes the indexer's lock, and run history ensures the schema.

Covers: the web boot, ``MediaIndex`` and the single-item rescrape migrate through
:func:`personalscraper.indexer.db.ensure_library_schema` (a held ``<db>.lock`` keeps them from
touching the store), and ``PipelineRunWriter`` ensures the schema itself on a fresh environment,
reporting a store it cannot ensure once, not once per write.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper import pipeline_history
from personalscraper.app.supervisor.execution import rescrape_item
from personalscraper.core.sqlite import SqliteSchemaNewerError, db_lock
from personalscraper.dispatch.media_index import MediaIndex
from personalscraper.indexer import db as indexer_db
from personalscraper.indexer.db import IndexerLockError
from personalscraper.pipeline_history import PipelineRunWriter
from personalscraper.web.app import _apply_pending_indexer_migrations


@pytest.fixture(autouse=True)
def _short_lock_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make a held lock refuse quickly, and forget the writer's per-process ensure memory."""
    monkeypatch.setattr(indexer_db, "_MIGRATION_LOCK_TIMEOUT_S", 0.2)
    monkeypatch.setattr(pipeline_history, "_UNENSURABLE", set(), raising=False)


def _empty_store(db_path: Path) -> Path:
    """Create an empty (``user_version`` 0) SQLite file, the store an older code left behind.

    Args:
        db_path: Where to create it.

    Returns:
        *db_path*.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    sqlite3.connect(str(db_path)).close()
    return db_path


def _version(db_path: Path) -> int:
    """Read ``PRAGMA user_version`` of *db_path*.

    Args:
        db_path: The store.

    Returns:
        Its schema version.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])
    finally:
        conn.close()


def _config_for(db_path: Path) -> MagicMock:
    """Build a config double whose ``indexer.db_path`` is *db_path*.

    Args:
        db_path: The library DB path.

    Returns:
        A mock exposing ``indexer.db_path``.
    """
    config = MagicMock()
    config.indexer.db_path = db_path
    return config


def test_web_boot_migration_waits_on_the_indexer_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, logged_events
) -> None:  # type: ignore[no-untyped-def]
    """A held lock keeps the web boot off the store: fail-soft, one error event, store untouched."""
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    db_path = _empty_store(tmp_path / "library.db")
    with db_lock(db_path), logged_events() as logs:
        _apply_pending_indexer_migrations(_config_for(db_path))
    assert _version(db_path) == 0
    assert [e["event"] for e in logs if e["log_level"] == "error"] == ["web_boot_migrate_failed"]


def test_web_boot_migration_still_fails_closed_on_a_newer_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The newer-schema refusal is still raised through the shared function."""
    monkeypatch.delenv("PERSONALSCRAPER_WEB_ROLE", raising=False)
    db_path = _empty_store(tmp_path / "library.db")
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 9999")
    conn.close()
    with pytest.raises(SqliteSchemaNewerError):
        _apply_pending_indexer_migrations(_config_for(db_path))
    assert _version(db_path) == 9999


def test_media_index_migration_waits_on_the_indexer_lock(tmp_path: Path) -> None:
    """``MediaIndex`` cannot migrate the store while another process holds its lock."""
    db_path = _empty_store(tmp_path / "library.db")
    with db_lock(db_path), pytest.raises(IndexerLockError):
        MediaIndex(db_path, auto_rebuild=False, event_bus=MagicMock())
    assert _version(db_path) == 0


@contextmanager
def _passthrough(*_args: object) -> Iterator[MagicMock]:
    """Stand in for the run-row / step-boundary context managers.

    Yields:
        A mock for the context value.
    """
    yield MagicMock()


def test_single_item_rescrape_migration_waits_on_the_indexer_lock(tmp_path: Path) -> None:
    """The item rescrape exits 1 when the lock is held, leaving the store unmigrated."""
    db_path = _empty_store(tmp_path / "library.db")
    with db_lock(db_path):
        code = rescrape_item(
            _config_for(db_path),
            MagicMock(),
            42,
            console=MagicMock(),
            run_row=_passthrough,
            step_boundary=_passthrough,
        )
    assert code == 1
    assert _version(db_path) == 0


def test_writer_on_a_fresh_data_dir_ensures_the_schema_and_writes_its_row(tmp_path: Path) -> None:
    """A writer built over a missing DB migrates it, so the run-history row is kept."""
    db_path = tmp_path / "data" / "library-staging.db"
    writer = PipelineRunWriter(db_path)
    writer.insert("run-1", trigger="cron", dry_run=False, pid=1)
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("SELECT run_uid, outcome FROM pipeline_run").fetchall() == [("run-1", "running")]
    finally:
        conn.close()


def test_writer_that_cannot_ensure_the_schema_logs_once_across_writes(tmp_path: Path, logged_events) -> None:  # type: ignore[no-untyped-def]
    """An unensurable store is one error event, never a warning per call."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    writer = PipelineRunWriter(blocker / "library.db")
    with logged_events() as logs:
        writer.insert("r", trigger="cli", dry_run=False, pid=1)
        writer.update_pid("r", 2)
        writer.update_step("r", "ingest", 1.0, 2.0, "success")
        writer.finalize("r", "success")
    assert [e["event"] for e in logs if e["log_level"] in ("error", "warning")] == [
        "pipeline_history.library_db_unavailable"
    ]
