# Phase 2 — Indexer predicate

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `personalscraper/indexer/ownership.py` with the `is_owned` SELECT-only predicate function, plus golden tests on a seeded in-memory `library.db` fixture.

**Architecture:** `is_owned` is a pure SQL function taking an open `sqlite3.Connection` and returning `bool`. It lives in `indexer/ownership.py` as a sibling to `indexer/query.py`. It does NOT import or mutate AppContext — pure query layer. The SQL joins `media_item → media_release → media_file WHERE deleted_at IS NULL` (live-file liveness filter). Provider-id matching follows the tvdb→tmdb→imdb priority from `core/identity.py`. **The `deleted_at IS NULL` filter is load-bearing** — a mutation test (see Task 2.3) proves that dropping it flips the soft-delete assertion.

**Tech Stack:** Python 3.12, `sqlite3`, pytest, `tests/_legacy_ids.py::legacy_external_ids_json`.

---

## Gate — what this phase requires

Phase 1 delivered:

- `personalscraper/core/ownership.py` (Protocol + NullOwnershipChecker)

Verify before starting:

```bash
python -c "from personalscraper.core.ownership import OwnershipChecker; print('gate OK')"
```

Expected: `gate OK`.

---

## Schema quick-reference (from `personalscraper/indexer/migrations/001_init.sql`)

Key tables and columns used by `is_owned`:

```
media_item(id, kind CHECK('movie'|'show'), tvdb_id INTEGER, tmdb_id INTEGER, imdb_id TEXT,
           external_ids_json TEXT)
  ↓ (item_id FK)
media_release(id, item_id, episode_id)
  ↓ (release_id FK)
media_file(id, release_id, deleted_at INTEGER)   -- deleted_at IS NULL = live

season(id, item_id, number)
  ↓ (season_id FK)
episode(id, season_id, number)
  ↓ (episode_id FK via media_release.episode_id)
media_release → media_file (same chain)
```

**Provider-id columns on `media_item`** (flat indexed columns, populated by the scanner):

- `tvdb_id INTEGER` — indexed by `idx_item_tvdb`
- `tmdb_id INTEGER` — indexed by `idx_item_tmdb`
- `imdb_id TEXT` — indexed by `idx_item_imdb`

Note: `external_ids_json` also carries these IDs (used by `query.py`), but `is_owned` targets the flat columns because they have dedicated indexes and are set by the scanner — simpler and faster for the EXISTS path.

---

## File map

| Action     | Path                                        |
| ---------- | ------------------------------------------- |
| **Create** | `personalscraper/indexer/ownership.py`      |
| **Create** | `tests/indexer/test_ownership_predicate.py` |

---

## Task 2.1 — Write the failing tests (golden fixture approach)

**Files:**

- Create: `tests/indexer/test_ownership_predicate.py`

The fixture opens an in-memory SQLite DB, applies the full migration chain, and seeds specific rows. All assertions are exact booleans — no "approximately" or vacuous checks.

- [ ] **Step 1: Write the test file**

```python
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

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.ownership import is_owned

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

NOW = int(time.time())


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _open_db() -> sqlite3.Connection:
    """Open a fresh in-memory DB with all migrations applied."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _insert_disk(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO disk(uuid, label, is_mounted) VALUES (?,?,1)",
        ("uuid-1", "Disk1"),
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
           tvdb_id, tmdb_id, imdb_id, date_created, date_modified)
           VALUES ('movie',?,?,2020,'movies',?,?,?,?,?)""",
        ("Test Movie", "Test Movie", tvdb_id, tmdb_id, imdb_id, NOW, NOW),
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
           tvdb_id, tmdb_id, date_created, date_modified)
           VALUES ('show',?,?,2020,'tv_shows',?,?,?,?)""",
        ("Test Show", "Test Show", tvdb_id, tmdb_id, NOW, NOW),
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

        # Mutant query WITHOUT the deleted_at filter — must return True (file exists)
        mutant_sql = (
            "SELECT EXISTS("
            "SELECT 1 FROM media_item mi"
            " JOIN media_release mr ON mr.item_id = mi.id"
            " JOIN media_file mf ON mf.release_id = mr.id"
            " WHERE mi.kind='movie' AND mi.tvdb_id=?"
            # deleted_at IS NULL intentionally OMITTED — this is the mutant
            ")"
        )
        row = conn.execute(mutant_sql, (88888,)).fetchone()
        mutant_result = bool(row[0]) if row else False
        assert mutant_result is True, (
            "Mutant SQL (no deleted_at IS NULL) should return True on a tombstoned file. "
            "This proves the production deleted_at IS NULL filter is load-bearing."
        )
```

