"""A fresh environment's library DB is migrated before the first run-history write.

Covers: the run boot migrates a missing / empty ``library.db`` (the row lands), a missing DB is a
named, logged condition rather than an empty file created by the writer, a DB that cannot be
migrated is reported once for the run, the newer-schema guard still comes first, and a store
at head is left untouched.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from personalscraper.app.supervisor.execution import _open_history_writer
from personalscraper.core.sqlite import apply_migrations
from personalscraper.indexer.migrations import MIGRATIONS_DIR
from personalscraper.pipeline_history import PipelineRunWriter


def _config_for(db_path: Path) -> MagicMock:
    """Build a config double whose ``indexer.db_path`` is *db_path*.

    Args:
        db_path: The library DB path the boot must use.

    Returns:
        A mock exposing only ``indexer.db_path``.
    """
    config = MagicMock()
    config.indexer.db_path = db_path
    return config


def _rows(db_path: Path) -> list[tuple[str, str | None]]:
    """Read ``(run_uid, outcome)`` of every ``pipeline_run`` row.

    Args:
        db_path: The library DB path.

    Returns:
        The rows, oldest first.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute("SELECT run_uid, outcome FROM pipeline_run ORDER BY id").fetchall()
    finally:
        conn.close()


def test_run_boot_on_a_fresh_data_dir_writes_its_pipeline_run_row(tmp_path: Path) -> None:
    """A run on a fresh data dir migrates the library DB, then its row is written."""
    db_path = tmp_path / "data" / "library-staging.db"
    writer = _open_history_writer(_config_for(db_path))
    assert writer is not None
    writer.insert("run-1", trigger="cron", dry_run=False, pid=1)
    writer.finalize("run-1", "success")
    assert _rows(db_path) == [("run-1", "success")]


def test_run_boot_on_an_empty_db_file_migrates_it_without_backup(tmp_path: Path) -> None:
    """The empty file the old writer left behind is migrated, with no ``.bak`` to protect nothing."""
    db_path = tmp_path / "library-staging.db"
    sqlite3.connect(str(db_path)).close()
    writer = _open_history_writer(_config_for(db_path))
    assert writer is not None
    writer.insert("run-1", trigger="cron", dry_run=False, pid=1)
    assert _rows(db_path) == [("run-1", "running")]
    assert list(tmp_path.glob("*.bak")) == []


def test_run_boot_leaves_a_store_at_head_untouched(tmp_path: Path) -> None:
    """An existing store at head is a no-op: no backup, same schema version."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    apply_migrations(conn, MIGRATIONS_DIR)
    head = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    before = sorted(p.name for p in tmp_path.iterdir())
    assert _open_history_writer(_config_for(db_path)) is not None
    assert sorted(p.name for p in tmp_path.iterdir()) == before
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == head
    conn.close()


def test_run_boot_refuses_a_newer_schema_before_any_migration(tmp_path: Path, logged_events) -> None:  # type: ignore[no-untyped-def]
    """A store migrated past the code is neither migrated nor written: no writer, one error event."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA user_version = 9999")
    conn.close()
    with logged_events() as logs:
        assert _open_history_writer(_config_for(db_path)) is None
    errors = [e for e in logs if e["log_level"] == "error" and e["event"] == "pipeline_history.library_db_unavailable"]
    assert len(errors) == 1
    conn = sqlite3.connect(str(db_path))
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 9999
    assert conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0
    conn.close()
    assert list(tmp_path.glob("*.bak")) == []


def test_unopenable_db_is_one_error_event_and_no_per_step_warnings(tmp_path: Path, logged_events) -> None:  # type: ignore[no-untyped-def]
    """A DB that cannot be opened gives one error for the run; the run goes on without a writer."""
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")
    with logged_events() as logs:
        assert _open_history_writer(_config_for(blocker / "library.db")) is None
    assert [e["event"] for e in logs if e["log_level"] == "error"] == ["pipeline_history.library_db_unavailable"]
    assert [e for e in logs if e["log_level"] == "warning"] == []


@pytest.mark.parametrize("method", ["insert", "update_pid", "update_step", "finalize"])
def test_writer_on_a_missing_db_creates_no_file_and_names_the_condition(
    tmp_path: Path,
    method: str,
    logged_events,  # type: ignore[no-untyped-def]
) -> None:
    """``pipeline_history`` never creates a DB through ``connect()``: a missing one is a named event."""
    db_path = tmp_path / "library-staging.db"
    writer = PipelineRunWriter(db_path)
    calls = {
        "insert": lambda: writer.insert("r", trigger="cli", dry_run=False, pid=1),
        "update_pid": lambda: writer.update_pid("r", 2),
        "update_step": lambda: writer.update_step("r", "ingest", 1.0, 2.0, "success"),
        "finalize": lambda: writer.finalize("r", "success"),
    }
    with logged_events() as logs:
        calls[method]()
    assert not db_path.exists()
    assert [e for e in logs if e["event"] == "pipeline_history.db_missing"]
