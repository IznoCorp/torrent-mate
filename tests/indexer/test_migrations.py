"""Unit tests for personalscraper.indexer.db.apply_migrations.

Covers:
- Applying migration 001 to a fresh DB.
- Idempotence (second apply is a no-op).
- Chain-replay equivalence: Path A (fixture via executescript) == Path B (apply_migrations).
- Failure rollback: malformed script triggers IndexerMigrationError and restores DB state.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.indexer.db import IndexerMigrationError, apply_migrations, open_db

# ---------------------------------------------------------------------------
# Paths to real migration artefacts
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"
FIXTURES_DIR = Path(__file__).parent / "migration_fixtures"

# Expected tables created by migration 001.
_EXPECTED_TABLES_V1 = {
    "disk",
    "path",
    "media_item",
    "item_attribute",
    "season",
    "episode",
    "media_release",
    "media_file",
    "media_stream",
    "item_issue",
    "index_outbox",
    "pending_op",
    "repair_queue",
    "scan_run",
    "scan_event",
    "deleted_item",
    "schema_version",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def dump_schema(conn: sqlite3.Connection) -> str:
    """Return a deterministic string representation of the database schema.

    Queries ``sqlite_master`` for all objects (tables, indexes, triggers,
    views), sorts the results, and joins them into a single string.  Used for
    structural equality assertions between two databases that should have
    arrived at the same schema via different paths.

    Args:
        conn: An open :class:`sqlite3.Connection`.

    Returns:
        A sorted, newline-joined string of ``(type, name, sql)`` rows from
        ``sqlite_master``, excluding auto-generated ``sqlite_*`` internals.
    """
    rows = conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
    ).fetchall()
    return "\n".join(f"{r[0]}|{r[1]}|{r[2]}" for r in rows)


def _table_names(conn: sqlite3.Connection) -> set[str]:
    """Return the set of user table names in *conn*.

    Args:
        conn: An open :class:`sqlite3.Connection`.

    Returns:
        A set of table name strings (excludes ``sqlite_*`` system tables).
    """
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    return {r[0] for r in rows}


def _user_version(conn: sqlite3.Connection) -> int:
    """Return the current ``PRAGMA user_version`` of *conn*.

    Args:
        conn: An open :class:`sqlite3.Connection`.

    Returns:
        The integer schema version stored in the DB header.
    """
    return conn.execute("PRAGMA user_version").fetchone()[0]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Test: apply 001 to fresh DB
# ---------------------------------------------------------------------------


class TestApplyMigrations001:
    """apply_migrations applies migration 001 to a fresh database correctly."""

    def test_user_version_is_1(self, tmp_path: Path) -> None:
        """After applying 001, PRAGMA user_version equals 1."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == 1

    def test_all_17_tables_present(self, tmp_path: Path) -> None:
        """After applying 001, all 17 expected tables exist."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _table_names(conn) == _EXPECTED_TABLES_V1

    def test_schema_version_row_exists(self, tmp_path: Path) -> None:
        """After applying 001, schema_version contains version=1."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, MIGRATIONS_DIR)
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        assert row is not None
        assert row[0] == 1


# ---------------------------------------------------------------------------
# Test: idempotence
# ---------------------------------------------------------------------------


class TestApplyMigrationsIdempotence:
    """Calling apply_migrations twice is a no-op on the second call."""

    def test_second_call_does_not_change_version(self, tmp_path: Path) -> None:
        """user_version remains 1 after a second apply_migrations call."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == 1
        # Second call must be a no-op.
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == 1

    def test_second_call_does_not_change_table_set(self, tmp_path: Path) -> None:
        """Table set is identical after the second apply_migrations call."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, MIGRATIONS_DIR)
        tables_after_first = _table_names(conn)
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _table_names(conn) == tables_after_first


# ---------------------------------------------------------------------------
# Test: chain-replay equivalence (DESIGN §15.5.1)
# ---------------------------------------------------------------------------


class TestChainReplayEquivalence:
    """Schema produced by direct fixture load equals schema from apply_migrations."""

    def test_chain_replay_matches_v1_fixture(self, tmp_path: Path) -> None:
        """Path A (v1.sql via executescript) and Path B (apply_migrations) yield identical schemas.

        Path A: load ``tests/indexer/migration_fixtures/v1.sql`` directly into an
        empty in-memory DB via ``executescript``.

        Path B: open a fresh file-based DB, call ``apply_migrations`` to run
        ``001_init.sql`` through the normal migration path.

        The resulting ``dump_schema()`` strings must be equal.  This guards
        against the case where someone edits ``001_init.sql`` without updating
        the fixture (or vice-versa), and also validates that the migration
        machinery does not corrupt the schema.
        """
        fixture_sql = (FIXTURES_DIR / "v1.sql").read_text(encoding="utf-8")

        # Path A: direct executescript on in-memory DB.
        db_a = sqlite3.connect(":memory:")
        db_a.executescript(fixture_sql)

        # Path B: apply_migrations on a fresh file-based DB.
        db_path_b = tmp_path / "b.db"
        db_b = open_db(db_path_b)
        apply_migrations(db_b, MIGRATIONS_DIR)

        schema_a = dump_schema(db_a)
        schema_b = dump_schema(db_b)

        assert schema_a == schema_b, (
            "Schema mismatch between v1.sql fixture and apply_migrations output.\n"
            f"--- v1.sql (Path A) ---\n{schema_a}\n"
            f"--- apply_migrations (Path B) ---\n{schema_b}"
        )


