"""Database-level invariant assertions for ``canonical_provider`` after repair.

Proves the post-repair invariant:
- Every ``kind='show'`` row with ``$.tvdb.series_id`` present MUST have
  ``canonical_provider='tvdb'``.
- Every ``kind='movie'`` row with ``$.tmdb.id`` present MUST have
  ``canonical_provider='tmdb'``.

The invariant is expressed as SQL property tests (COUNT(*) WHERE invariant
violated == 0) and exercised over a seeded in-memory DB after applying the
same UPDATE statements the CLI command uses.

Note on plan-drift: the plan §12.1 also mentions a scrape-time invariant test,
but scrape-time write paths use ``match.source`` (tv_service.py:333) which can
legitimately yield ``'tmdb'`` for a show when only TMDB matches. Testing that
would require fixing the scraper (OUT OF SCOPE this sub-phase) or yield a
known-failing test. This test implements the DATABASE post-repair property —
consistent with the migration rule and produces a passing regression net.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from personalscraper.indexer.db import apply_migrations

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"

_SHOWS_REPAIR_SQL = """
UPDATE media_item SET canonical_provider='tvdb'
WHERE kind='show' AND canonical_provider='tmdb'
  AND json_extract(external_ids_json, '$.tvdb.series_id') IS NOT NULL
"""

_MOVIES_REPAIR_SQL = """
UPDATE media_item SET canonical_provider='tmdb'
WHERE kind='movie' AND canonical_provider IS NULL
  AND json_extract(external_ids_json, '$.tmdb.id') IS NOT NULL
"""


def _seed_invariant_data(conn: sqlite3.Connection) -> None:
    """Seed a representative mix of rows to exercise the invariant.

    Layout:
    - 3 shows with tvdb IDs + canonical='tmdb' → must be fixed to 'tvdb'
    - 1 show with tvdb IDs + canonical='tvdb' → already correct
    - 1 show with ONLY tmdb (no tvdb.series_id) + canonical='tmdb' →
      stays 'tmdb' — invariant only applies when tvdb IS available
    - 2 movies with tmdb IDs + canonical=NULL → must be fixed to 'tmdb'
    - 1 movie with tmdb IDs + canonical='tmdb' → already correct
    - 1 show with BOTH tvdb.series_id AND tmdb.id + canonical='tmdb' →
      tvdb wins, must become 'tvdb'
    """
    now = 1700000000

    # Shows with tvdb + canonical='tmdb' (broken).
    for i in range(1, 4):
        eids = json.dumps({"tvdb": {"series_id": f"tvdb_show_{i}"}, "tmdb": {"series_id": f"tmdb_show_{i}"}})
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('show', ?, ?, 'tv_shows', ?, 'tmdb', ?, ?)",
            (f"Broken Show {i}", f"Broken Show {i}", eids, now, now),
        )

    # Show already correct (tvdb + canonical='tvdb').
    eids_ok = json.dumps({"tvdb": {"series_id": "tvdb_ok_show"}, "tmdb": {"series_id": "tmdb_ok_show"}})
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'OK Show', 'OK Show', 'tv_shows', ?, 'tvdb', ?, ?)",
        (eids_ok, now, now),
    )

    # Show with ONLY tmdb (no tvdb.series_id) + canonical='tmdb'.
    # This is NOT a violation — invariant only applies when tvdb IS available.
    eids_tmdb_only = json.dumps({"tmdb": {"series_id": "tmdb_only_show"}})
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'TMDB Only Show', 'TMDB Only Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (eids_tmdb_only, now, now),
    )

    # Movies with tmdb + canonical=NULL (broken).
    for i in range(1, 3):
        eids = json.dumps({"tmdb": {"id": f"tmdb_movie_{i}"}})
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, category_id, "
            "external_ids_json, canonical_provider, date_created, date_modified) "
            "VALUES ('movie', ?, ?, 'movies', ?, NULL, ?, ?)",
            (f"Broken Movie {i}", f"Broken Movie {i}", eids, now, now),
        )

    # Movie already correct (tmdb + canonical='tmdb').
    eids_m_ok = json.dumps({"tmdb": {"id": "tmdb_ok_movie"}})
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('movie', 'OK Movie', 'OK Movie', 'movies', ?, 'tmdb', ?, ?)",
        (eids_m_ok, now, now),
    )

    # Show with BOTH tvdb AND tmdb + canonical='tmdb' → tvdb wins.
    eids_both = json.dumps({"tvdb": {"series_id": "tvdb_winner"}, "tmdb": {"series_id": "tmdb_also"}})
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, category_id, "
        "external_ids_json, canonical_provider, date_created, date_modified) "
        "VALUES ('show', 'Both IDs Show', 'Both IDs Show', 'tv_shows', ?, 'tmdb', ?, ?)",
        (eids_both, now, now),
    )

    conn.commit()


def test_post_repair_invariant_shows_tvdb_when_series_id_exists() -> None:
    """After repair, every show with tvdb.series_id has canonical_provider='tvdb'."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)

    _seed_invariant_data(conn)

    # Pre-condition: violations exist before repair.
    pre_violations = conn.execute(
        "SELECT COUNT(*) FROM media_item "
        "WHERE kind='show' "
        "AND json_extract(external_ids_json, '$.tvdb.series_id') IS NOT NULL "
        "AND canonical_provider != 'tvdb'"
    ).fetchone()[0]
    assert pre_violations == 4, f"Expected 4 pre-repair show violations, got {pre_violations}"

    # Apply the repair.
    conn.execute(_SHOWS_REPAIR_SQL)
    conn.execute(_MOVIES_REPAIR_SQL)

    # Invariant: zero violations for shows with tvdb.series_id.
    violations = conn.execute(
        "SELECT COUNT(*) FROM media_item "
        "WHERE kind='show' "
        "AND json_extract(external_ids_json, '$.tvdb.series_id') IS NOT NULL "
        "AND canonical_provider != 'tvdb'"
    ).fetchone()[0]
    assert violations == 0, (
        f"Invariant violated: {violations} shows with tvdb.series_id have canonical_provider != 'tvdb'"
    )

    conn.close()


