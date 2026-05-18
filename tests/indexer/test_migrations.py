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

from personalscraper.core.event_bus import EventBus
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
    """apply_migrations applies all migrations to a fresh database correctly.

    With migrations 001-004 present, the final schema version is 4.
    """

    def test_user_version_matches_latest(self, tmp_path: Path) -> None:
        """After applying every migration, PRAGMA user_version equals the latest version (4)."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == 4

    def test_all_17_tables_present(self, tmp_path: Path) -> None:
        """After applying all migrations, all 17 expected tables exist."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _table_names(conn) == _EXPECTED_TABLES_V1

    def test_schema_version_row_exists(self, tmp_path: Path) -> None:
        """After applying all migrations, schema_version contains every version 1..N.

        Specifically, every migration script must record its version in the
        ``schema_version`` audit table — this is the contract that lets
        ``library-status`` and downgrade tooling reason about the migration
        chain. A migration that bumps ``PRAGMA user_version`` without
        inserting into ``schema_version`` is a bug (see fc7d16c).
        """
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        assert rows is not None
        versions = [r[0] for r in rows]
        # Every migration in the chain must register its version.
        for v in (1, 2, 3, 4):
            assert v in versions, f"migration {v} did not insert into schema_version"


# ---------------------------------------------------------------------------
# Test: idempotence
# ---------------------------------------------------------------------------


class TestApplyMigrationsIdempotence:
    """Calling apply_migrations twice is a no-op on the second call."""

    def test_second_call_does_not_change_version(self, tmp_path: Path) -> None:
        """user_version remains at the latest version after a second apply_migrations call."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)
        version_after_first = _user_version(conn)
        assert version_after_first == 5
        # Second call must be a no-op.
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == version_after_first

    def test_second_call_does_not_change_table_set(self, tmp_path: Path) -> None:
        """Table set is identical after the second apply_migrations call."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)
        tables_after_first = _table_names(conn)
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _table_names(conn) == tables_after_first


class TestMigration003RepairQueueDedup:
    """Migration 003 collapses duplicate pending repair rows + adds UNIQUE index.

    Validates the data-mutation path of the migration on a DB that already
    contains duplicates — guards against future edits that accidentally
    drop the collapse step or the DELETE filter.
    """

    def _apply_through_002(self, conn: sqlite3.Connection) -> None:
        """Run migrations 001 + 002 only (skip 003) so we can seed duplicates."""
        for name in ("001_init.sql", "002_nullable_release_id_oshash.sql"):
            sql = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            conn.executescript(sql)

    def _apply_003(self, conn: sqlite3.Connection) -> None:
        """Run migration 003 (the dedup migration under test)."""
        sql = (MIGRATIONS_DIR / "003_repair_queue_pending_dedup.sql").read_text(encoding="utf-8")
        conn.executescript(sql)

    def test_collapses_duplicates_keeps_oldest(self, tmp_path: Path) -> None:
        """Two pending rows for the same (scope, scope_id) collapse to the oldest."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        self._apply_through_002(conn)

        # Seed three pending duplicates (same scope+scope_id, different enqueued_at)
        # plus one terminal 'done' row that should survive untouched.
        conn.executemany(
            "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at, status) VALUES (?, ?, ?, ?, ?)",
            [
                ("file", 42, "drift_run_1", 100, "pending"),
                ("file", 42, "drift_run_2", 200, "pending"),
                ("file", 42, "drift_run_3", 300, "pending"),
                ("file", 42, "old_completed", 50, "done"),
            ],
        )
        conn.commit()

        self._apply_003(conn)

        # One pending row survives — the oldest.
        rows = conn.execute(
            "SELECT id, reason, enqueued_at FROM repair_queue WHERE scope='file' AND scope_id=42 AND status='pending'"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0][1] == "drift_run_1"
        assert rows[0][2] == 100

        # The terminal 'done' row is untouched.
        done_rows = conn.execute(
            "SELECT id FROM repair_queue WHERE scope='file' AND scope_id=42 AND status='done'"
        ).fetchall()
        assert len(done_rows) == 1

    def test_subsequent_insert_or_ignore_dedups(self, tmp_path: Path) -> None:
        """After 003, ``INSERT OR IGNORE`` skips a duplicate pending row."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at, status) "
            "VALUES ('item', 7, 'first', 100, 'pending')"
        )
        cursor = conn.execute(
            "INSERT OR IGNORE INTO repair_queue (scope, scope_id, reason, enqueued_at, status) "
            "VALUES ('item', 7, 'second', 200, 'pending')"
        )
        # Second INSERT must be a no-op.
        assert cursor.rowcount == 0

        rows = conn.execute("SELECT reason FROM repair_queue WHERE scope='item' AND scope_id=7").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "first"

    def test_terminal_row_does_not_block_new_pending(self, tmp_path: Path) -> None:
        """A 'done'/'failed' row does NOT block a fresh pending row for the same target."""
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at, status) "
            "VALUES ('file', 9, 'first_run', 100, 'done')"
        )
        cursor = conn.execute(
            "INSERT OR IGNORE INTO repair_queue (scope, scope_id, reason, enqueued_at, status) "
            "VALUES ('file', 9, 'second_run', 200, 'pending')"
        )
        # Insert succeeds — partial UNIQUE INDEX is keyed only on pending rows.
        assert cursor.rowcount == 1

    def test_idempotent_re_apply_via_apply_migrations(self, tmp_path: Path) -> None:
        """Running apply_migrations twice is a no-op for migration 003 specifically.

        The migration uses ``CREATE UNIQUE INDEX IF NOT EXISTS`` so even if an
        outer caller bypassed the user_version skip-if-applied logic, the
        script itself would not raise on re-execution.
        """
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)
        # Manually re-execute 003 — must not raise even though the index exists.
        self._apply_003(conn)
        # Verify the index still exists exactly once.
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_repair_pending_dedup'"
        ).fetchall()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Test: chain-replay equivalence (DESIGN §15.5.1)
