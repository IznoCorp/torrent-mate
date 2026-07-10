"""Unit tests for :class:`PipelineRunWriter`.

Covers the four scenarios required by DESIGN §3.2:
- ``insert`` → row present with outcome ``'running'`` and ``steps_json="[]"``.
- ``update_step`` twice → ``steps_json`` has 2 entries in insertion order.
- ``finalize`` → ``ended_at`` set and ``outcome`` updated to ``'success'``.
- Fail-soft: a broken DB path or dropped table never raises — the method
  logs a warning and returns.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from personalscraper.core.sqlite._pragmas import apply_pragmas
from personalscraper.pipeline_history import PipelineRunWriter

# ---------------------------------------------------------------------------
# Helpers
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
)
"""


def _create_db(db_path: Path) -> None:
    """Create an in-memory or on-disk SQLite DB with the pipeline_run table."""
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPipelineRunWriterInsert:
    """``insert()`` tests."""

    def test_insert_creates_row_with_running_outcome(self, tmp_path: Path) -> None:
        """After ``insert()`` the row exists with ``outcome='running'``."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)

        writer.insert("uid-1", trigger="cli", dry_run=False, pid=1234)

        row = _select_row(db_path, "uid-1")
        assert row is not None
        assert row["run_uid"] == "uid-1"
        assert row["trigger"] == "cli"
        assert row["dry_run"] == 0
        assert row["outcome"] == "running"
        assert row["steps_json"] == "[]"
        assert row["pid"] == 1234
        assert row["started_at"] > 0
        assert row["ended_at"] is None

    def test_insert_dry_run_sets_flag(self, tmp_path: Path) -> None:
        """``dry_run=True`` → ``dry_run=1`` in the row."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)

        writer.insert("uid-dr", trigger="web", dry_run=True, pid=5678)

        row = _select_row(db_path, "uid-dr")
        assert row is not None
        assert row["dry_run"] == 1


class TestPipelineRunWriterUpdateStep:
    """``update_step()`` tests."""

    def test_update_step_appends_single_entry(self, tmp_path: Path) -> None:
        """One ``update_step()`` call → ``steps_json`` has 1 entry."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-2", trigger="cli", dry_run=False, pid=1)

        writer.update_step("uid-2", "ingest", 100.0, 101.5, "success")

        row = _select_row(db_path, "uid-2")
        assert row is not None
        steps = json.loads(row["steps_json"])
        assert len(steps) == 1
        assert steps[0] == {
            "name": "ingest",
            "started_at": 100.0,
            "ended_at": 101.5,
            "status": "success",
        }

    def test_update_step_twice_preserves_order(self, tmp_path: Path) -> None:
        """Two ``update_step()`` calls maintain insertion order."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-3", trigger="cli", dry_run=False, pid=1)

        writer.update_step("uid-3", "ingest", 100.0, 101.0, "success")
        writer.update_step("uid-3", "sort", 101.0, 102.0, "success")

        row = _select_row(db_path, "uid-3")
        assert row is not None
        steps = json.loads(row["steps_json"])
        assert len(steps) == 2
        assert steps[0]["name"] == "ingest"
        assert steps[1]["name"] == "sort"

    def test_update_step_unknown_run_uid_does_not_raise(self, tmp_path: Path) -> None:
        """Calling ``update_step`` on a non-existent ``run_uid`` logs and returns."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)

        # Must not raise.
        writer.update_step("nonexistent", "ingest", 100.0, 101.0, "success")

    def test_update_step_status_error(self, tmp_path: Path) -> None:
        """``status='error'`` is recorded correctly."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-err-step", trigger="cli", dry_run=False, pid=1)

        writer.update_step("uid-err-step", "scrape", 200.0, 200.1, "error")

        row = _select_row(db_path, "uid-err-step")
        steps = json.loads(row["steps_json"])
        assert steps[0]["status"] == "error"


