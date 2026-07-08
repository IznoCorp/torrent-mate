"""Unit tests for personalscraper.run_journal (universal run journal).

Covers the 2026-07-08 "silent run" gap: pipeline invocations that do not go
through the web UI (direct CLI step commands, safety_net-spawned runs) left no
``pipeline_run`` row and no ``output_tail``, so the UI showed a running
pipeline with "aucun log pour cette exécution".

- ``TestLogTailHandler`` — ring-buffer log capture: records formatted lines,
  trims to the byte cap from the front, returns ``None`` when nothing logged.
- ``TestCliStepJournal`` — the context manager wraps ONE CLI step command:
  inserts a ``pipeline_run`` row (``trigger='cli'``, ``kind='pipeline'``,
  ``command=<step>``), finalizes with the captured ``output_tail``, maps
  exceptions to ``outcome='error'`` (re-raised), ``typer.Exit(0)`` to success,
  and stays fail-soft when the DB path is unusable.
- ``TestPerStepBoundaryPublisher`` — the per-step CLI boundary builds the
  fail-soft Redis event publisher (live feed for step runs) and closes it.
"""

from __future__ import annotations

import logging
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.run_journal import LogTailHandler, cli_step_journal

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
)
"""


def _create_db(db_path: Path) -> None:
    """Create a SQLite database with the ``pipeline_run`` table."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    conn.executescript(PIPELINE_RUN_DDL)
    conn.commit()
    conn.close()


def _fetch_only_row(db_path: Path) -> dict:
    """Return the single ``pipeline_run`` row as a dict (fails if 0 or 2+)."""
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    apply_pragmas(conn)
    rows = conn.execute(
        "SELECT run_uid, trigger, dry_run, ended_at, outcome, error, pid, kind, command, output_tail FROM pipeline_run"
    ).fetchall()
    conn.close()
    assert len(rows) == 1, f"expected exactly one pipeline_run row, got {len(rows)}"
    keys = ("run_uid", "trigger", "dry_run", "ended_at", "outcome", "error", "pid", "kind", "command", "output_tail")
    return dict(zip(keys, rows[0], strict=True))


def _config_with_db(db_path: Path) -> MagicMock:
    """Minimal config stub exposing ``indexer.db_path``."""
    config = MagicMock()
    config.indexer.db_path = db_path
    return config


# ---------------------------------------------------------------------------
# LogTailHandler
# ---------------------------------------------------------------------------


class TestLogTailHandler:
    """Ring-buffer capture of formatted log lines."""

    def test_captures_logged_lines(self) -> None:
        """Lines logged while installed appear in tail(), newline-joined."""
        handler = LogTailHandler()
        logger = logging.getLogger("test.run_journal.capture")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            logger.info("first line")
            logger.info("second line")
        finally:
            logger.removeHandler(handler)

        tail = handler.tail()
        assert tail is not None
        assert "first line" in tail
        assert "second line" in tail

    def test_empty_capture_returns_none(self) -> None:
        """tail() is None when nothing was logged (NULL in DB, not '')."""
        assert LogTailHandler().tail() is None

    def test_trims_to_byte_cap_from_the_front(self) -> None:
        """Old lines are dropped first once the byte cap is exceeded."""
        handler = LogTailHandler(max_bytes=200)
        logger = logging.getLogger("test.run_journal.trim")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            for i in range(50):
                logger.info("line-%03d xxxxxxxxxxxxxxxxxxxx", i)
        finally:
            logger.removeHandler(handler)

        tail = handler.tail()
        assert tail is not None
        assert len(tail.encode("utf-8")) <= 200
        assert "line-049" in tail, "most recent line must survive trimming"
        assert "line-000" not in tail, "oldest line must be trimmed"


# ---------------------------------------------------------------------------
# cli_step_journal
# ---------------------------------------------------------------------------


