"""Unit tests for migration 012 — pipeline_run maintenance columns.

Validates the additive migration that extends ``pipeline_run`` with ``kind``,
``command``, ``options_json``, and ``output_tail`` columns (S3 maintenance
dashboard feature).

Covers:
- Upgrading from 011 → 012 preserves existing rows with ``kind='pipeline'`` default.
- Inserting a maintenance row with all four new columns read back correctly.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parent.parent.parent.parent / "personalscraper" / "indexer" / "migrations"

# Migration files to include when building a "through-011" directory
_MIGRATION_NAMES_001_011 = sorted(p.name for p in MIGRATIONS_DIR.glob("*.sql") if int(p.name.split("_", 1)[0]) <= 11)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_through_011(conn: sqlite3.Connection) -> None:
    """Apply all migrations 001–011 to *conn*, excluding 012.

    Copies the migration files into a temporary directory so that
    ``apply_migrations`` only sees and applies 001–011.

    Args:
        conn: An open :class:`sqlite3.Connection` (in-memory or file-based).
    """
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        for name in _MIGRATION_NAMES_001_011:
            shutil.copy2(MIGRATIONS_DIR / name, tmp_dir / name)
        apply_migrations(conn, tmp_dir)


def _apply_012(conn: sqlite3.Connection) -> None:
    """Apply migration 012 to *conn* via ``executescript``.

    Args:
        conn: An open :class:`sqlite3.Connection` already upgraded to schema
            version 11.
    """
    sql = (MIGRATIONS_DIR / "012_pipeline_run_maintenance.sql").read_text(encoding="utf-8")
    conn.executescript(sql)


def _insert_s2_pipeline_row(conn: sqlite3.Connection) -> int:
    """Insert a minimal pipeline_run row in the 011 schema shape.

    The row does NOT include the new 012 columns (kind, command, options_json,
    output_tail) — the migration must backfill these with defaults.

    Args:
        conn: An open :class:`sqlite3.Connection` at schema version 11.

    Returns:
        The rowid of the inserted row.
    """
    cursor = conn.execute(
        "INSERT INTO pipeline_run (run_uid, trigger, dry_run, started_at) VALUES ('test-uid-001', 'cli', 0, 100.5)"
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def _user_version(conn: sqlite3.Connection) -> int:
    """Return the current ``PRAGMA user_version`` of *conn*.

    Args:
        conn: An open :class:`sqlite3.Connection`.

    Returns:
        The integer schema version stored in the DB header.
    """
    return conn.execute("PRAGMA user_version").fetchone()[0]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMigration012Upgrade:
    """Migration 012 upgrades a 011 DB correctly."""

    def test_user_version_is_12_after_migration(self) -> None:
        """After applying 001–011 then 012, PRAGMA user_version is 12."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_through_011(conn)
        assert _user_version(conn) == 11

        _apply_012(conn)
        assert _user_version(conn) == 12
        conn.close()

    def test_existing_row_gets_kind_pipeline_default(self) -> None:
        """An 011-row inserted before 012 gets ``kind='pipeline'`` after upgrade.

        This is the core invariant: the migration is additive and must not lose
        existing data.  The ``DEFAULT 'pipeline'`` clause ensures every pre-existing
        pipeline run row is correctly classified.
        """
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_through_011(conn)

        row_id = _insert_s2_pipeline_row(conn)
        conn.commit()

        _apply_012(conn)

        row = conn.execute(
            "SELECT kind, command, options_json, output_tail FROM pipeline_run WHERE id = ?",
            (row_id,),
        ).fetchone()
        assert row is not None

        # Default values on the pre-existing row.
        assert row[0] == "pipeline", f"expected kind='pipeline', got {row[0]!r}"
        assert row[1] is None  # command
        assert row[2] is None  # options_json
        assert row[3] is None  # output_tail
        conn.close()

    def test_insert_maintenance_row_with_new_columns(self) -> None:
        """After 012, a maintenance row with all new columns round-trips correctly."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_through_011(conn)
        _apply_012(conn)

        cursor = conn.execute(
            "INSERT INTO pipeline_run "
            "(run_uid, trigger, dry_run, started_at, ended_at, outcome, kind, command, options_json, output_tail) "
            "VALUES ('maint-uid-001', 'web', 0, 200.0, 210.0, 'success', "
            "'maintenance', 'library-doctor', '{\"fix\":true}', 'No issues found.')"
        )
        row_id = cursor.lastrowid

        row = conn.execute(
            "SELECT run_uid, trigger, kind, command, options_json, output_tail, outcome FROM pipeline_run WHERE id = ?",
            (row_id,),
        ).fetchone()
        assert row is not None
        assert row[0] == "maint-uid-001"
        assert row[1] == "web"
        assert row[2] == "maintenance"
        assert row[3] == "library-doctor"
        assert row[4] == '{"fix":true}'
        assert row[5] == "No issues found."
        assert row[6] == "success"
        conn.close()

    def test_schema_version_row_recorded(self) -> None:
        """Migration 012 records its version 12 in the schema_version audit table."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_through_011(conn)
        _apply_012(conn)

        versions = [r[0] for r in conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()]
        assert 12 in versions, f"schema_version must contain 12, got {versions}"
        conn.close()

    def test_kind_index_exists(self) -> None:
        """Migration 012 creates the idx_pipeline_run_kind index."""
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys=ON")
        _apply_through_011(conn)
        _apply_012(conn)

        indexes = [
            r[1]
            for r in conn.execute(
                "SELECT type, name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pipeline_run%'"
            ).fetchall()
        ]
        assert "idx_pipeline_run_kind" in indexes, f"Expected idx_pipeline_run_kind in {indexes}"
        conn.close()