class TestPipelineRunWriterStepSummary:
    """webui-ux Phase 2.2 — StepReport summary persistence in ``steps_json``."""

    def test_update_step_persists_summary_counts(self, tmp_path: Path) -> None:
        """Summary kwargs are folded into the ``steps_json`` entry."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-sum", trigger="cli", dry_run=False, pid=1)

        writer.update_step(
            "uid-sum",
            "scrape",
            100.0,
            105.0,
            "success",
            success_count=3,
            skip_count=1,
            error_count=0,
            unmatched_count=2,
            counts={"downloaded": 3, "bot_detected": 1},
        )

        row = _select_row(db_path, "uid-sum")
        assert row is not None
        steps = json.loads(row["steps_json"])
        assert steps[0]["success_count"] == 3
        assert steps[0]["skip_count"] == 1
        assert steps[0]["error_count"] == 0
        assert steps[0]["unmatched_count"] == 2
        assert steps[0]["counts"] == {"downloaded": 3, "bot_detected": 1}

    def test_update_step_without_summary_omits_count_keys(self, tmp_path: Path) -> None:
        """A timing-only call keeps the exact legacy entry shape (no count keys)."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-legacy", trigger="cli", dry_run=False, pid=1)

        writer.update_step("uid-legacy", "ingest", 100.0, 101.0, "success")

        row = _select_row(db_path, "uid-legacy")
        assert row is not None
        steps = json.loads(row["steps_json"])
        assert steps[0] == {
            "name": "ingest",
            "started_at": 100.0,
            "ended_at": 101.0,
            "status": "success",
        }

    def test_update_step_empty_counts_omitted(self, tmp_path: Path) -> None:
        """An empty ``counts`` dict is omitted; scalar zeros are still stored."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-empty", trigger="cli", dry_run=False, pid=1)

        writer.update_step(
            "uid-empty",
            "sort",
            100.0,
            100.5,
            "success",
            success_count=0,
            skip_count=0,
            error_count=0,
            unmatched_count=0,
            counts={},
        )

        row = _select_row(db_path, "uid-empty")
        assert row is not None
        steps = json.loads(row["steps_json"])
        assert "counts" not in steps[0]
        assert steps[0]["success_count"] == 0
        assert steps[0]["skip_count"] == 0
        assert steps[0]["error_count"] == 0
        assert steps[0]["unmatched_count"] == 0


class TestPipelineRunWriterFinalize:
    """``finalize()`` tests."""

    def test_finalize_sets_ended_at_and_outcome(self, tmp_path: Path) -> None:
        """After ``finalize()`` the row has ``ended_at`` and ``outcome``."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-4", trigger="cli", dry_run=False, pid=1)

        writer.finalize("uid-4", "success")

        row = _select_row(db_path, "uid-4")
        assert row is not None
        assert row["outcome"] == "success"
        assert row["ended_at"] is not None
        assert row["ended_at"] > 0

    def test_finalize_with_error(self, tmp_path: Path) -> None:
        """``finalize`` with an error message stores it."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-5", trigger="cli", dry_run=False, pid=1)

        writer.finalize("uid-5", "error", error="Scrape step failed: TMDB timeout")

        row = _select_row(db_path, "uid-5")
        assert row["outcome"] == "error"
        assert row["error"] == "Scrape step failed: TMDB timeout"
        assert row["ended_at"] is not None

    def test_finalize_killed_outcome(self, tmp_path: Path) -> None:
        """``finalize`` with ``outcome='killed'``."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-6", trigger="web", dry_run=False, pid=1)

        writer.finalize("uid-6", "killed")

        row = _select_row(db_path, "uid-6")
        assert row["outcome"] == "killed"


class TestPipelineRunWriterFailSoft:
    """Fail-soft tests — the writer must never raise."""

    def test_insert_bad_db_path_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a non-existent directory does not raise."""
        writer = PipelineRunWriter(tmp_path / "nonexistent" / "library.db")
        # Must not raise.
        writer.insert("uid-fs1", trigger="cli", dry_run=False, pid=1)

    def test_insert_dropped_table_does_not_raise(self, tmp_path: Path) -> None:
        """Dropping the table before insert does not raise."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        # Drop the table to simulate schema mismatch.
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        apply_pragmas(conn)
        conn.execute("DROP TABLE pipeline_run")
        conn.commit()
        conn.close()

        writer = PipelineRunWriter(db_path)
        # Must not raise.
        writer.insert("uid-fs2", trigger="cli", dry_run=False, pid=1)

    def test_update_step_bad_db_path_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a non-existent directory does not raise."""
        writer = PipelineRunWriter(tmp_path / "nonexistent" / "library.db")
        # Must not raise.
        writer.update_step("uid-fs3", "ingest", 100.0, 101.0, "success")

    def test_finalize_bad_db_path_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a non-existent directory does not raise."""
        writer = PipelineRunWriter(tmp_path / "nonexistent" / "library.db")
        # Must not raise.
        writer.finalize("uid-fs4", "success")

    def test_full_lifecycle_then_drop_table_finalize_does_not_raise(self, tmp_path: Path) -> None:
        """A full insert→update→finalize cycle, but drop the table before finalize."""
        db_path = tmp_path / "library.db"
        _create_db(db_path)
        writer = PipelineRunWriter(db_path)
        writer.insert("uid-fs5", trigger="cli", dry_run=False, pid=1)
        writer.update_step("uid-fs5", "ingest", 100.0, 101.0, "success")

        # Drop the table after the update_step to test finalize resilience.
        conn = sqlite3.connect(str(db_path), isolation_level=None)
        apply_pragmas(conn)
        conn.execute("DROP TABLE pipeline_run")
        conn.commit()
        conn.close()

        # Must not raise.
        writer.finalize("uid-fs5", "success")

    def test_insert_on_path_that_is_a_file_not_a_db_does_not_raise(self, tmp_path: Path) -> None:
        """Pointing at a regular file that is not a SQLite DB does not raise."""
        not_a_db = tmp_path / "not_a_db.txt"
        not_a_db.write_text("hello")
        writer = PipelineRunWriter(not_a_db)
        # Must not raise (sqlite3 will complain but we catch it).
        writer.insert("uid-fs6", trigger="cli", dry_run=False, pid=1)
