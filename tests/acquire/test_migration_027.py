"""Migration 027: requesters, scope, removal, trigger and candidates (K3 P2, additive).

Covers the script on a fresh store and on a 026 store (rows kept, the defaults
``scope='follow'`` / ``removed_at`` NULL / ``trigger`` NULL), the ``ON DELETE CASCADE`` of
the two new tables (``foreign_keys=ON`` asserted: SQLite ignores a CASCADE without it) and
the CHECK constraints that refuse a bad floor, via, scope or trigger.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from personalscraper.core.sqlite import apply_migrations, open_db

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "acquire" / "migrations"

_REF = '{"tvdb_id": 81189, "tmdb_id": null, "imdb_id": null}'


def _columns(conn: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row | tuple]:
    """Return a table's columns by name, as ``PRAGMA table_info`` rows.

    Args:
        conn: An open connection.
        table: The table to describe.

    Returns:
        ``{column name: table_info row}``.
    """
    return {row[1]: row for row in conn.execute(f"PRAGMA table_info({table})")}  # noqa: S608 — a test literal


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Yield a fully migrated acquire connection, opened as the store opens it.

    Args:
        tmp_path: Pytest temp directory.

    Yields:
        A connection with ``foreign_keys=ON`` and every migration applied.
    """
    connection = open_db(tmp_path / "acquire.db")
    apply_migrations(connection, MIGRATIONS_DIR)
    try:
        yield connection
    finally:
        connection.close()


def _seed_follow_and_wanted(conn: sqlite3.Connection) -> tuple[int, int]:
    """Insert one follow and one wanted row on it.

    Args:
        conn: A migrated connection.

    Returns:
        ``(followed_id, wanted_id)``.
    """
    conn.execute(
        "INSERT INTO followed_series (id, media_ref_json, title, active, added_at) VALUES (1, ?, 'Show', 1, 100)",
        (_REF,),
    )
    conn.execute(
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, status, enqueued_at) "
        "VALUES (10, 1, ?, 'episode', 'pending', 200)",
        (_REF,),
    )
    return 1, 10


class TestFreshStore:
    """027 applied on a fresh store."""

    def test_user_version_is_27(self, conn: sqlite3.Connection) -> None:
        """The chain ends at 027 and records its schema_version marker."""
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 27
        assert conn.execute("SELECT 1 FROM schema_version WHERE version = 27").fetchone() is not None

    def test_new_tables_and_columns_exist(self, conn: sqlite3.Connection) -> None:
        """The requester and candidate tables and the three new columns are there."""
        assert set(_columns(conn, "acquisition_requester")) == {
            "followed_id",
            "account_id",
            "via",
            "floor",
            "paused",
            "since",
        }
        assert set(_columns(conn, "wanted_candidate")) == {
            "wanted_id",
            "rank",
            "provider",
            "title",
            "info_hash",
            "size_bytes",
            "seeders",
            "resolution",
            "source",
            "language",
            "score",
            "season",
            "episode",
            "searched_at",
        }
        assert {"scope", "removed_at"} <= set(_columns(conn, "followed_series"))
        assert "trigger" in _columns(conn, "wanted")

    def test_foreign_keys_are_on(self, conn: sqlite3.Connection) -> None:
        """The connection enforces foreign keys: a CASCADE is a no-op without it."""
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


