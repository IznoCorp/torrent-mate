"""R9 regression: a run losing the pipeline.lock race still journals a terminal row.

The web ``POST /api/pipeline/run`` returns a ``run_uid`` in its 202 before the
spawned ``personalscraper run`` subprocess acquires ``pipeline.lock``. If that
subprocess loses the race it exits without writing any ``pipeline_run`` row, so
``GET /api/pipeline/history/{run_uid}`` 404s forever. ``_journal_lock_conflict``
closes that gap by writing a terminal ``error`` row for the injected run_uid.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from personalscraper.commands.pipeline import _journal_lock_conflict


def _make_pipeline_run_db(path: Path) -> None:
    """Create a minimal ``library.db`` with the ``pipeline_run`` table."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE pipeline_run ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  run_uid TEXT NOT NULL UNIQUE,"
        "  kind TEXT NOT NULL DEFAULT 'pipeline',"
        "  command TEXT,"
        "  trigger TEXT NOT NULL DEFAULT 'web',"
        "  dry_run INTEGER NOT NULL DEFAULT 0,"
        "  options_json TEXT,"
        "  started_at REAL NOT NULL,"
        "  ended_at REAL,"
        "  outcome TEXT,"
        "  steps_json TEXT,"
        "  error TEXT,"
        "  pid INTEGER,"
        "  output_tail TEXT"
        ")"
    )
    conn.commit()
    conn.close()


def _config(db_path: Path) -> SimpleNamespace:
    """A minimal config carrying only ``indexer.db_path`` (all the helper reads)."""
    return SimpleNamespace(indexer=SimpleNamespace(db_path=db_path))


def test_writes_terminal_error_row_for_injected_run_uid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With ``PERSONALSCRAPER_RUN_UID`` set → a terminal ``error`` row is written."""
    db_path = tmp_path / "library.db"
    _make_pipeline_run_db(db_path)
    run_uid = "a1b2c3d4" * 4  # 32 hex chars, like uuid4().hex
    monkeypatch.setenv("PERSONALSCRAPER_RUN_UID", run_uid)

    _journal_lock_conflict(_config(db_path), dry_run=False)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT outcome, trigger, error, ended_at FROM pipeline_run WHERE run_uid = ?",
        (run_uid,),
    ).fetchone()
    conn.close()

    assert row is not None, "the run_uid must resolve (no orphan 404)"
    assert row["outcome"] == "error"
    assert row["trigger"] == "web"
    assert row["ended_at"] is not None
    assert "acquire pipeline.lock" in row["error"]


def test_noop_without_injected_run_uid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No ``PERSONALSCRAPER_RUN_UID`` (a plain CLI run) → no row written."""
    db_path = tmp_path / "library.db"
    _make_pipeline_run_db(db_path)
    monkeypatch.delenv("PERSONALSCRAPER_RUN_UID", raising=False)

    _journal_lock_conflict(_config(db_path), dry_run=False)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM pipeline_run").fetchone()[0]
    conn.close()
    assert count == 0


def test_fail_soft_on_db_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A journaling failure (missing table) must never raise — the caller still exits."""
    db_path = tmp_path / "nonexistent" / "library.db"  # parent dir missing → write fails
    monkeypatch.setenv("PERSONALSCRAPER_RUN_UID", "deadbeef" * 4)

    # Must not raise despite the unwritable path.
    _journal_lock_conflict(_config(db_path), dry_run=True)
