"""Unit tests for personalscraper.acquire migration chain.

Covers:
- Applying the full migration chain (001 + 002) to a fresh DB.
- All 6 domain tables + schema_version table exist (including cross-seed tables from 002).
- PRAGMA user_version == 2 after fresh apply.
- Partial indexes idx_wanted_pending + idx_seed_dispatched_path exist (001).
- schema_version contains version 1 (002 omitted the INSERT — tracked as tech-debt).
- Idempotence (second apply is a no-op).
- seed_obligation CHECK constraints (001).
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

# Expected tables after the full migration chain (001 + 002) is applied.
_LATEST_VERSION = 3

_EXPECTED_TABLES = {
    "followed_series",
    "wanted",
    "seed_obligation",
    "ratio_state",
    "cross_seed_history",
    "cross_seed_quota",
    "watch_state",
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
# Test: apply full migration chain to fresh DB
# ---------------------------------------------------------------------------


class TestAcquireMigrations:
    """Full migration chain (001 + 002) creates 6 domain tables + schema_version."""

    def test_user_version_is_latest(self, tmp_path: Path) -> None:
        """After applying the full chain, PRAGMA user_version equals the latest version."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == _LATEST_VERSION

    def test_all_tables_present(self, tmp_path: Path) -> None:
        """After applying the full chain, all 6 domain tables + schema_version exist."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        assert _table_names(conn) == _EXPECTED_TABLES

    def test_schema_version_row_exists(self, tmp_path: Path) -> None:
        """After applying the full chain, schema_version contains version 1 then version 2."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        assert rows == [(1,), (2,), (3,)]

    def test_partial_index_wanted_pending_exists(self, tmp_path: Path) -> None:
        """After applying the full chain, the partial index idx_wanted_pending exists (001)."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_wanted_pending'"
        ).fetchall()
        assert len(rows) == 1

    def test_partial_index_seed_dispatched_path_exists(self, tmp_path: Path) -> None:
        """After applying the full chain, the partial index idx_seed_dispatched_path exists (001)."""
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