class TestCliStepJournal:
    """Journal wrapper for direct CLI step commands (dispatch, process, …)."""

    def test_success_records_row_with_output_tail(self) -> None:
        """A clean block yields one finalized row with the captured log tail."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            with cli_step_journal(_config_with_db(db_path), command="dispatch", dry_run=False):
                logging.getLogger("test.run_journal.body").info("dispatch body ran")

            row = _fetch_only_row(db_path)
            assert row["trigger"] == "cli"
            assert row["kind"] == "pipeline"
            assert row["command"] == "dispatch"
            assert row["dry_run"] == 0
            assert row["outcome"] == "success"
            assert row["ended_at"] is not None
            assert row["pid"] is not None
            assert row["output_tail"] is not None
            assert "dispatch body ran" in row["output_tail"]

    def test_exception_finalizes_error_and_reraises(self) -> None:
        """A raising block finalizes outcome='error' with the message, re-raised."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            with pytest.raises(RuntimeError, match="boom"):
                with cli_step_journal(_config_with_db(db_path), command="process", dry_run=True):
                    raise RuntimeError("boom")

            row = _fetch_only_row(db_path)
            assert row["outcome"] == "error"
            assert row["dry_run"] == 1
            assert "boom" in (row["error"] or "")

    def test_clean_typer_exit_is_success(self) -> None:
        """typer.Exit(0) is a normal CLI termination, not an error."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            with pytest.raises(typer.Exit):
                with cli_step_journal(_config_with_db(db_path), command="verify", dry_run=False):
                    raise typer.Exit(0)

            assert _fetch_only_row(db_path)["outcome"] == "success"

    def test_nonzero_typer_exit_is_error(self) -> None:
        """typer.Exit(1) finalizes outcome='error'."""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "library.db"
            _create_db(db_path)

            with pytest.raises(typer.Exit):
                with cli_step_journal(_config_with_db(db_path), command="verify", dry_run=False):
                    raise typer.Exit(1)

            assert _fetch_only_row(db_path)["outcome"] == "error"

    def test_fail_soft_on_unusable_db(self) -> None:
        """A missing/unwritable DB never breaks the wrapped command."""
        config = _config_with_db(Path("/nonexistent/dir/library.db"))
        ran = False
        with cli_step_journal(config, command="sort", dry_run=False):
            ran = True
        assert ran, "the body must run even when journaling is impossible"


# ---------------------------------------------------------------------------
# per_step_boundary Redis publisher
# ---------------------------------------------------------------------------


class TestPerStepBoundaryPublisher:
    """Step commands opt into event streaming like ``personalscraper run``."""

    def test_boundary_builds_and_closes_publisher_when_opted_in(self) -> None:
        """stream_events=True wires build_redis_publisher on the step bus and closes it."""
        from personalscraper import cli_helpers

        publisher = MagicMock()
        config = MagicMock()
        settings = MagicMock()
        app_context = MagicMock()
        with (
            patch.object(cli_helpers, "_build_app_context", return_value=app_context),
            patch.object(cli_helpers, "build_redis_publisher", return_value=publisher) as build_mock,
        ):
            with cli_helpers.per_step_boundary(config, settings, stream_events=True):
                build_mock.assert_called_once_with(app_context.event_bus, config.web)
                publisher.close.assert_not_called()
        publisher.close.assert_called_once()

    def test_boundary_defaults_to_no_publisher(self) -> None:
        """Non-step consumers (library-*, grab, seed, …) keep a publisher-free boundary.

        Regression contract: an unconditional publisher polluted the stdout of
        JSON-emitting CLI commands with fail-soft Redis warnings when Redis is
        absent (CI), breaking their output parsing.
        """
        from personalscraper import cli_helpers

        config = MagicMock()
        settings = MagicMock()
        app_context = MagicMock()
        with (
            patch.object(cli_helpers, "_build_app_context", return_value=app_context),
            patch.object(cli_helpers, "build_redis_publisher") as build_mock,
        ):
            with cli_helpers.per_step_boundary(config, settings):
                pass
        build_mock.assert_not_called()