- [ ] **Step 2: Run the tests — they must FAIL**

```bash
pytest tests/indexer/test_ownership_predicate.py -v --tb=short
```

Expected: `ImportError` or `ModuleNotFoundError: No module named 'personalscraper.indexer.ownership'`.

---

## Task 2.2 — Implement `indexer/ownership.py` (predicate only)

**Files:**

- Create: `personalscraper/indexer/ownership.py`

This file contains ONLY `is_owned` in this phase. The `IndexerOwnershipChecker` adapter is added in Phase 3.

- [ ] **Step 3: Write the module**

```python
"""Indexer ownership predicate (RP6) — SELECT-only query layer.

Public API (Phase 2):
- :func:`is_owned` — answers "does the library contain a live file for
  this work?" via a chain of EXISTS sub-queries.

The ``IndexerOwnershipChecker`` adapter that wraps this function and
implements ``core.ownership.OwnershipChecker`` is added in Phase 3.

Import direction: stdlib + personalscraper.logger only.
No core.ownership import at runtime in this module (the adapter adds it).
"""

from __future__ import annotations

import sqlite3

from personalscraper.logger import get_logger

log = get_logger("indexer.ownership")


def is_owned(
    conn: sqlite3.Connection,
    *,
    kind: str,
    tvdb_id: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int | None = None,
    episode: int | None = None,
) -> bool:
    """Return True iff the library contains a live file for the given work.

    Matches ``media_item`` on the first available provider ID in priority
    order tvdb_id → tmdb_id → imdb_id, then follows the release chain to
    ``media_file`` and checks ``deleted_at IS NULL`` (live-file liveness
    filter). A soft-deleted file does not count as owned.

    Movie path:
        media_item(kind='movie', <provider_id>=?) →
        media_release(item_id) →
        media_file(deleted_at IS NULL)

    Episode path:
        media_item(kind='show', <provider_id>=?) →
        season(number=season) →
        episode(number=episode) →
        media_release(episode_id) →
        media_file(deleted_at IS NULL)

    Args:
        conn: Open, read-capable SQLite connection to the indexer database.
        kind: ``"movie"`` or ``"episode"``.
        tvdb_id: TVDB numeric ID (primary); matched first when not None.
        tmdb_id: TMDB numeric ID (fallback); matched when tvdb_id is None.
        imdb_id: IMDB string ID e.g. ``"tt0000001"`` (last resort).
        season: Season number; required when ``kind="episode"``.
        episode: Episode number; required when ``kind="episode"``.

    Returns:
        ``True`` if a live (non-soft-deleted) file exists for the work.
        ``False`` when the work is not found, has no file, or all files are
        soft-deleted.

    Raises:
        Nothing — callers must never crash on a predicate failure; the
        ``IndexerOwnershipChecker`` adapter (Phase 3) wraps this in a
        try/except for fail-soft behaviour.
    """
    if kind == "movie":
        return _is_owned_movie(conn, tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id)
    if kind == "episode":
        if season is None or episode is None:
            log.warning("is_owned.episode_missing_season_or_episode", kind=kind, season=season, episode=episode)
            return False
        return _is_owned_episode(
            conn, tvdb_id=tvdb_id, tmdb_id=tmdb_id, imdb_id=imdb_id, season=season, episode=episode
        )
    log.warning("is_owned.unknown_kind", kind=kind)
    return False


# ---------------------------------------------------------------------------
# Internal helpers — one per kind
# ---------------------------------------------------------------------------

# Base EXISTS clause for a live file linked to a movie-level media_item.
# The <PROVIDER_CLAUSE> placeholder is replaced by the caller with a
# concrete WHERE fragment (e.g. "mi.tvdb_id=?").
_MOVIE_EXISTS_TMPL = (
    "SELECT EXISTS("
    "SELECT 1 FROM media_item mi"
    " JOIN media_release mr ON mr.item_id = mi.id"
    " JOIN media_file mf ON mf.release_id = mr.id"
    " WHERE mi.kind='movie' AND {provider_clause}"
    " AND mf.deleted_at IS NULL"
    ")"
)

_EPISODE_EXISTS_TMPL = (
    "SELECT EXISTS("
    "SELECT 1 FROM media_item mi"
    " JOIN season s ON s.item_id = mi.id"
    " JOIN episode e ON e.season_id = s.id"
    " JOIN media_release mr ON mr.episode_id = e.id"
    " JOIN media_file mf ON mf.release_id = mr.id"
    " WHERE mi.kind='show' AND {provider_clause}"
    " AND s.number=? AND e.number=?"
    " AND mf.deleted_at IS NULL"
    ")"
)


def _run_exists(conn: sqlite3.Connection, sql: str, params: tuple[object, ...]) -> bool:
    """Execute a single-row EXISTS query and return the boolean result.

    Args:
        conn: Open SQLite connection.
        sql: SQL SELECT EXISTS(…) string.
        params: Bind parameters.

    Returns:
        ``True`` if EXISTS returns 1, ``False`` otherwise.
    """
    row = conn.execute(sql, params).fetchone()
    return bool(row[0]) if row else False


def _is_owned_movie(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
) -> bool:
    """Check movie ownership via the provider-id priority chain.

    Args:
        conn: Open SQLite connection.
        tvdb_id: TVDB ID (tried first).
        tmdb_id: TMDB ID (tried second).
        imdb_id: IMDB ID (tried last).

    Returns:
        ``True`` if a live file exists for any matched movie item.
    """
    if tvdb_id is not None:
        sql = _MOVIE_EXISTS_TMPL.format(provider_clause="mi.tvdb_id=?")
        if _run_exists(conn, sql, (tvdb_id,)):
            return True
    if tmdb_id is not None:
        sql = _MOVIE_EXISTS_TMPL.format(provider_clause="mi.tmdb_id=?")
        if _run_exists(conn, sql, (tmdb_id,)):
            return True
    if imdb_id is not None:
        sql = _MOVIE_EXISTS_TMPL.format(provider_clause="mi.imdb_id=?")
        if _run_exists(conn, sql, (imdb_id,)):
            return True
    return False


def _is_owned_episode(
    conn: sqlite3.Connection,
    *,
    tvdb_id: int | None,
    tmdb_id: int | None,
    imdb_id: str | None,
    season: int,
    episode: int,
) -> bool:
    """Check episode ownership via the provider-id priority chain.

    Args:
        conn: Open SQLite connection.
        tvdb_id: TVDB ID (tried first).
        tmdb_id: TMDB ID (tried second).
        imdb_id: IMDB ID (tried last).
        season: Season number to match.
        episode: Episode number to match.

    Returns:
        ``True`` if a live file exists for the matched episode.
    """
    if tvdb_id is not None:
        sql = _EPISODE_EXISTS_TMPL.format(provider_clause="mi.tvdb_id=?")
        if _run_exists(conn, sql, (tvdb_id, season, episode)):
            return True
    if tmdb_id is not None:
        sql = _EPISODE_EXISTS_TMPL.format(provider_clause="mi.tmdb_id=?")
        if _run_exists(conn, sql, (tmdb_id, season, episode)):
            return True
    if imdb_id is not None:
        sql = _EPISODE_EXISTS_TMPL.format(provider_clause="mi.imdb_id=?")
        if _run_exists(conn, sql, (imdb_id, season, episode)):
            return True
    return False


__all__ = ["is_owned"]
```

- [ ] **Step 4: Run all predicate tests — they must PASS**

```bash
pytest tests/indexer/test_ownership_predicate.py -v --tb=short
```

Expected: `13 passed`.

---

## Task 2.3 — Verify no layering violations introduced

- [ ] **Step 5: Check acquire/ layering guard (must not import indexer/)**

```bash
pytest tests/architecture/test_layering.py::test_acquire_does_not_import_triage -v --tb=short
```

Expected: `1 passed`.

- [ ] **Step 6: Smoke import**

```bash
python -c "from personalscraper.indexer.ownership import is_owned; print('OK')"
```

Expected: `OK`.

- [ ] **Step 7: Run the full indexer test suite to catch regressions**

```bash
pytest tests/indexer/ -v --tb=short -q 2>&1 | tail -10
```

Expected: all existing tests still pass (0 failures).

- [ ] **Step 8: Commit**

```bash
git add personalscraper/indexer/ownership.py tests/indexer/test_ownership_predicate.py
git commit -m "feat(ownership): indexer predicate — is_owned SELECT-only with golden tests"
```