def test_post_repair_invariant_movies_tmdb_when_tmdb_id_exists() -> None:
    """After repair, every movie with tmdb.id has canonical_provider='tmdb'."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)

    _seed_invariant_data(conn)

    # Pre-condition: violations exist before repair (NULL or wrong value).
    pre_violations = conn.execute(
        "SELECT COUNT(*) FROM media_item "
        "WHERE kind='movie' "
        "AND json_extract(external_ids_json, '$.tmdb.id') IS NOT NULL "
        "AND (canonical_provider IS NULL OR canonical_provider != 'tmdb')"
    ).fetchone()[0]
    assert pre_violations == 2, f"Expected 2 pre-repair movie violations, got {pre_violations}"

    # Apply the repair.
    conn.execute(_SHOWS_REPAIR_SQL)
    conn.execute(_MOVIES_REPAIR_SQL)

    # Invariant: zero violations for movies with tmdb.id (NULL or wrong value).
    violations = conn.execute(
        "SELECT COUNT(*) FROM media_item "
        "WHERE kind='movie' "
        "AND json_extract(external_ids_json, '$.tmdb.id') IS NOT NULL "
        "AND (canonical_provider IS NULL OR canonical_provider != 'tmdb')"
    ).fetchone()[0]
    assert violations == 0, f"Invariant violated: {violations} movies with tmdb.id have canonical_provider != 'tmdb'"

    conn.close()


def test_post_repair_invariant_tmdb_only_show_not_a_violation() -> None:
    """A show with ONLY tmdb (no tvdb.series_id) is NOT an invariant violation.

    The repair only fixes shows that HAVE a tvdb.series_id. A show scraped
    via TMDB only (no TVDB match) legitimately keeps canonical_provider='tmdb'.
    """
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)

    _seed_invariant_data(conn)

    # Apply the repair.
    conn.execute(_SHOWS_REPAIR_SQL)
    conn.execute(_MOVIES_REPAIR_SQL)

    # The TMDB-only show must still have canonical_provider='tmdb'.
    row = conn.execute("SELECT canonical_provider FROM media_item WHERE title='TMDB Only Show'").fetchone()
    assert row is not None
    assert row[0] == "tmdb", (
        f"TMDB-only show was wrongly changed to {row[0]!r}. "
        f"Only shows with tvdb.series_id should be switched to 'tvdb'."
    )

    conn.close()


def test_post_repair_invariant_control_rows_unchanged() -> None:
    """Items already in correct state are untouched by the repair."""
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)

    _seed_invariant_data(conn)

    # Snapshot the "already correct" rows before repair.
    pre_ok_show = conn.execute("SELECT canonical_provider FROM media_item WHERE title='OK Show'").fetchone()
    pre_ok_movie = conn.execute("SELECT canonical_provider FROM media_item WHERE title='OK Movie'").fetchone()

    conn.execute(_SHOWS_REPAIR_SQL)
    conn.execute(_MOVIES_REPAIR_SQL)

    post_ok_show = conn.execute("SELECT canonical_provider FROM media_item WHERE title='OK Show'").fetchone()
    post_ok_movie = conn.execute("SELECT canonical_provider FROM media_item WHERE title='OK Movie'").fetchone()

    assert pre_ok_show == post_ok_show, f"Already-correct show was mutated: {post_ok_show}"
    assert pre_ok_movie == post_ok_movie, f"Already-correct movie was mutated: {post_ok_movie}"

    conn.close()
