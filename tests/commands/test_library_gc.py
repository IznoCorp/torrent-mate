"""Regression tests for ``personalscraper library-gc`` CLI command (sub-phase 5.5 — SH-7).

Verifies:
- ``library-gc --help`` exits 0 (smoke test, existence proof).
- ``library-gc --dry-run`` counts rows without deleting, returns dry_run:true in JSON.
- ``library-gc`` (live) deletes rows older than the cutoff and reports count in JSON.
- ``--older-than-days`` cutoff is forwarded correctly.
- Missing ``indexer.db_path`` exits non-zero with a clear error.
"""

from __future__ import annotations

import json
import sqlite3
import time
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from personalscraper.cli import app

runner = CliRunner()

# ── patch targets ─────────────────────────────────────────────────────────────

_OPEN_DB = "personalscraper.indexer.db.open_db"
_APPLY_MIGRATIONS = "personalscraper.indexer.db.apply_migrations"


def _conn_mock(count: int = 5) -> MagicMock:
    """Return a minimal sqlite3.Connection stub pre-loaded with a row count.

    Args:
        count: Value returned by the COUNT(*) query in the GC command.

    Returns:
        MagicMock satisfying the open_db / apply_migrations / execute / commit / close
        contract expected by the library-gc implementation.
    """
    m = MagicMock()
    row_mock = MagicMock()
    row_mock.__getitem__ = lambda self, idx: count  # row[0] == count
    m.execute.return_value.fetchone.return_value = row_mock
    return m


# ── 1. Smoke / existence ──────────────────────────────────────────────────────


class TestLibraryGcHelp:
    """``library-gc --help`` must exist and exit 0."""

    def test_help_exits_zero(self) -> None:
        """``library-gc --help`` exits 0 — proves the command is registered."""
        result = runner.invoke(app, ["library-gc", "--help"])
        assert result.exit_code == 0, result.output

    def test_help_mentions_dry_run(self) -> None:
        """``--dry-run`` is documented in the help text."""
        result = runner.invoke(app, ["library-gc", "--help"])
        assert "--dry-run" in result.output

    def test_help_mentions_older_than_days(self) -> None:
        """``--older-than-days`` is documented in the help text."""
        result = runner.invoke(app, ["library-gc", "--help"])
        assert "--older-than-days" in result.output


# ── 2. --dry-run behaviour ────────────────────────────────────────────────────


class TestLibraryGcDryRun:
    """``library-gc --dry-run`` reports count without deleting anything."""

    def test_dry_run_exits_zero(self, test_config) -> None:
        """``--dry-run`` exits 0 when the DB is accessible."""
        conn_mock = _conn_mock(count=3)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output

    def test_dry_run_outputs_json_with_dry_run_true(self, test_config) -> None:
        """``--dry-run`` emits JSON with ``dry_run: true``."""
        conn_mock = _conn_mock(count=7)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None, f"No JSON line in output: {raw!r}"
        data = json.loads(json_line)
        assert data["dry_run"] is True

    def test_dry_run_reports_row_count(self, test_config) -> None:
        """``--dry-run`` reports ``rows_to_delete`` equal to the COUNT(*) result."""
        conn_mock = _conn_mock(count=42)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["rows_to_delete"] == 42

    def test_dry_run_does_not_delete(self, test_config) -> None:
        """``--dry-run`` must NOT execute a DELETE statement."""
        conn_mock = _conn_mock(count=5)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output
        # Verify no DELETE call was made among the execute() calls.
        calls_sql = [str(c) for c in conn_mock.execute.call_args_list]
        assert not any("DELETE" in s for s in calls_sql), "DELETE was called in dry-run mode"

    def test_dry_run_does_not_commit(self, test_config) -> None:
        """``--dry-run`` must NOT call ``conn.commit()`` — no DB writes."""
        conn_mock = _conn_mock(count=2)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output
        conn_mock.commit.assert_not_called()

    def test_dry_run_closes_connection(self, test_config) -> None:
        """``--dry-run`` closes the DB connection (finally block)."""
        conn_mock = _conn_mock(count=1)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output
        conn_mock.close.assert_called()


# ── 3. Live delete behaviour ──────────────────────────────────────────────────