# ---------------------------------------------------------------------------


class TestChainReplayEquivalence:
    """Schema produced by direct fixture load equals schema from apply_migrations.

    With migration 002 present, the canonical schema is v2: applying 001 + 002
    via ``apply_migrations`` must match loading ``v1.sql`` then ``002_nullable_release_id_oshash.sql``
    directly via ``executescript``.
    """

    def test_chain_replay_matches_v1_plus_002_fixture(self, tmp_path: Path) -> None:
        """Path A (v1.sql + 002.sql + 003.sql via executescript) and Path B (apply_migrations) yield identical schemas.

        Path A: load ``v1.sql`` then every published migration script after
        the v1 fixture directly into an in-memory DB via ``executescript``.

        Path B: open a fresh file-based DB, call ``apply_migrations`` to run
        every script in ``MIGRATIONS_DIR`` through the normal migration path.

        The resulting ``dump_schema()`` strings must be equal.  This guards
        against the case where someone edits a migration script without the other
        path reflecting it, and validates that the migration machinery does not
        corrupt the schema.
        """
        v1_sql = (FIXTURES_DIR / "v1.sql").read_text(encoding="utf-8")
        # Apply every migration with version >= 2 in numeric order so the
        # fixture-replay path mirrors the apply_migrations chain.  v1.sql is
        # the canonical version-1 schema and stands in for 001_init.sql.
        post_v1_scripts = sorted(
            (p for p in MIGRATIONS_DIR.glob("*.sql") if p.name != "001_init.sql"),
            key=lambda p: int(p.name.split("_", 1)[0]),
        )

        # Path A: direct executescript on in-memory DB (v1 fixture + every later migration).
        db_a = sqlite3.connect(":memory:")
        db_a.executescript(v1_sql)
        for script in post_v1_scripts:
            db_a.executescript(script.read_text(encoding="utf-8"))

        # Path B: apply_migrations on a fresh file-based DB.
        db_path_b = tmp_path / "b.db"
        db_b = open_db(db_path_b, event_bus=EventBus())
        apply_migrations(db_b, MIGRATIONS_DIR)

        schema_a = dump_schema(db_a)
        schema_b = dump_schema(db_b)

        assert schema_a == schema_b, (
            "Schema mismatch between v1 fixture + post-v1 scripts and apply_migrations output.\n"
            f"--- fixture-replay (Path A) ---\n{schema_a}\n"
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
        """Create a seeded DB at latest version (via MIGRATIONS_DIR) and a mig_dir with 005_noop + 999_bad.

        After applying MIGRATIONS_DIR the DB is at the latest committed version
        (migrations 001-004). The custom mig_dir uses version 005 for the noop
        migration so it runs after the real chain.

        Args:
            tmp_path: Pytest-provided temporary directory.

        Returns:
            A tuple of ``(db_path, conn, mig_dir)`` ready for the rollback scenario.
            ``conn`` is the open connection after applying the full chain.
            ``mig_dir`` contains both ``005_noop.sql`` and ``999_bad.sql``.
        """
        mig_dir = tmp_path / "migrations"
        mig_dir.mkdir()
        # Valid migration: creates `noop` table at version 5.
        (mig_dir / "005_noop.sql").write_text(
            "CREATE TABLE noop (id INTEGER PRIMARY KEY);\nPRAGMA user_version = 5;\n",
            encoding="utf-8",
        )
        # Malformed migration: intentionally broken SQL at version 999.
        (mig_dir / "999_bad.sql").write_text(
            "CREATE TABLE foo (BAD SQL;",
            encoding="utf-8",
        )
        db_path = tmp_path / "lib.db"
        conn = open_db(db_path, event_bus=EventBus())
        apply_migrations(conn, MIGRATIONS_DIR)  # applies the full chain; user_version=latest
        return db_path, conn, mig_dir

    def test_bad_migration_raises_indexer_migration_error(self, tmp_path: Path) -> None:
        """IndexerMigrationError is raised with version=999 when migration 999 is malformed.

        In a single ``apply_migrations`` call on ``mig_dir`` (which contains both
        ``003_noop.sql`` and ``999_bad.sql``):
        - ``003`` is applied successfully (version → 3).
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

        The snapshot for version 999 is taken after version 5 has been applied (``noop``
        table exists).  After rollback, the DB is at the snapshot state: ``noop`` present,
        ``foo`` absent.
        """
        db_path, conn, mig_dir = self._setup_db_and_mig_dir(tmp_path)

        with pytest.raises(IndexerMigrationError):
            apply_migrations(conn, mig_dir)

        # Re-open the DB (connection was closed during rollback) and verify state.
        conn2 = open_db(db_path, event_bus=EventBus())
        tables = _table_names(conn2)
        assert "foo" not in tables, "foo table should not exist after rollback"
        # noop was added by the successful 005 migration and should still be present
        # in the restored snapshot (which was taken just before 999).
        assert "noop" in tables, "noop table from migration 005 should be preserved in snapshot"
