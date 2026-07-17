"""Unit tests for :func:`personalscraper.web.decisions.reserve._reserve_decision_run`.

Sub-phase 2.3 — covers the reservation contract:

* Row is inserted atomically under ``BEGIN IMMEDIATE`` with correct column values.
* Second concurrent reservation → 409 (live-pid guard).
* Dead-pid stale running row → allowed (mirrors maintenance stale-pid semantics).
* DB error → 409 fail-CLOSED (a resolve WRITES to staging).
* Reserved row is finalizable afterwards via :class:`PipelineRunWriter`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from personalscraper.core.sqlite._pragmas import apply_pragmas

# ---------------------------------------------------------------------------
# Helpers — DB setup (migration 011 pipeline_run schema)
# ---------------------------------------------------------------------------

PIPELINE_RUN_DDL = """
CREATE TABLE pipeline_run (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_uid      TEXT    UNIQUE NOT NULL,
    trigger      TEXT    NOT NULL,
    dry_run      INTEGER NOT NULL DEFAULT 0,
    started_at   REAL    NOT NULL,
    ended_at     REAL,
    outcome      TEXT,
    steps_json   TEXT,
    error        TEXT,
    pid          INTEGER,
    kind         TEXT    NOT NULL DEFAULT 'pipeline',
    command      TEXT    NULL,
    options_json TEXT    NULL,
    output_tail  TEXT    NULL
);
CREATE INDEX idx_pipeline_run_started ON pipeline_run(started_at);
CREATE INDEX idx_pipeline_run_kind ON pipeline_run(kind);
"""


def _create_db(db_path: Path) -> None:
    """Create an on-disk SQLite DB with the ``pipeline_run`` table."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()