class TestLibraryGcLiveDelete:
    """``library-gc`` (without --dry-run) deletes matching rows."""

    def test_live_exits_zero(self, test_config) -> None:
        """Live mode exits 0 on success."""
        conn_mock = _conn_mock(count=4)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code == 0, result.output

    def test_live_outputs_json_with_dry_run_false(self, test_config) -> None:
        """Live mode emits JSON with ``dry_run: false``."""
        conn_mock = _conn_mock(count=3)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        assert json_line is not None, f"No JSON line in output: {raw!r}"
        data = json.loads(json_line)
        assert data["dry_run"] is False

    def test_live_reports_rows_deleted(self, test_config) -> None:
        """Live mode reports ``rows_deleted`` equal to the COUNT(*) result."""
        conn_mock = _conn_mock(count=11)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["rows_deleted"] == 11

    def test_live_executes_delete(self, test_config) -> None:
        """Live mode issues a DELETE statement on the outbox table."""
        conn_mock = _conn_mock(count=6)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code == 0, result.output
        calls_sql = [str(c) for c in conn_mock.execute.call_args_list]
        assert any("DELETE" in s for s in calls_sql), "Expected a DELETE execute call in live mode"

    def test_live_commits(self, test_config) -> None:
        """Live mode commits the transaction after the DELETE."""
        conn_mock = _conn_mock(count=2)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code == 0, result.output
        conn_mock.commit.assert_called_once()

    def test_live_closes_connection(self, test_config) -> None:
        """Live mode closes the DB connection in the finally block."""
        conn_mock = _conn_mock(count=1)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code == 0, result.output
        conn_mock.close.assert_called()


# ── 4. --older-than-days forwarding ──────────────────────────────────────────


class TestLibraryGcOlderThanDays:
    """``--older-than-days`` is reflected in JSON output."""

    def test_older_than_days_appears_in_dry_run_output(self, test_config) -> None:
        """``--older-than-days 7`` is reflected as ``older_than_days: 7`` in JSON."""
        conn_mock = _conn_mock(count=0)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run", "--older-than-days", "7"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["older_than_days"] == 7

    def test_older_than_days_appears_in_live_output(self, test_config) -> None:
        """``--older-than-days 14`` is reflected as ``older_than_days: 14`` in live JSON."""
        conn_mock = _conn_mock(count=0)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--older-than-days", "14"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["older_than_days"] == 14

    def test_default_older_than_days_is_30(self, test_config) -> None:
        """The default ``--older-than-days`` is 30."""
        conn_mock = _conn_mock(count=0)
        with (
            patch(_OPEN_DB, return_value=conn_mock),
            patch(_APPLY_MIGRATIONS),
        ):
            result = runner.invoke(app, ["library-gc", "--dry-run"])
        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["older_than_days"] == 30


# ── 5. Missing db_path guard ──────────────────────────────────────────────────


class TestLibraryGcMissingDbPath:
    """``library-gc`` exits non-zero when ``indexer.db_path`` is None."""

    def test_missing_db_path_exits_nonzero(self, test_config) -> None:
        """When ``cfg.indexer.db_path`` is None the command exits with code 1."""
        cfg_no_db = test_config.model_copy(update={"indexer": test_config.indexer.model_copy(update={"db_path": None})})
        with patch("personalscraper.conf.loader.load_config", return_value=cfg_no_db):
            result = runner.invoke(app, ["library-gc"])
        assert result.exit_code != 0


# ── 6. Integration: real SQLite GC ───────────────────────────────────────────


