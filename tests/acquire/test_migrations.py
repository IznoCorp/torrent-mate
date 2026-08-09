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

# Expected tables after the full migration chain (001 → 017) is applied.
_LATEST_VERSION = 22

_EXPECTED_TABLES = {
    "followed_series",
    "wanted",
    "seed_obligation",
    "ratio_state",
    "cross_seed_history",
    "cross_seed_quota",
    "watch_state",
    "aired_episode",
    "staging_provenance",
    "download_marks",
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
        """After applying the full chain, schema_version carries every marker-writing script.

        014 is absent on purpose: it bumps ``user_version`` without inserting a
        ``schema_version`` marker. The list is the set of scripts that DO insert one.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        rows = conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()
        expected = [(v,) for v in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19, 20, 21, 22)]
        assert rows == expected

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
                "VALUES ('abc', 'c411', -1, 1.0, 1)"
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
                "VALUES ('abc', 'c411', 100, -0.5, 1)"
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
            "VALUES ('abc', 'c411', 0, 0.0, 1)"
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


# ---------------------------------------------------------------------------
# Helpers for migration 008
# ---------------------------------------------------------------------------


def _apply_up_to_007(conn: sqlite3.Connection, tmp_path: Path) -> None:
    """Apply migrations 001–007 only (schema BEFORE the 008 wanted rebuild).

    Copies the pre-008 ``*.sql`` scripts into an isolated temp dir so that
    ``apply_migrations`` sees exactly the 001–007 chain — leaving the DB at
    ``user_version=7`` with the original CHECK constraint and no verdict columns.
    This lets the test seed wanted rows before exercising the 008 rebuild.

    Args:
        conn: Open connection to the DB being migrated.
        tmp_path: Pytest temp dir used to stage the pre-008 migration subset.
    """
    subset = tmp_path / "migrations_pre_008"
    subset.mkdir()
    for name in (
        "001_init.sql",
        "002_cross_seed.sql",
        "003_watch_state.sql",
        "004_followed_unique.sql",
        "005_followed_metadata.sql",
        "006_followed_kind.sql",
        "007_aired_episode.sql",
    ):
        (subset / name).write_text((MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    apply_migrations(conn, subset)


def _squat_index_name(conn: sqlite3.Connection) -> None:
    """Force 008 to fail at the statement AFTER its destructive swap.

    ``DROP TABLE wanted`` takes ``idx_wanted_pending`` with it, so the name is
    free by the time 008 recreates the index. Parking a TABLE on that name makes
    ``CREATE INDEX IF NOT EXISTS`` raise — which happens once the drop and the
    rename have already run, exactly the window the transaction must cover.

    Args:
        conn: A connection already migrated to 007.
    """
    conn.execute("DROP INDEX idx_wanted_pending")
    conn.execute("CREATE TABLE idx_wanted_pending (boom INTEGER)")
    conn.commit()


# ---------------------------------------------------------------------------
# Migration 008: available status + verdict columns on wanted (table rebuild)
# ---------------------------------------------------------------------------


class TestMigration008:
    """008 adds 'available' status + last_search_outcome / last_search_found to wanted."""

    # ── (a) fresh DB → new columns + 'available' accepted ─────────────────

    def test_fresh_db_has_new_columns(self, tmp_path: Path) -> None:
        """After applying the full chain, wanted has last_search_outcome and last_search_found."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        # Verify the two new columns exist on the wanted table.
        cols = {row[1] for row in conn.execute("PRAGMA table_info('wanted')").fetchall()}
        assert "last_search_outcome" in cols
        assert "last_search_found" in cols

    def test_fresh_db_accepts_available_status(self, tmp_path: Path) -> None:
        """After migration, INSERT with status='available' succeeds."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, status, enqueued_at) "
            "VALUES (NULL, '{}', 'episode', 'available', 1)"
        )
        conn.commit()
        row = conn.execute("SELECT status FROM wanted WHERE id = 1").fetchone()
        assert row[0] == "available"

    # ── (b) idempotence ───────────────────────────────────────────────────

    def test_idempotent_second_call(self, tmp_path: Path) -> None:
        """Calling apply_migrations twice leaves wanted unchanged on second call."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)
        version_after_first = _user_version(conn)

        # Insert a row so we can verify it survives a second apply untouched.
        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, status, enqueued_at) "
            "VALUES (NULL, '{}', 'episode', 'available', 1)"
        )
        conn.commit()

        apply_migrations(conn, MIGRATIONS_DIR)
        assert _user_version(conn) == version_after_first

        # The row we inserted must still be there — the second apply didn't
        # re-execute the rebuild (user_version was already 8).
        count = conn.execute("SELECT COUNT(*) FROM wanted").fetchone()[0]
        assert count == 1

    # ── (c) data preservation ─────────────────────────────────────────────

    def test_data_preservation_all_statuses(self, tmp_path: Path) -> None:
        """Rows covering every status survive 008 with all values intact, new cols NULL."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)

        # Insert a row for every pre-008 status with non-default values.
        conn.executescript(
            """
            INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode,
                                status, criteria_json, enqueued_at, last_search_at,
                                attempts, grabbed_hash)
            VALUES
              (1, NULL, '{}', 'episode', 1, 1,
               'pending',   '{"lang":"fr"}', 100, 200, 0, NULL),
              (2, NULL, '{}', 'episode', 1, 2,
               'searching', '{"lang":"fr"}', 110, 210, 1, NULL),
              (3, NULL, '{}', 'episode', 1, 3,
               'grabbed',   '{"lang":"en"}', 120, 220, 1, 'deadbeef01'),
              (4, NULL, '{}', 'episode', 1, 4,
               'done',      '{"lang":"en"}', 130, 230, 1, 'deadbeef02'),
              (5, NULL, '{}', 'episode', 1, 5,
               'abandoned', '{"lang":"fr"}', 140, 240, 3, NULL);
            """
        )
        conn.commit()

        # Apply 008 (rebuilds wanted).
        apply_migrations(conn, MIGRATIONS_DIR)

        # Every row must survive with every column value intact.
        rows = conn.execute(
            "SELECT id, followed_id, media_ref_json, kind, season, episode, "
            "status, criteria_json, enqueued_at, last_search_at, attempts, "
            "grabbed_hash, last_search_outcome, last_search_found "
            "FROM wanted ORDER BY id"
        ).fetchall()

        assert len(rows) == 5

        # Row 1: pending
        assert rows[0] == (1, None, "{}", "episode", 1, 1, "pending", '{"lang":"fr"}', 100, 200, 0, None, None, None)
        # Row 2: searching
        assert rows[1] == (2, None, "{}", "episode", 1, 2, "searching", '{"lang":"fr"}', 110, 210, 1, None, None, None)
        # Row 3: grabbed (with hash)
        assert rows[2] == (
            3,
            None,
            "{}",
            "episode",
            1,
            3,
            "grabbed",
            '{"lang":"en"}',
            120,
            220,
            1,
            "deadbeef01",
            None,
            None,
        )
        # Row 4: done (with hash)
        assert rows[3] == (
            4,
            None,
            "{}",
            "episode",
            1,
            4,
            "done",
            '{"lang":"en"}',
            130,
            230,
            1,
            "deadbeef02",
            None,
            None,
        )
        # Row 5: abandoned
        assert rows[4] == (5, None, "{}", "episode", 1, 5, "abandoned", '{"lang":"fr"}', 140, 240, 3, None, None, None)

    # ── (d) partial index preservation ────────────────────────────────────

    def test_idx_wanted_pending_is_partial(self, tmp_path: Path) -> None:
        """After 008 rebuild, idx_wanted_pending exists and is still partial."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'idx_wanted_pending'").fetchone()
        assert row is not None, "idx_wanted_pending must exist after rebuild"
        assert "WHERE" in row[0], "idx_wanted_pending must be a partial index (contain WHERE)"

    # ── (e) FK integrity ──────────────────────────────────────────────────

    def test_foreign_key_check_clean(self, tmp_path: Path) -> None:
        """After 008, PRAGMA foreign_key_check returns no violations."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(violations) == 0, f"foreign_key_check found violations: {violations}"

    # ── (f) CHECK constraint: 'available' OK, bogus rejected ──────────────

    def test_insert_available_succeeds(self, tmp_path: Path) -> None:
        """INSERT with status='available' succeeds (new status in CHECK)."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at) "
            "VALUES (NULL, '{}', 'episode', 1, 1, 'available', 1)"
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM wanted WHERE status = 'available'").fetchone()[0] == 1

    def test_insert_bogus_rejected(self, tmp_path: Path) -> None:
        """INSERT with status='bogus' raises IntegrityError (CHECK constraint)."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO wanted (followed_id, media_ref_json, kind, status, enqueued_at) "
                "VALUES (NULL, '{}', 'episode', 'bogus', 1)"
            )
            conn.commit()

    # ── (f) atomicity: user_version advances only on success ──────────────

    def test_failed_rebuild_leaves_user_version_at_7(self, tmp_path: Path) -> None:
        """Regression (PR #320 review, F-M7): a failed 008 must not claim schema 8.

        ``PRAGMA user_version = 8`` used to be the FIRST statement, and
        ``executescript`` is not one transaction — so it auto-committed on its
        own. A crash anywhere in the rebuild therefore left a DB advertising
        schema 8 while carrying schema 7 (or a half-swapped one), and the
        applier — which skips any script whose version <= user_version — would
        never run it again to repair the damage.

        Forced failure: pre-create a conflicting ``wanted_new`` table so
        ``CREATE TABLE wanted_new`` raises. The script is executed directly
        (not through ``apply_migrations``) because the applier restores its
        pre-migration snapshot on failure, which would mask what the script
        itself left behind.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)
        conn.execute("CREATE TABLE wanted_new (boom INTEGER)")
        conn.commit()
        assert _user_version(conn) == 7

        sql_text = (MIGRATIONS_DIR / "008_wanted_available_state.sql").read_text(encoding="utf-8")
        with pytest.raises(sqlite3.OperationalError):
            conn.executescript(sql_text)
        conn.execute("ROLLBACK")  # the failed script left its transaction open

        assert _user_version(conn) == 7, (
            "a failed rebuild must NOT advertise schema 8 — the applier would never re-run it"
        )
        # And the original table is intact: the destructive part never ran.
        cols = {row[1] for row in conn.execute("PRAGMA table_info('wanted')").fetchall()}
        assert "last_search_outcome" not in cols
        assert conn.execute("SELECT COUNT(*) FROM schema_version WHERE version = 8").fetchone()[0] == 0

    def test_destructive_rebuild_is_one_transaction(self, tmp_path: Path) -> None:
        """The swap, the marker row AND ``user_version`` commit together, or not at all.

        Proven behaviourally by failing AFTER the destructive part: a table
        squatting the ``idx_wanted_pending`` name makes ``CREATE INDEX`` raise,
        which happens once ``DROP TABLE wanted`` and the rename have already
        run. Everything must still roll back — old schema, no orphan
        ``wanted_new``, ``user_version`` still 7.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)
        _squat_index_name(conn)

        sql_text = (MIGRATIONS_DIR / "008_wanted_available_state.sql").read_text(encoding="utf-8")
        with pytest.raises(sqlite3.OperationalError):
            conn.executescript(sql_text)
        conn.execute("ROLLBACK")

        assert _user_version(conn) == 7
        # The swap rolled back with the rest: old schema, no orphan wanted_new.
        cols = {row[1] for row in conn.execute("PRAGMA table_info('wanted')").fetchall()}
        assert "last_search_outcome" not in cols, "the rebuild must roll back whole"
        names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        assert "wanted" in names
        assert "wanted_new" not in names, "a rolled-back rebuild must leave no orphan table"
        assert conn.execute("SELECT COUNT(*) FROM schema_version WHERE version = 8").fetchone()[0] == 0

    def test_user_version_and_schema_commit_together(self, tmp_path: Path) -> None:
        """Regression (PR #320 review, cycle 2): no window between the two.

        ``PRAGMA user_version`` writes the database header and IS transactional.
        Leaving it after the COMMIT opened a window where the rebuild was
        durable but the version was not — and a re-run from there BRICKS the DB:
        the destructive part replays against an already-migrated schema and dies
        on the ``schema_version`` PRIMARY KEY, forever. Inside the transaction
        the two become durable in the same commit, so the window does not exist.

        Probes the window directly: run the script only as far as its COMMIT —
        i.e. simulate the process dying the instant the rebuild became durable —
        and assert the version is ALREADY 8 there. With the pragma after the
        COMMIT this stops at 8-worth of schema advertising version 7, and the
        re-run bricks the DB.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)

        sql_text = (MIGRATIONS_DIR / "008_wanted_available_state.sql").read_text(encoding="utf-8")
        head, sep, _tail = sql_text.partition("COMMIT;")
        assert sep, "008 must wrap its rebuild in an explicit transaction"
        conn.executescript(head + sep)  # everything up to and including COMMIT

        migrated = "last_search_outcome" in {row[1] for row in conn.execute("PRAGMA table_info('wanted')").fetchall()}
        version_after = _user_version(conn)
        assert migrated, "the prefix must have applied the rebuild"
        assert version_after == 8, (
            "the schema is durable but user_version is still "
            f"{version_after}: a crash here leaves a DB whose re-run replays the "
            "destructive part against an already-migrated schema"
        )

    def test_a_replay_from_the_committed_state_is_a_clean_no_op(self, tmp_path: Path) -> None:
        """The applier skips 008 once the rebuild committed — no destructive replay.

        The end state of the window probed above: with the version inside the
        transaction, a process that died right after the COMMIT restarts into a
        DB the applier considers done. The data survives untouched.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)
        conn.execute(
            "INSERT INTO wanted (id, followed_id, media_ref_json, kind, status, enqueued_at) "
            "VALUES (1, NULL, '{}', 'episode', 'pending', 100)"
        )
        conn.commit()

        sql_text = (MIGRATIONS_DIR / "008_wanted_available_state.sql").read_text(encoding="utf-8")
        head, sep, _tail = sql_text.partition("COMMIT;")
        conn.executescript(head + sep)  # "crash" right after the commit

        apply_migrations(conn, MIGRATIONS_DIR)  # the restart

        assert _user_version(conn) == _LATEST_VERSION
        assert conn.execute("SELECT COUNT(*) FROM wanted").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM schema_version WHERE version = 8").fetchone()[0] == 1

    def test_replaying_the_script_over_an_existing_marker_still_completes(self, tmp_path: Path) -> None:
        """``INSERT OR IGNORE`` keeps the marker row from blocking a rebuild.

        The marker is a record that the migration ran, not a constraint to trip
        over. A plain INSERT made a DB that already carried the row impossible
        to migrate — the rebuild died at its final statement every time.
        """
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)
        conn.execute("INSERT INTO schema_version(version) VALUES (8)")
        conn.commit()

        sql_text = (MIGRATIONS_DIR / "008_wanted_available_state.sql").read_text(encoding="utf-8")
        conn.executescript(sql_text)  # must NOT raise

        assert _user_version(conn) == 8
        cols = {row[1] for row in conn.execute("PRAGMA table_info('wanted')").fetchall()}
        assert "last_search_outcome" in cols
        assert conn.execute("SELECT COUNT(*) FROM schema_version WHERE version = 8").fetchone()[0] == 1


class TestMigrationFailureLeavesNoOpenTransaction:
    """The applier never hands back a connection stuck inside a failed script's tx."""

    def test_failure_without_a_snapshot_rolls_back_and_closes(self, tmp_path: Path) -> None:
        """Regression (PR #320 review, M8): the no-snapshot raise path must clean up.

        An in-memory DB gets no ``.bak``, so the restore branch is skipped. 008
        opens an explicit ``BEGIN``, so a statement failing inside it leaves that
        transaction OPEN. The applier used to raise straight through, handing the
        caller a connection with ``in_transaction=True`` still holding the writer
        lock — every later write on it failed for reasons no log explained. Both
        failure paths now leave the connection closed.
        """
        from personalscraper.core.sqlite.errors import SqliteMigrationError

        conn = sqlite3.connect(":memory:")
        _apply_up_to_007(conn, tmp_path)
        _squat_index_name(conn)

        with pytest.raises(SqliteMigrationError):
            apply_migrations(conn, MIGRATIONS_DIR)

        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_a_fresh_connection_can_still_migrate_afterwards(self, tmp_path: Path) -> None:
        """The failure is recoverable: nothing is left holding the DB hostage."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)
        _squat_index_name(conn)
        conn.close()

        # Clear the squatter, then a fresh connection completes the chain.
        repair = sqlite3.connect(str(db_path))
        repair.execute("DROP TABLE idx_wanted_pending")
        repair.commit()
        apply_migrations(repair, MIGRATIONS_DIR)
        assert _user_version(repair) == _LATEST_VERSION
        repair.close()


# ---------------------------------------------------------------------------
# Migration 013: season kind + absorbed/fallback_episodes statuses + absorbed_by
# ---------------------------------------------------------------------------


class TestMigration013:
    """013 widens kind/status CHECKs and adds absorbed_by column (season-grab)."""

    def test_fresh_db_accepts_season_kind(self, tmp_path: Path) -> None:
        """After applying the full chain, INSERT with kind='season' succeeds."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at) "
            "VALUES (NULL, '{}', 'season', 3, NULL, 'pending', 1)"
        )
        conn.commit()
        row = conn.execute("SELECT kind, season, episode FROM wanted WHERE id = 1").fetchone()
        assert row == ("season", 3, None)

    def test_fresh_db_accepts_absorbed_status(self, tmp_path: Path) -> None:
        """After migration, INSERT with status='absorbed' succeeds."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at) "
            "VALUES (NULL, '{}', 'episode', 1, 1, 'absorbed', 1)"
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM wanted WHERE status = 'absorbed'").fetchone()[0] == 1

    def test_fresh_db_accepts_fallback_episodes_status(self, tmp_path: Path) -> None:
        """After migration, INSERT with status='fallback_episodes' succeeds."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at) "
            "VALUES (NULL, '{}', 'season', 3, NULL, 'fallback_episodes', 1)"
        )
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM wanted WHERE status = 'fallback_episodes'").fetchone()[0] == 1

    def test_fresh_db_has_absorbed_by_column(self, tmp_path: Path) -> None:
        """After applying the full chain, wanted has absorbed_by column."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        cols = {row[1] for row in conn.execute("PRAGMA table_info('wanted')").fetchall()}
        assert "absorbed_by" in cols

    def test_absorbed_by_is_nullable(self, tmp_path: Path) -> None:
        """absorbed_by defaults to NULL for new rows."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        conn.execute(
            "INSERT INTO wanted (followed_id, media_ref_json, kind, season, episode, "
            "status, enqueued_at) "
            "VALUES (NULL, '{}', 'episode', 1, 2, 'pending', 1)"
        )
        conn.commit()
        row = conn.execute("SELECT absorbed_by FROM wanted WHERE id = 1").fetchone()
        assert row[0] is None

    def test_data_preservation_across_rebuild(self, tmp_path: Path) -> None:
        """Pre-013 rows survive with all values intact, new column NULL."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        _apply_up_to_007(conn, tmp_path)

        # Insert a row with all existing columns populated.
        conn.executescript(
            """
            INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode,
                                status, criteria_json, enqueued_at, last_search_at,
                                attempts, grabbed_hash)
            VALUES (1, NULL, '{}', 'episode', 1, 1,
                    'pending', '{"lang":"fr"}', 100, 200, 0, NULL);
            """
        )
        conn.commit()

        apply_migrations(conn, MIGRATIONS_DIR)

        row = conn.execute("SELECT id, kind, status, absorbed_by FROM wanted WHERE id = 1").fetchone()
        assert row[0] == 1
        assert row[1] == "episode"
        assert row[2] == "pending"
        assert row[3] is None  # new column defaults to NULL for existing rows

    def test_idx_wanted_pending_preserved(self, tmp_path: Path) -> None:
        """After 013 rebuild, idx_wanted_pending still exists and is partial."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        row = conn.execute("SELECT sql FROM sqlite_master WHERE name = 'idx_wanted_pending'").fetchone()
        assert row is not None, "idx_wanted_pending must exist after rebuild"
        assert "WHERE" in row[0], "idx_wanted_pending must be a partial index"

    def test_foreign_key_check_clean(self, tmp_path: Path) -> None:
        """After 013, PRAGMA foreign_key_check returns no violations."""
        db_path = tmp_path / "acquire.db"
        conn = sqlite3.connect(str(db_path))
        apply_migrations(conn, MIGRATIONS_DIR)

        violations = conn.execute("PRAGMA foreign_key_check").fetchall()
        assert len(violations) == 0, f"foreign_key_check found violations: {violations}"