class TestOn026Store:
    """027 applied on top of a 026 store that already holds rows, every column set."""

    _FOLLOWED_SEED = (
        "INSERT INTO followed_series (id, media_ref_json, title, active, quality_profile_json, cadence_json, "
        "added_at, poster_url, overview, year, season_count, kind, replace_owned, series_status, original_title) "
        "VALUES (?, ?, ?, ?, '{\"floor\": 1080}', '{\"every\": \"daily\"}', ?, 'http://poster', "
        "'An overview', 2008, 5, ?, ?, 'Ended', 'Original Title')"
    )
    _WANTED_SEED = (
        "INSERT INTO wanted (id, followed_id, media_ref_json, kind, season, episode, status, criteria_json, "
        "enqueued_at, last_search_at, attempts, grabbed_hash, last_search_outcome, last_search_found, "
        "tried_hashes_json, absorbed_by, last_search_best_json, last_grab_reason, last_grab_at) "
        "VALUES (?, ?, ?, 'episode', ?, ?, ?, '{\"q\": 1}', ?, 250, 4, 'abcdef0123', 'available', 3, "
        "'[\"dead\"]', ?, '{\"best\": 1}', 'a reason', 260)"
    )

    def _store_at_026(self, tmp_path: Path) -> sqlite3.Connection:
        """Build a store stopped at 026 and seed two follows and two wanted rows, no column left at its default.

        Args:
            tmp_path: Pytest temp directory.

        Returns:
            The connection, at ``user_version`` 26.
        """
        subset = tmp_path / "migrations_026"
        subset.mkdir()
        for script in MIGRATIONS_DIR.glob("0*.sql"):
            if int(script.name[:3]) <= 26:
                shutil.copy(script, subset / script.name)
        connection = open_db(tmp_path / "acquire.db")
        apply_migrations(connection, subset)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 26
        connection.execute(self._FOLLOWED_SEED, (1, _REF, "Show", 0, 100, "show", 1))
        connection.execute(
            self._FOLLOWED_SEED, (2, '{"tvdb_id": null, "tmdb_id": 603, "imdb_id": null}', "Film", 1, 101, "movie", 0)
        )
        connection.execute(self._WANTED_SEED, (11, 1, _REF, 2, 4, "absorbed", 199, None))
        connection.execute(self._WANTED_SEED, (10, 1, _REF, 2, 3, "grabbed", 200, 11))
        return connection

    @staticmethod
    def _rows(connection: sqlite3.Connection, table: str, columns: list[str]) -> list[tuple]:
        """Read the given columns of every row of a table, by id.

        Args:
            connection: An open connection.
            table: ``followed_series`` or ``wanted``.
            columns: The columns to read, in order.

        Returns:
            The rows as tuples.
        """
        return connection.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY id").fetchall()  # noqa: S608 — test literals

    def test_every_old_column_of_every_row_is_kept(self, tmp_path: Path) -> None:
        """No 026 column of a followed_series or wanted row is rewritten, nulled or dropped by 027."""
        connection = self._store_at_026(tmp_path)
        try:
            old_columns = {table: list(_columns(connection, table)) for table in ("followed_series", "wanted")}
            before = {table: self._rows(connection, table, cols) for table, cols in old_columns.items()}
            assert all(None not in row for row in before["followed_series"][:1] + before["wanted"][:1]), (
                "the seed must leave no column NULL, or a column nulled by the migration would go unseen"
            )

            apply_migrations(connection, MIGRATIONS_DIR)

            after = {table: self._rows(connection, table, cols) for table, cols in old_columns.items()}
        finally:
            connection.close()

        assert after == before
        assert len(before["followed_series"]) == 2
        assert len(before["wanted"]) == 2

    def test_the_new_columns_take_their_defaults_on_old_rows(self, tmp_path: Path) -> None:
        """Every 026 follow becomes scope 'follow' and not removed, every 026 wanted row has trigger NULL."""
        connection = self._store_at_026(tmp_path)
        try:
            apply_migrations(connection, MIGRATIONS_DIR)

            follows = connection.execute("SELECT scope, removed_at FROM followed_series ORDER BY id").fetchall()
            wanted = connection.execute("SELECT trigger FROM wanted ORDER BY id").fetchall()
            requesters = connection.execute("SELECT COUNT(*) FROM acquisition_requester").fetchone()[0]
            candidates = connection.execute("SELECT COUNT(*) FROM wanted_candidate").fetchone()[0]
        finally:
            connection.close()

        assert follows == [("follow", None), ("follow", None)]
        assert wanted == [(None,), (None,)]
        assert (requesters, candidates) == (0, 0), "no backfill of requesters (K9's reprise), no candidate invented"