class TestLibraryGcIntegration:
    """End-to-end test using a real in-memory SQLite DB (no external deps).

    Regression test for SH-7: verifies that ``library-gc`` actually removes
    the expected rows from ``index_outbox`` based on the cutoff timestamp.
    This test would FAIL if the DELETE logic or cutoff calculation were
    broken — it reproduces the exact scenario the GC command is meant to handle.
    """

    def _build_db(self, tmp_path) -> sqlite3.Connection:  # type: ignore[no-untyped-def]
        """Create a fully-migrated indexer DB and seed index_outbox test rows.

        Uses the real ``open_db`` + ``apply_migrations`` so the schema is
        identical to production — avoids the ``'table index_outbox already exists'``
        failure that occurs when a hand-crafted CREATE TABLE conflicts with
        migration 001_init.sql.

        Args:
            tmp_path: Pytest temporary directory for the SQLite file.

        Returns:
            Open sqlite3.Connection to the seeded database (caller must close).
        """
        from pathlib import Path as _Path  # noqa: PLC0415

        from personalscraper.core.event_bus import EventBus  # noqa: PLC0415
        from personalscraper.indexer import migrations as _migrations_pkg  # noqa: PLC0415
        from personalscraper.indexer.db import apply_migrations, open_db  # noqa: PLC0415

        db_file = tmp_path / "test_indexer.db"
        migrations_dir = _Path(_migrations_pkg.__file__).parent
        event_bus = EventBus()
        conn = open_db(db_file, event_bus=event_bus)
        apply_migrations(conn, migrations_dir)

        now = int(time.time())
        # Row 1: done, processed 60 days ago → should be GC-ed with --older-than-days 30
        conn.execute(
            "INSERT INTO index_outbox(source,op,payload_json,created_at,processed_at,status)"
            " VALUES ('dispatch','move','{}',?,?,'done')",
            (now - 60 * 86400, now - 60 * 86400),
        )
        # Row 2: done, processed 1 day ago → should NOT be GC-ed with --older-than-days 30
        conn.execute(
            "INSERT INTO index_outbox(source,op,payload_json,created_at,processed_at,status)"
            " VALUES ('dispatch','move','{}',?,?,'done')",
            (now - 86400, now - 86400),
        )
        # Row 3: pending → must NEVER be touched
        conn.execute(
            "INSERT INTO index_outbox(source,op,payload_json,created_at,processed_at,status)"
            " VALUES ('scraper','nfo_write','{}',?,NULL,'pending')",
            (now - 60 * 86400,),
        )
        conn.commit()
        return conn

    def test_dry_run_counts_without_deleting(self, tmp_path, test_config) -> None:
        """``--dry-run`` counts 1 row (the 60-day-old done row) without deleting.

        Regression: without --dry-run guard, the DELETE would fire and remove
        the row. This test confirms the guard is respected.
        """
        db_file = tmp_path / "test_indexer.db"
        conn = self._build_db(tmp_path)
        conn.close()

        cfg_with_db = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )

        with patch("personalscraper.conf.loader.load_config", return_value=cfg_with_db):
            result = runner.invoke(app, ["library-gc", "--dry-run", "--older-than-days", "30"])

        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["dry_run"] is True
        assert data["rows_to_delete"] == 1, f"Expected 1 row to delete, got: {data}"

        # Verify nothing was actually deleted.
        conn2 = sqlite3.connect(str(db_file))
        total = conn2.execute("SELECT COUNT(*) FROM index_outbox").fetchone()[0]
        conn2.close()
        assert total == 3, "dry-run must not delete any rows"

    def test_live_deletes_only_old_done_rows(self, tmp_path, test_config) -> None:
        """Live GC deletes the 60-day-old done row and leaves pending + recent rows intact.

        Regression: if the WHERE clause missed status='done', the pending row (id=3)
        would also be deleted — this test pins that only done rows older than the
        cutoff are removed.
        """
        db_file = tmp_path / "test_indexer.db"
        conn = self._build_db(tmp_path)
        conn.close()

        cfg_with_db = test_config.model_copy(
            update={"indexer": test_config.indexer.model_copy(update={"db_path": str(db_file)})}
        )

        with patch("personalscraper.conf.loader.load_config", return_value=cfg_with_db):
            result = runner.invoke(app, ["library-gc", "--older-than-days", "30"])

        assert result.exit_code == 0, result.output
        raw = result.output.strip()
        json_line = next((ln for ln in raw.splitlines() if ln.strip().startswith("{")), None)
        data = json.loads(json_line)
        assert data["dry_run"] is False
        assert data["rows_deleted"] == 1, f"Expected 1 row deleted, got: {data}"

        # Verify that rows 2 (recent done) and 3 (pending) still exist.
        conn2 = sqlite3.connect(str(db_file))
        remaining_ids = {r[0] for r in conn2.execute("SELECT id FROM index_outbox").fetchall()}
        conn2.close()
        assert 2 in remaining_ids, "Recent done row (id=2) must not be deleted"
        assert 3 in remaining_ids, "Pending row (id=3) must never be deleted"
        assert 1 not in remaining_ids, "Old done row (id=1) must have been deleted"