def _select_row(db_path: Path, run_uid: str) -> dict | None:
    """Return the ``pipeline_run`` row as a dict, or ``None``."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM pipeline_run WHERE run_uid = ?", (run_uid,)).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _insert_running_row(
    db_path: Path,
    run_uid: str,
    pid: int | None = None,
    command: str = "scrape-resolve",
    decision_id: int | None = None,
) -> None:
    """Insert a running ``pipeline_run`` row directly (bypassing the reserve function).

    Args:
        db_path: Path to the test database.
        run_uid: The unique run identifier.
        pid: The pid to write (``None`` for a NULL-pid stale row).
        command: The ``command`` column value.
        decision_id: Optional ``decision_id`` embedded in ``options_json`` so the
            per-decision reservation guard (scoped by
            ``json_extract(options_json, '$.decision_id')``) can match it.  When
            ``None`` an empty ``{}`` is stored (scoped to no decision).
    """
    options_json = "{}" if decision_id is None else json.dumps({"decision_id": decision_id})
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.execute(
        "INSERT INTO pipeline_run "
        "(run_uid, trigger, dry_run, started_at, outcome, steps_json, pid, kind, command, options_json) "
        "VALUES (?, 'web', 0, ?, 'running', '[]', ?, 'maintenance', ?, ?)",
        (run_uid, time.time(), pid, command, options_json),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Tests — basic reservation
# ---------------------------------------------------------------------------


class TestReserveDecisionRun:
    """Unit tests for :func:`_reserve_decision_run`."""

    def test_inserts_row_with_correct_columns(self, tmp_path: Path) -> None:
        """After reservation the row has kind, command, options_json, trigger, outcome, pid."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        run_uid = "reserve-001"

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        _reserve_decision_run(
            db_path,
            run_uid=run_uid,
            decision_id=42,
            provider="tmdb",
            provider_id=12345,
        )

        row = _select_row(db_path, run_uid)
        assert row is not None
        assert row["kind"] == "maintenance"
        assert row["command"] == "scrape-resolve"
        assert row["trigger"] == "web"
        assert row["dry_run"] == 0
        assert row["outcome"] == "running"
        assert row["pid"] == os.getpid()
        assert row["started_at"] is not None
        assert row["steps_json"] == "[]"

        options = json.loads(row["options_json"])
        assert options == {"decision_id": 42, "provider": "tmdb", "provider_id": 12345}

    def test_missing_db_returns_early_no_error(self, tmp_path: Path) -> None:
        """When the DB file does not exist, the function is a no-op (no exception)."""
        db_path = tmp_path / "nonexistent.db"

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        # Must not raise.
        _reserve_decision_run(
            db_path,
            run_uid="noop-run",
            decision_id=1,
            provider="tmdb",
            provider_id=1,
        )

    # ------------------------------------------------------------------
    # Concurrency guard
    # ------------------------------------------------------------------

    def test_concurrent_resolve_raises_409_with_live_pid(self, tmp_path: Path) -> None:
        """A second reservation while a live-pid resolve of THIS decision is running → 409."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        # Insert a running row for decision 1 with OUR pid (guaranteed alive).
        _insert_running_row(db_path, "existing-run", pid=os.getpid(), decision_id=1)

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        with pytest.raises(HTTPException) as exc_info:
            _reserve_decision_run(
                db_path,
                run_uid="new-run",
                decision_id=1,
                provider="tmdb",
                provider_id=1,
            )
        assert exc_info.value.status_code == 409

    def test_concurrent_resolve_of_different_decision_allowed(self, tmp_path: Path) -> None:
        """A live-pid resolve of a DIFFERENT decision does NOT block this reservation.

        Per-decision scoping (webui-ux phase 4): the guard filters running rows by
        ``json_extract(options_json, '$.decision_id')``, so a live resolve of
        decision 2 leaves decision 1 free to reserve concurrently.
        """
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        # A live resolve of decision 2 must NOT block a reservation for decision 1.
        _insert_running_row(db_path, "other-run", pid=os.getpid(), decision_id=2)

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        _reserve_decision_run(
            db_path,
            run_uid="new-run",
            decision_id=1,
            provider="tmdb",
            provider_id=1,
        )

        row = _select_row(db_path, "new-run")
        assert row is not None
        assert row["outcome"] == "running"

    def test_dead_pid_stale_row_allows_new_reservation(self, tmp_path: Path) -> None:
        """A running row with a dead pid is stale → new reservation succeeds."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        stale_pid = 99999
        _insert_running_row(db_path, "stale-run", pid=stale_pid, decision_id=1)

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        # Patch os.kill so stale_pid raises ProcessLookupError (dead process).
        original_kill = os.kill

        def patched_kill(pid: int, sig: int) -> None:
            if pid == stale_pid:
                raise ProcessLookupError()
            return original_kill(pid, sig)  # type: ignore[func-returns-value]

        with patch("personalscraper.web.decisions.reserve.os.kill", patched_kill):
            _reserve_decision_run(
                db_path,
                run_uid="new-run",
                decision_id=1,
                provider="tmdb",
                provider_id=1,
            )

        row = _select_row(db_path, "new-run")
        assert row is not None
        assert row["outcome"] == "running"

    def test_null_pid_stale_row_allows_new_reservation(self, tmp_path: Path) -> None:
        """A running row with NULL pid (pre-migration) is stale → allowed."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        _insert_running_row(db_path, "null-pid-run", pid=None, decision_id=1)

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        _reserve_decision_run(
            db_path,
            run_uid="new-run",
            decision_id=1,
            provider="tmdb",
            provider_id=1,
        )

        row = _select_row(db_path, "new-run")
        assert row is not None
        assert row["outcome"] == "running"

    def test_other_command_running_does_not_block_resolve(self, tmp_path: Path) -> None:
        """A running maintenance row with a DIFFERENT command does NOT block resolve."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        # A library-index is running (live pid), but command != 'scrape-resolve'.
        _insert_running_row(db_path, "index-run", pid=os.getpid(), command="library-index")

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        _reserve_decision_run(
            db_path,
            run_uid="resolve-run",
            decision_id=1,
            provider="tmdb",
            provider_id=1,
        )

        row = _select_row(db_path, "resolve-run")
        assert row is not None
        assert row["outcome"] == "running"

    # ------------------------------------------------------------------
    # Fail-CLOSED on DB error
    # ------------------------------------------------------------------

    def test_db_error_fail_closed_409(self, tmp_path: Path) -> None:
        """When the DB raises OperationalError during BEGIN, fail-CLOSED with 409."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        # Simulate a connection that works for PRAGMAs but fails on BEGIN IMMEDIATE.
        # Pass the real db_path so the exists() guard passes; the mock intercepts
        # the actual connect call.
        mock_conn = MagicMock()

        def mock_execute(sql: str, params: object = None) -> MagicMock:
            if isinstance(sql, str) and "BEGIN" in sql:
                raise sqlite3.OperationalError("database is locked")
            return MagicMock()

        mock_conn.execute = mock_execute

        with patch("personalscraper.web._runner_engine.sqlite3.connect", return_value=mock_conn):
            with pytest.raises(HTTPException) as exc_info:
                _reserve_decision_run(
                    db_path,
                    run_uid="fail-closed-run",
                    decision_id=1,
                    provider="tmdb",
                    provider_id=1,
                )

        assert exc_info.value.status_code == 409
        assert "Cannot verify" in exc_info.value.detail

    # ------------------------------------------------------------------
    # Finalizability
    # ------------------------------------------------------------------

    def test_reserved_row_can_be_finalized(self, tmp_path: Path) -> None:
        """PipelineRunWriter.finalize works on the row reserved by _reserve_decision_run."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        run_uid = "finalize-test"

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        _reserve_decision_run(
            db_path,
            run_uid=run_uid,
            decision_id=1,
            provider="tmdb",
            provider_id=1,
        )

        from personalscraper.pipeline_history import PipelineRunWriter

        writer = PipelineRunWriter(db_path)
        writer.finalize(run_uid, "success")

        row = _select_row(db_path, run_uid)
        assert row["outcome"] == "success"
        assert row["ended_at"] is not None
        assert row["error"] is None

    def test_reserved_row_can_be_finalized_with_error(self, tmp_path: Path) -> None:
        """PipelineRunWriter.finalize with 'error' outcome works on the reserved row."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        run_uid = "finalize-error-test"

        from personalscraper.web.decisions.reserve import _reserve_decision_run

        _reserve_decision_run(
            db_path,
            run_uid=run_uid,
            decision_id=1,
            provider="tvdb",
            provider_id=999,
        )

        from personalscraper.pipeline_history import PipelineRunWriter

        writer = PipelineRunWriter(db_path)
        writer.finalize(run_uid, "error", error="scrape failed")

        row = _select_row(db_path, run_uid)
        assert row["outcome"] == "error"
        assert row["ended_at"] is not None
        assert row["error"] == "scrape failed"
