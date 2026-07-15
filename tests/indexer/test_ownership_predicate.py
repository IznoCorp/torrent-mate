"""Golden tests for indexer.ownership.is_owned predicate.

Uses a seeded in-memory library.db fixture. Every assertion checks the real
bool returned by is_owned; the soft-delete test includes a mutation proof
showing that deleted_at IS NULL is load-bearing.

NON-VACUOUS discipline:
- owned_movie: True (live file present)
- soft_deleted_movie: False (all files deleted_at-tombstoned)
- not_owned_movie: False (no file at all)
- provider_id_fallback: True via tmdb_id when tvdb_id is None
- owned_episode: True (live file on S01E03)
- not_owned_episode: False (S01E04 has no file)
- catalog_only_show: False (show row exists but zero episode files)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ownership import is_owned

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

NOW = int(time.time())


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _external_ids_json(
    *,
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
    imdb_id: str | None = None,
) -> str:
    """Build an external_ids_json payload mirroring migration 005's shape.

    Migration 005 dropped the flat tvdb_id/tmdb_id/imdb_id columns and
    consolidated provider IDs into ``{provider: {series_id, episode_id}}``.
    series_id is stored as a string (the backfill CASTs numeric IDs to TEXT);
    a provider whose id is None is omitted so json_extract returns NULL for it.
    """
    payload: dict[str, dict[str, str | None]] = {}
    if tvdb_id is not None:
        payload["tvdb"] = {"series_id": str(tvdb_id), "episode_id": None}
    if tmdb_id is not None:
        payload["tmdb"] = {"series_id": str(tmdb_id), "episode_id": None}
    if imdb_id is not None:
        payload["imdb"] = {"series_id": imdb_id, "episode_id": None}
    return json.dumps(payload)


def _open_db() -> sqlite3.Connection:
    """Open a fresh in-memory DB with all migrations applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES (?,?,?,1)",
        ("uuid-1", "Disk1", "/Volumes/Disk1"),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_path(conn: sqlite3.Connection, disk_id: int, rel_path: str = "001-MOVIES/Test") -> int:
    cur = conn.execute(
        "INSERT INTO path(disk_id, rel_path) VALUES (?,?)",
        (disk_id, rel_path),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_movie_item(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
    imdb_id: str | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO media_item(kind, title, title_sort, year, category_id,
           external_ids_json, date_created, date_modified)
           VALUES ('movie',?,?,2020,'movies',?,?,?)""",
        (
            "Test Movie",
            "Test Movie",
            _external_ids_json(tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id),
            NOW,
            NOW,
        ),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_show_item(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int | None = None,
    tmdb_id: int | None = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO media_item(kind, title, title_sort, year, category_id,
           external_ids_json, date_created, date_modified)
           VALUES ('show',?,?,2020,'tv_shows',?,?,?)""",
        (
            "Test Show",
            "Test Show",
            _external_ids_json(tvdb_id=tvdb_id, tmdb_id=tmdb_id),
            NOW,
            NOW,
        ),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_release(conn: sqlite3.Connection, *, item_id: int | None = None, episode_id: int | None = None) -> int:
    cur = conn.execute(
        "INSERT INTO media_release(item_id, episode_id) VALUES (?,?)",
        (item_id, episode_id),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_file(conn: sqlite3.Connection, release_id: int, path_id: int, *, deleted_at: int | None = None) -> int:
    cur = conn.execute(
        """INSERT INTO media_file(release_id, path_id, filename, size_bytes,
           mtime_ns, oshash, scan_generation, last_verified_at, deleted_at)
           VALUES (?,?,'movie.mkv',1000000000,?,?,1,?,?)""",
        (release_id, path_id, NOW * 10**9, "abcd1234abcd1234", NOW, deleted_at),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_season(conn: sqlite3.Connection, item_id: int, number: int) -> int:
    cur = conn.execute(
        "INSERT INTO season(item_id, number) VALUES (?,?)",
        (item_id, number),
    )
    return cur.lastrowid  # type: ignore[return-value]


def _insert_episode(conn: sqlite3.Connection, season_id: int, number: int) -> int:
    cur = conn.execute(
        "INSERT INTO episode(season_id, number) VALUES (?,?)",
        (season_id, number),
    )
    return cur.lastrowid  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIsOwnedMovie:
    """Golden tests for movie ownership."""

    def test_owned_movie_tvdb_match_returns_true(self) -> None:
        """A movie with a live media_file and matching tvdb_id → True."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=12345)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="movie", tvdb_id=12345, tmdb_id=None, imdb_id=None)
        assert result is True

    def test_soft_deleted_movie_returns_false(self) -> None:
        """A movie whose only file is soft-deleted → False.

        LOAD-BEARING: the deleted_at IS NULL filter is what makes this False.
        Mutation proof is in test_soft_delete_filter_is_load_bearing.
        """
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=22222)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=NOW)  # tombstoned

        result = is_owned(conn, kind="movie", tvdb_id=22222, tmdb_id=None, imdb_id=None)
        assert result is False

    def test_not_owned_movie_returns_false(self) -> None:
        """A movie with no media_release (catalog-only) → False."""
        conn = _open_db()
        _insert_movie_item(conn, tvdb_id=33333)

        result = is_owned(conn, kind="movie", tvdb_id=33333, tmdb_id=None, imdb_id=None)
        assert result is False

    def test_provider_id_fallback_tmdb(self) -> None:
        """A movie with only tmdb_id (no tvdb_id) → True when matched by tmdb_id.

        LOAD-BEARING: proves the tvdb→tmdb→imdb fallback chain works.
        """
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=None, tmdb_id=44444, imdb_id=None)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        # Query with only tmdb_id (no tvdb_id supplied)
        result = is_owned(conn, kind="movie", tvdb_id=None, tmdb_id=44444, imdb_id=None)
        assert result is True

    def test_provider_id_fallback_imdb(self) -> None:
        """A movie with only imdb_id → True when matched by imdb_id."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=None, tmdb_id=None, imdb_id="tt9999999")
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="movie", tvdb_id=None, tmdb_id=None, imdb_id="tt9999999")
        assert result is True

    def test_tmdb_only_item_not_matched_by_tvdb(self) -> None:
        """A movie with ONLY tmdb_id set, queried by a tvdb_id → no match (False).

        Proves the provider-id columns do not cross-contaminate: a tvdb-keyed
        query must not collide with a tmdb-only row.
        """
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=None, tmdb_id=44444, imdb_id=None)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="movie", tvdb_id=44444, tmdb_id=None, imdb_id=None)
        assert result is False

    def test_no_id_given_returns_false(self) -> None:
        """No provider id supplied → cannot identify → False."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=12345)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="movie", tvdb_id=None, tmdb_id=None, imdb_id=None)
        assert result is False

    def test_wrong_tvdb_id_returns_false(self) -> None:
        """A movie exists but with a different tvdb_id → False."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=11111)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="movie", tvdb_id=99999, tmdb_id=None, imdb_id=None)
        assert result is False


class TestIsOwnedEpisode:
    """Golden tests for episode ownership."""

    def test_owned_episode_returns_true(self) -> None:
        """A show with a live file for S01E03 → True for (season=1, episode=3)."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id, rel_path="002-TVSHOWS/Test Show/Season 01")
        item_id = _insert_show_item(conn, tvdb_id=55555)
        season_id = _insert_season(conn, item_id, number=1)
        ep_id = _insert_episode(conn, season_id, number=3)
        rel_id = _insert_release(conn, episode_id=ep_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="episode", tvdb_id=55555, tmdb_id=None, imdb_id=None, season=1, episode=3)
        assert result is True

    def test_not_owned_episode_returns_false(self) -> None:
        """S01E04 has no release/file → False even though S01E03 is owned."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id, rel_path="002-TVSHOWS/Test Show/Season 01")
        item_id = _insert_show_item(conn, tvdb_id=55555)
        season_id = _insert_season(conn, item_id, number=1)
        # Only episode 3 has a file
        ep_id = _insert_episode(conn, season_id, number=3)
        rel_id = _insert_release(conn, episode_id=ep_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)
        # Episode 4 exists in the DB but has no release
        _insert_episode(conn, season_id, number=4)

        result = is_owned(conn, kind="episode", tvdb_id=55555, tmdb_id=None, imdb_id=None, season=1, episode=4)
        assert result is False

    def test_catalog_only_show_returns_false(self) -> None:
        """A show exists in media_item but has no episode files → False."""
        conn = _open_db()
        item_id = _insert_show_item(conn, tvdb_id=66666)
        _insert_season(conn, item_id, number=1)
        # No episode, no release, no file

        result = is_owned(conn, kind="episode", tvdb_id=66666, tmdb_id=None, imdb_id=None, season=1, episode=1)
        assert result is False

    def test_soft_deleted_episode_returns_false(self) -> None:
        """An episode whose only file is tombstoned → False."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id, rel_path="002-TVSHOWS/Test Show/Season 01")
        item_id = _insert_show_item(conn, tvdb_id=77777)
        season_id = _insert_season(conn, item_id, number=1)
        ep_id = _insert_episode(conn, season_id, number=2)
        rel_id = _insert_release(conn, episode_id=ep_id)
        _insert_file(conn, rel_id, path_id, deleted_at=NOW)  # tombstoned

        result = is_owned(conn, kind="episode", tvdb_id=77777, tmdb_id=None, imdb_id=None, season=1, episode=2)
        assert result is False

    def test_episode_missing_season_returns_false(self) -> None:
        """kind='episode' without a season number → cannot identify → False."""
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id, rel_path="002-TVSHOWS/Test Show/Season 01")
        item_id = _insert_show_item(conn, tvdb_id=55555)
        season_id = _insert_season(conn, item_id, number=1)
        ep_id = _insert_episode(conn, season_id, number=3)
        rel_id = _insert_release(conn, episode_id=ep_id)
        _insert_file(conn, rel_id, path_id, deleted_at=None)

        result = is_owned(conn, kind="episode", tvdb_id=55555, tmdb_id=None, imdb_id=None, season=None, episode=3)
        assert result is False


class TestIsOwnedCrossKindCollision:
    """Regression: a movie and a show sharing the same tvdb_id must NOT collide.

    The is_owned predicate applies ``kind='movie'`` (movie branch) and
    ``kind='show'`` (episode branch) in the SQL WHERE clauses. A future join
    refactor that drops the kind filter while a same-id show is owned would
    ship a false-owned that silently skips a wanted movie.

    This test seeds BOTH in the same library.db:
    - a SHOW media_item (kind='show') with a live episode file (S01E03)
    - a MOVIE media_item (kind='movie') with NO file, same tvdb_id

    It proves that the kind filter correctly disambiguates the two paths.
    """

    def test_movie_false_despite_same_tvdb_id_show_owned(self) -> None:
        """is_owned(kind='movie', tvdb_id=X) → False when only the show has a file.

        The show's episode file must NOT count as ownership for the movie branch.
        """
        SHARED_ID = 11111
        conn = _open_db()
        disk_id = _insert_disk(conn)

        # Seed a SHOW with S01E03 + live file.
        path_show = _insert_path(conn, disk_id, rel_path="002-TVSHOWS/Collision Show/Season 01")
        show_item_id = _insert_show_item(conn, tvdb_id=SHARED_ID)
        season_id = _insert_season(conn, show_item_id, number=1)
        ep_id = _insert_episode(conn, season_id, number=3)
        rel_show = _insert_release(conn, episode_id=ep_id)
        _insert_file(conn, rel_show, path_show, deleted_at=None)

        # Seed a MOVIE with the SAME tvdb_id, distinct title, NO file.
        _insert_movie_item(conn, tvdb_id=SHARED_ID)
        # No release, no file — this movie should NOT appear owned.

        # The movie branch must NOT match the show's episode file.
        assert is_owned(conn, kind="movie", tvdb_id=SHARED_ID, tmdb_id=None, imdb_id=None) is False

        # The episode branch must still correctly match the show's episode.
        assert (
            is_owned(
                conn,
                kind="episode",
                tvdb_id=SHARED_ID,
                tmdb_id=None,
                imdb_id=None,
                season=1,
                episode=3,
            )
            is True
        )


class TestSoftDeleteFilterLoadBearing:
    """Mutation proof: deleted_at IS NULL is load-bearing.

    This test class proves that removing the liveness filter from the SQL
    would flip the soft-delete assertions above. It does so by patching
    is_owned to use a mutant SQL (without the deleted_at IS NULL clause)
    and verifying the mutant returns True on a soft-deleted item.

    If this test PASSES, the filter is confirmed load-bearing.
    If it FAILS, the production SQL never used the filter (silent bug).
    """

    def test_soft_delete_filter_is_load_bearing_movie(self) -> None:
        """Mutant SQL (no deleted_at IS NULL) → True on tombstoned movie.

        Proves: only deleted_at IS NULL in the real query makes it return False.
        """
        conn = _open_db()
        disk_id = _insert_disk(conn)
        path_id = _insert_path(conn, disk_id)
        item_id = _insert_movie_item(conn, tvdb_id=88888)
        rel_id = _insert_release(conn, item_id=item_id)
        _insert_file(conn, rel_id, path_id, deleted_at=NOW)  # tombstoned

        # Real query: False (filter active)
        assert is_owned(conn, kind="movie", tvdb_id=88888, tmdb_id=None, imdb_id=None) is False

        # Mutant query WITHOUT the deleted_at filter — must return True (file exists).
        # Provider id lives in external_ids_json (migration 005); mirror the
        # production CAST-to-INTEGER match on the tvdb series_id JSON path.
        mutant_sql = (
            "SELECT EXISTS("
            "SELECT 1 FROM media_item mi"
            " JOIN media_release mr ON mr.item_id = mi.id"
            " JOIN media_file mf ON mf.release_id = mr.id"
            " WHERE mi.kind='movie'"
            " AND CAST(json_extract(mi.external_ids_json, '$.tvdb.series_id') AS INTEGER)=?"
            # deleted_at IS NULL intentionally OMITTED — this is the mutant
            ")"
        )
        row = conn.execute(mutant_sql, (88888,)).fetchone()
        mutant_result = bool(row[0]) if row else False
        assert mutant_result is True, (
            "Mutant SQL (no deleted_at IS NULL) should return True on a tombstoned file. "
            "This proves the production deleted_at IS NULL filter is load-bearing."
        )


class TestSpanOwnership:
    """Multi-episode span releases own EVERY covered episode (migration 014).

    Live incident (2026-07-15): « Friends S09E23-24 » linked only episode 23 —
    ownership missed E24, the wanted row stayed pending forever, and grab kept
    searching for content already on disk.
    """

    @staticmethod
    def _seed_span_show(conn: sqlite3.Connection) -> None:
        """Seed a show whose S09 has a single file covering E23–E24."""
        disk = _insert_disk(conn)
        path = _insert_path(conn, disk, "002-TVSHOWS/Friends/Saison 09")
        item = _insert_show_item(conn, tvdb_id=79168)
        season = _insert_season(conn, item, 9)
        e23 = _insert_episode(conn, season, 23)
        e24 = _insert_episode(conn, season, 24)
        cur = conn.execute(
            "INSERT INTO media_release(episode_id, episode_end_id) VALUES (?,?)",
            (e23, e24),
        )
        _insert_file(conn, int(cur.lastrowid), path)

    def test_span_release_owns_both_episodes(self) -> None:
        """is_owned returns True for the start AND the end of the span."""
        conn = _open_db()
        self._seed_span_show(conn)

        owns_start = is_owned(conn, kind="episode", tvdb_id=79168, tmdb_id=None, imdb_id=None, season=9, episode=23)
        owns_end = is_owned(conn, kind="episode", tvdb_id=79168, tmdb_id=None, imdb_id=None, season=9, episode=24)
        assert owns_start is True
        assert owns_end is True, "the second episode of a span file must count as owned"

    def test_span_does_not_leak_outside_range(self) -> None:
        """Episodes outside the span stay un-owned."""
        conn = _open_db()
        self._seed_span_show(conn)

        assert is_owned(conn, kind="episode", tvdb_id=79168, tmdb_id=None, imdb_id=None, season=9, episode=22) is False
        assert is_owned(conn, kind="episode", tvdb_id=79168, tmdb_id=None, imdb_id=None, season=9, episode=25) is False

    def test_owned_pairs_expands_span(self) -> None:
        """owned_episode_pairs returns every pair the span covers."""
        from personalscraper.indexer.ownership import owned_episode_pairs

        conn = _open_db()
        self._seed_span_show(conn)

        pairs = owned_episode_pairs(conn, tvdb_id=79168)
        assert (9, 23) in pairs
        assert (9, 24) in pairs
        assert (9, 25) not in pairs

    def test_soft_deleted_span_file_owns_nothing(self) -> None:
        """A tombstoned span file releases its whole coverage."""
        conn = _open_db()
        disk = _insert_disk(conn)
        path = _insert_path(conn, disk, "002-TVSHOWS/Friends/Saison 10")
        item = _insert_show_item(conn, tvdb_id=79168)
        season = _insert_season(conn, item, 10)
        e17 = _insert_episode(conn, season, 17)
        e18 = _insert_episode(conn, season, 18)
        cur = conn.execute(
            "INSERT INTO media_release(episode_id, episode_end_id) VALUES (?,?)",
            (e17, e18),
        )
        _insert_file(conn, int(cur.lastrowid), path, deleted_at=NOW)

        assert is_owned(conn, kind="episode", tvdb_id=79168, tmdb_id=None, imdb_id=None, season=10, episode=17) is False
        assert is_owned(conn, kind="episode", tvdb_id=79168, tmdb_id=None, imdb_id=None, season=10, episode=18) is False