class TestCascade:
    """The CASCADE removes requesters and candidates with their parent row."""

    def test_deleting_a_follow_removes_its_requesters(self, conn: sqlite3.Connection) -> None:
        """A followed_series row takes its acquisition_requester rows with it."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        conn.execute(
            "INSERT INTO acquisition_requester (followed_id, account_id, via, floor, paused, since) "
            "VALUES (?, 'acc-1', 'follow', 1080, 0, 300), (?, 'acc-2', 'request', NULL, 1, 301)",
            (followed_id, followed_id),
        )

        conn.execute("DELETE FROM followed_series WHERE id = ?", (followed_id,))

        assert conn.execute("SELECT COUNT(*) FROM acquisition_requester").fetchone()[0] == 0

    def test_deleting_a_wanted_row_removes_its_candidates(self, conn: sqlite3.Connection) -> None:
        """A wanted row takes its wanted_candidate rows with it."""
        _, wanted_id = _seed_follow_and_wanted(conn)
        conn.execute(
            "INSERT INTO wanted_candidate (wanted_id, rank, provider, title, size_bytes, seeders, score, searched_at) "
            "VALUES (?, 1, 'c411', 'Show.S01E01.1080p', 1000, 12, 90, 400), "
            "(?, 2, 'c411', 'Show.S01E01.720p', 800, 3, 70, 400)",
            (wanted_id, wanted_id),
        )

        conn.execute("DELETE FROM wanted WHERE id = ?", (wanted_id,))

        assert conn.execute("SELECT COUNT(*) FROM wanted_candidate").fetchone()[0] == 0

    def test_a_requester_of_a_missing_follow_is_refused(self, conn: sqlite3.Connection) -> None:
        """The foreign key refuses a requester whose follow does not exist."""
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO acquisition_requester (followed_id, account_id, via, since) VALUES (99, 'a', 'follow', 1)"
            )


class TestChecks:
    """The CHECK constraints refuse out-of-domain values."""

    @pytest.mark.parametrize("floor", [480, 1081, 0, -1])
    def test_a_bad_floor_is_refused(self, conn: sqlite3.Connection, floor: int) -> None:
        """Only 720, 1080, 2160 or NULL are floors."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO acquisition_requester (followed_id, account_id, via, floor, since) "
                "VALUES (?, 'a', 'follow', ?, 1)",
                (followed_id, floor),
            )

    @pytest.mark.parametrize("floor", [720, 1080, 2160, None])
    def test_a_good_floor_is_accepted(self, conn: sqlite3.Connection, floor: int | None) -> None:
        """Each rung of the ladder, and none, is a floor."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        conn.execute(
            "INSERT INTO acquisition_requester (followed_id, account_id, via, floor, since) "
            "VALUES (?, 'a', 'follow', ?, 1)",
            (followed_id, floor),
        )

    @pytest.mark.parametrize("via", ["qbittorrent", "", "FOLLOW"])
    def test_a_bad_via_is_refused(self, conn: sqlite3.Connection, via: str) -> None:
        """Only 'follow' and 'request' are vias (QBITTORRENT is K4b's)."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO acquisition_requester (followed_id, account_id, via, since) VALUES (?, 'a', ?, 1)",
                (followed_id, via),
            )

    def test_paused_is_a_boolean(self, conn: sqlite3.Connection) -> None:
        """The paused flag is 0 or 1."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO acquisition_requester (followed_id, account_id, via, paused, since) "
                "VALUES (?, 'a', 'follow', 2, 1)",
                (followed_id,),
            )

    def test_one_requester_row_per_account_and_follow(self, conn: sqlite3.Connection) -> None:
        """(followed_id, account_id) is the primary key."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        row = "INSERT INTO acquisition_requester (followed_id, account_id, via, since) VALUES (?, 'a', 'follow', 1)"
        conn.execute(row, (followed_id,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(row, (followed_id,))

    def test_a_bad_scope_is_refused(self, conn: sqlite3.Connection) -> None:
        """Only 'follow' and 'request' are scopes."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE followed_series SET scope = 'other' WHERE id = ?", (followed_id,))

    def test_a_request_scope_is_accepted(self, conn: sqlite3.Connection) -> None:
        """A one-off request is a followed_series row with scope 'request' (O-2 A)."""
        followed_id, _ = _seed_follow_and_wanted(conn)
        conn.execute("UPDATE followed_series SET scope = 'request' WHERE id = ?", (followed_id,))
        assert conn.execute("SELECT scope FROM followed_series").fetchone()[0] == "request"

    @pytest.mark.parametrize("trigger", ["manual", "automatic", None])
    def test_a_good_trigger_is_accepted(self, conn: sqlite3.Connection, trigger: str | None) -> None:
        """manual, automatic, and NULL (unknown) are triggers."""
        _, wanted_id = _seed_follow_and_wanted(conn)
        conn.execute("UPDATE wanted SET trigger = ? WHERE id = ?", (trigger, wanted_id))

    def test_a_bad_trigger_is_refused(self, conn: sqlite3.Connection) -> None:
        """Only manual and automatic name a trigger."""
        _, wanted_id = _seed_follow_and_wanted(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("UPDATE wanted SET trigger = 'cli' WHERE id = ?", (wanted_id,))

    def test_one_candidate_per_rank_of_a_wanted_row(self, conn: sqlite3.Connection) -> None:
        """(wanted_id, rank) is the primary key."""
        _, wanted_id = _seed_follow_and_wanted(conn)
        row = (
            "INSERT INTO wanted_candidate (wanted_id, rank, provider, title, size_bytes, seeders, score, searched_at) "
            "VALUES (?, 1, 'c411', 't', 1, 1, 1, 1)"
        )
        conn.execute(row, (wanted_id,))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(row, (wanted_id,))
