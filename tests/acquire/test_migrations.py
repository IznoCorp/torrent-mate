"""Unit tests for personalscraper.acquire migration chain.

Covers:
- Applying migration 001 to a fresh DB.
- All 4 domain tables + schema_version table exist.
- PRAGMA user_version == 1 after fresh apply.
- Partial index idx_wanted_pending exists.
- schema_version contains version 1.
- Idempotence (second apply is a no-op).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personalscraper.core.sqlite import apply_migrations

# ---------------------------------------------------------------------------
# Paths to real migration artefacts
# ---------------------------------------------------------------------------

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"

# Expected tables after migration 001 is applied.
_EXPECTED_TABLES = {
    "followed_series",
    "wanted",
    "seed_obligation",
    "ratio_state",
    "schema_version",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


class TestAcquireMigrations001:
    """Migration 001 creates the initial acquire.db schema with 4 domain tables."""

    def test_user_version_is_one(self, tmp_path: Path) -> None:
        """After applying 001, PRAGMA user_version equals 1."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == 1

    def test_all_tables_present(self, tmp_path: Path) -> None:
        """After applying 001, all 4 domain tables + schema_version exist."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _table_names(conn) == _EXPECTED_TABLES

    def test_schema_version_row_exists(self, tmp_path: Path) -> None:
        """After applying 001, schema_version contains version 1.

        Every migration script must record its version in the ``schema_version``
        audit table — this is the contract that lets tooling reason about the
        migration chain.  A migration that bumps ``PRAGMA user_version`` without
        inserting into ``schema_version`` is a bug.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute("SELECT version FROM schema_version").fetchall()
        assert rows == [(1,)]

    def test_partial_index_wanted_pending_exists(self, tmp_path: Path) -> None:
        """After applying 001, the partial index idx_wanted_pending exists."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_wanted_pending'"
        ).fetchall()
        assert len(rows) == 1

    def test_partial_index_seed_dispatched_path_exists(self, tmp_path: Path) -> None:
        """After applying 001, the partial index idx_seed_dispatched_path exists."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_seed_dispatched_path'"
        ).fetchall()
        assert len(rows) == 1

    def test_idempotent_second_call(self, tmp_path: Path) -> None:
        """Calling apply_migrations twice is a no-op on the second call."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        version_after_first = _user_version(conn)
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == version_after_first

    def test_seed_obligation_rejects_negative_min_seed_time(self, tmp_path: Path) -> None:
        """T1: the seed_obligation CHECK rejects a negative min_seed_time_s.

        Defense-in-depth at the DB boundary: even bypassing the domain
        __post_init__ guard via raw SQL, a negative floor is refused.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO seed_obligation "
                "(info_hash, source_tracker, min_seed_time_s, min_ratio, added_at) "
                "VALUES ('abc', 'lacale', -1, 1.0, 1)"
            )
            conn.commit()

    def test_seed_obligation_rejects_negative_min_ratio(self, tmp_path: Path) -> None:
        """T1: the seed_obligation CHECK rejects a negative min_ratio."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO seed_obligation "
                "(info_hash, source_tracker, min_seed_time_s, min_ratio, added_at) "
                "VALUES ('abc', 'lacale', 100, -0.5, 1)"
            )
            conn.commit()

    def test_seed_obligation_accepts_zero_floors(self, tmp_path: Path) -> None:
        """T1: zero floors are accepted by the CHECK (non-negative, not positive)."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        conn.execute(
            "INSERT INTO seed_obligation "
            "(info_hash, source_tracker, min_seed_time_s, min_ratio, added_at) "
            "VALUES ('abc', 'lacale', 0, 0.0, 1)"
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM seed_obligation").fetchone()[0]
        assert count == 1