# ---------------------------------------------------------------------------
# Test: failure rollback
# ---------------------------------------------------------------------------


class TestApplyMigrationsFailureRollback:
    """A failing migration script triggers IndexerMigrationError and restores DB state.

    Test setup:
    - Apply the real ``001_init.sql`` first (via MIGRATIONS_DIR) to reach version=1.
    - Build a ``mig_dir`` with two scripts: ``002_noop.sql`` (valid) and ``999_bad.sql``
      (malformed).  Both are processed in a single ``apply_migrations(conn, mig_dir)``
      call: ``002`` succeeds (version → 2, ``noop`` table created), then the snapshot
      is taken just before ``999``, ``999`` fails, the DB is restored from that snapshot
      (preserving ``noop``), and ``IndexerMigrationError(999)`` is raised.
    """

    def _setup_db_and_mig_dir(self, tmp_path: Path) -> tuple[Path, sqlite3.Connection, Path]:
        """Create a seeded DB at version=1 and a mig_dir with 002_noop + 999_bad.

        Args:
            tmp_path: Pytest-provided temporary directory.

        Returns:
            A tuple of ``(db_path, conn, mig_dir)`` ready for the rollback scenario.
            ``conn`` is the open connection after applying 001.
            ``mig_dir`` contains both ``002_noop.sql`` and ``999_bad.sql``.
        """
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        # Valid migration: creates `noop` table at version 2.
        (mig_dir / "002_noop.sql").write_text(
            "CREATE TABLE noop (id INTEGER PRIMARY KEY);\nPRAGMA user_version = 2;\n",
            encoding="utf-8",
        )
        # Malformed migration: intentionally broken SQL at version 999.
        (mig_dir / "999_bad.sql").write_text(
            "CREATE TABLE foo (BAD SQL;",
            encoding="utf-8",
        )
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path)
        apply_migrations(conn, MIGRATIONS_DIR)  # applies 001; user_version=1
        return db_path, conn, mig_dir

    def test_bad_migration_raises_indexer_migration_error(self, tmp_path: Path) -> None:
        """IndexerMigrationError is raised with version=999 when migration 999 is malformed.

        In a single ``apply_migrations`` call on ``mig_dir`` (which contains both
        ``002_noop.sql`` and ``999_bad.sql``):
        - ``002`` is applied successfully (version → 2).
        - ``999`` fails → ``IndexerMigrationError(version=999)`` is raised.
        """
        db_path, conn, mig_dir = self._setup_db_and_mig_dir(tmp_path)

        # Single call: 002 succeeds, 999 fails → IndexerMigrationError(999).
        with pytest.raises(IndexerMigrationError) as exc_info:
            apply_migrations(conn, mig_dir)

        assert exc_info.value.version == 999

    def test_backup_file_created_before_failing_migration(self, tmp_path: Path) -> None:
        """A .pre-migration-999.bak snapshot is created before the failing migration is attempted."""
        db_path, conn, mig_dir = self._setup_db_and_mig_dir(tmp_path)

        with pytest.raises(IndexerMigrationError):
            apply_migrations(conn, mig_dir)

        bak_path = db_path.parent / f"{db_path.name}.pre-migration-999.bak"
        assert bak_path.exists(), f"Expected backup at {bak_path} but it does not exist"

    def test_db_restored_no_foo_table_after_rollback(self, tmp_path: Path) -> None:
        """After rollback, the ``foo`` table from the malformed migration does not exist.

        The snapshot for version 999 is taken after version 2 has been applied (``noop``
        table exists).  After rollback, the DB is at the snapshot state: ``noop`` present,
        ``foo`` absent.
        """
        db_path, conn, mig_dir = self._setup_db_and_mig_dir(tmp_path)

        with pytest.raises(IndexerMigrationError):
            apply_migrations(conn, mig_dir)

        # Re-open the DB (connection was closed during rollback) and verify state.
        conn2 = open_db(db_path)
        tables = _table_names(conn2)
        assert "foo" not in tables, "foo table should not exist after rollback"
        # noop was added by the successful 002 migration and should still be present
        # in the restored snapshot (which was taken just before 999).
        assert "noop" in tables, "noop table from migration 002 should be preserved in snapshot"
