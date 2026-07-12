"""Unit tests for personalscraper.acquire migration chain.

Covers:
- Applying the full migration chain (001 + 002 + 003 + 004) to a fresh DB.
- All 7 domain tables + schema_version table exist (cross-seed from 002, watch from 003).
- PRAGMA user_version == 4 after fresh apply.
- Partial indexes idx_wanted_pending + idx_seed_dispatched_path exist (001).
- UNIQUE index ux_followed_media_ref exists (004).
- schema_version contains versions 1..4.
- Idempotence (second apply is a no-op).
- seed_obligation CHECK constraints (001).
- 004 dedup: collapses duplicate followed_series rows on a populated DB and
  reattaches dependent wanted.followed_id to the surviving (lowest-id) row.
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

# Expected tables after the full migration chain (001 → 004) is applied.
_LATEST_VERSION = 5

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
    """Full migration chain (001 → 004) creates 7 domain tables + schema_version."""

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
        """After applying the full chain, schema_version contains versions 1..4."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        assert rows == [(1,), (2,), (3,), (4,), (5,)]

    def test_unique_index_followed_media_ref_exists(self, tmp_path: Path) -> None:
        """After applying the full chain, the UNIQUE index ux_followed_media_ref exists (004)."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='ux_followed_media_ref'"
        ).fetchall()
        assert len(rows) == 1

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


# ---------------------------------------------------------------------------
# Migration 004: dedup existing rows on a POPULATED db (with pre-existing dups)
# ---------------------------------------------------------------------------


def _apply_up_to_003(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Apply migrations 001–003 only (schema BEFORE the 004 UNIQUE index).

    Copies the pre-004 ``*.sql`` scripts into an isolated temp dir so that
    ``apply_migrations`` sees exactly the 001–003 chain — leaving the DB at
    ``user_version=3`` with NO UNIQUE index on ``followed_series.media_ref_json``.
    This lets the test seed duplicate rows (impossible once 004 has run) before
    exercising the 004 dedup path.

    Args:
        conn: Open connection to the DB being migrated.
        tmp_path: Pytest temp dir used to stage the pre-004 migration subset.
    """
    subset = tmp_path / "migrations_pre_004"
    subset.mkdir()
    for name in ("001_init.sql", "002_cross_seed.sql", "003_watch_state.sql"):
        (subset / name).write_text((MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    apply_migrations(conn, subset)


class TestMigration004Dedup:
    """004 collapses duplicate followed_series + reattaches wanted, then enforces UNIQUE."""

    _REF_A = '{"tvdb_id": 111, "tmdb_id": null, "imdb_id": null}'
    _REF_B = '{"tvdb_id": 222, "tmdb_id": null, "imdb_id": null}'

    def _seed_dups(self, conn: sqlite3.Connection) -> None:
        """Insert 3 followed rows for ref A (ids 1,2,3), 1 for ref B (id 4), + wanted rows.

        Wanted rows are attached to the loser followed ids (2 and 3) so the test
        can prove they are reattached to the survivor (MIN id = 1). One wanted
        row is attached to the ref-B survivor (id 4) and one has NULL followed_id
        to prove those are left untouched.
        """
        conn.executescript(
            f"""
            INSERT INTO followed_series (id, media_ref_json, title, active, added_at)
            VALUES
              (1, '{self._REF_A}', 'Show A v1', 1, 100),
              (2, '{self._REF_A}', 'Show A v2', 0, 200),
              (3, '{self._REF_A}', 'Show A v3', 1, 300),
              (4, '{self._REF_B}', 'Show B',    1, 400);

            INSERT INTO wanted (id, followed_id, media_ref_json, kind, status, enqueued_at)
            VALUES
              (10, 2, '{self._REF_A}', 'episode', 'pending', 500),
              (11, 3, '{self._REF_A}', 'episode', 'pending', 600),
              (12, 1, '{self._REF_A}', 'episode', 'pending', 700),
              (13, 4, '{self._REF_B}', 'episode', 'pending', 800),
              (14, NULL, '{self._REF_A}', 'episode', 'pending', 900);
            """
        )
        conn.commit()

    def test_dedup_keeps_lowest_id_and_reattaches_wanted(self, tmp_path: Path) -> None:
        """004 keeps MIN(id) per ref, deletes losers, reattaches dependent wanted rows."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_003(conn, tmp_path)
        self._seed_dups(conn)

        # Apply 004 (user_version is 3 → only 004 runs).
        apply_migrations(conn, MIGRATIONS_DIR)

        # Ref A collapsed to the single lowest-id survivor (id=1); ref B untouched (id=4).
        surviving_a = conn.execute(
            "SELECT id FROM followed_series WHERE media_ref_json = ? ORDER BY id",
            (self._REF_A,),
        ).fetchall()
        assert surviving_a == [(1,)], "ref A must collapse to exactly its lowest id (1)"
        surviving_b = conn.execute(
            "SELECT id FROM followed_series WHERE media_ref_json = ?",
            (self._REF_B,),
        ).fetchall()
        assert surviving_b == [(4,)], "ref B (no dup) must be preserved unchanged"

        # Every wanted row that pointed at a loser (2 or 3) now points at survivor 1.
        followed_ids = dict(conn.execute("SELECT id, followed_id FROM wanted ORDER BY id").fetchall())
        assert followed_ids[10] == 1, "wanted 10 (was →2) must reattach to survivor 1"
        assert followed_ids[11] == 1, "wanted 11 (was →3) must reattach to survivor 1"
        assert followed_ids[12] == 1, "wanted 12 (already →1) stays on survivor 1"
        assert followed_ids[13] == 4, "wanted 13 (ref B →4) must be untouched"
        assert followed_ids[14] is None, "wanted 14 (NULL followed_id) must stay NULL"

    def test_dedup_preserves_active_when_survivor_was_unfollowed(self, tmp_path: Path) -> None:
        """004 promotes the MIN(id) survivor to active=1 when a higher-id dup is active.

        A duplicate group where the low-id row is unfollowed (active=0) and a
        higher-id row is re-followed (active=1) must NOT collapse to the inactive
        row — that would silently drop the active follow.  The survivor keeps the
        MIN id (1) but is promoted to active=1 (Step 0 of the migration).
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_003(conn, tmp_path)

        # id=1 active=0 (unfollowed), id=2 active=1 (re-followed) — same ref.
        conn.executescript(
            f"""
            INSERT INTO followed_series (id, media_ref_json, title, active, added_at)
            VALUES
              (1, '{self._REF_A}', 'Show A unfollowed', 0, 100),
              (2, '{self._REF_A}', 'Show A refollowed', 1, 200);
            """
        )
        conn.commit()

        apply_migrations(conn, MIGRATIONS_DIR)

        rows = conn.execute(
            "SELECT id, active FROM followed_series WHERE media_ref_json = ? ORDER BY id",
            (self._REF_A,),
        ).fetchall()
        # Survivor is the MIN id (1) — but active-ness of the group is preserved.
        assert rows == [(1, 1)], "survivor must be id=1 with active=1 (active follow not dropped)"

    def test_unique_index_enforced_after_dedup(self, tmp_path: Path) -> None:
        """After 004, a second raw INSERT of a duplicate media_ref_json is rejected."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_003(conn, tmp_path)
        self._seed_dups(conn)
        apply_migrations(conn, MIGRATIONS_DIR)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO followed_series (media_ref_json, title, active, added_at) VALUES (?, 'dup', 1, 1)",
                (self._REF_A,),
            )
            conn.commit()

    def test_dedup_fresh_db_no_rows_still_creates_index(self, tmp_path: Path) -> None:
        """004 applies cleanly on a fresh (empty) db and still creates the UNIQUE index."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)  # full chain on an empty db
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='ux_followed_media_ref'"
        ).fetchall()
        assert len(rows) == 1
        assert _user_version(conn) == _LATEST_VERSION
