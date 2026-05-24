"""Regression test for ``_upsert_media_item`` dedup logic (DEV #53).

Covers the scenario where stored ``media_item.title`` contains a trailing
`` (YYYY)`` suffix (from a directory name like ``Inception (2010)``) while
the upsert caller passes a cleaned title, or vice-versa.  Before the fix,
exact-match ``WHERE title = ?`` failed → a duplicate row was inserted.

Also tests migration 007 forward-apply: canonicalisation of existing rows,
dedup of post-canonicalisation collisions, and the UNIQUE constraint.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.schema import MediaItemKind, MediaItemRow

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with all migrations applied (including 007).

    Returns:
        An open :class:`sqlite3.Connection`.
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, _MIGRATIONS_DIR)
    return c


def _make_item(
    title: str = "Test Item",
    kind: MediaItemKind = "movie",
    year: int | None = 2024,
    category_id: str = "movies",
) -> MediaItemRow:
    """Return a minimal :class:`MediaItemRow`.

    Args:
        title: Display title to store.
        kind: ``'movie'`` or ``'show'``.
        year: Release year; ``None`` if unknown.
        category_id: Logical category from config.

    Returns:
        Populated :class:`MediaItemRow` ready for insertion.
    """
    now = int(time.time())
    return MediaItemRow(
        id=0,
        kind=kind,
        title=title,
        title_sort=title,
        original_title=None,
        year=year,
        category_id=category_id,
        external_ids_json="{}",
        ratings_json=None,
        canonical_provider=None,
        nfo_status=None,
        artwork_json=None,
        date_created=now,
        date_modified=now,
        date_metadata_refreshed=None,
        is_locked=0,
        preferred_lang="fr",
    )


# ---------------------------------------------------------------------------
# Core dedup scenarios
# ---------------------------------------------------------------------------


def test_upsert_with_year_suffix_matches_clean_title(conn: sqlite3.Connection) -> None:
    """Upsert with ``title="Foo (2020)"`` matches stored ``title="Foo"``."""
    # Seed: insert a row with clean title.
    item_repo.insert(conn, _make_item(title="Foo", year=2020))

    # Upsert: same kind, title WITH year suffix.
    row = _make_item(title="Foo (2020)", year=2020)
    item_id = item_repo.upsert(conn, row)

    # Must be the SAME row (updated), not a new one.
    count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
    assert count == 1, f"Expected 1 row, got {count} (duplicate created)"
    assert item_id == 1

    # Stored title must be canonicalised.
    stored = item_repo.get_by_id(conn, item_id)
    assert stored is not None
    assert stored.title == "Foo"


def test_upsert_with_clean_title_matches_year_suffix_stored(tmp_path: Path) -> None:
    """Upsert with ``title="Bar"`` matches stored ``title="Bar (2019)"`` after migration 007.

    Simulates the real-world flow: a pre-migration DB has a row with a year-suffix
    title.  Migration 007 canonicalises it.  The code fix then makes upsert with
    a clean title find and UPDATE the canonicalised row.
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    # Phase 1 — simulate pre-migration state: apply 001–006, insert a
    # year-suffix row (the buggy legacy state).
    _apply_through_migration(conn, up_to_version=6)
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "external_ids_json, date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Bar (2019)', 'Bar (2019)', 2019, 'movies', '{}', 1, 1, 0, 'fr')"
    )
    conn.commit()

    # Phase 2 — apply migration 007 (canonicalises the stored title).
    apply_migrations(conn, _MIGRATIONS_DIR)

    # Verify canonicalisation happened.
    row = conn.execute("SELECT title FROM media_item WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "Bar", f"Migration 007 should have canonicalised, got {row[0]!r}"

    # Phase 3 — now call upsert with a clean title.  Must UPDATE, not INSERT.
    item = _make_item(title="Bar", year=2019)
    result_id = item_repo.upsert(conn, item)
    assert result_id == 1  # the existing row, not a new one

    count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
    assert count == 1, f"Expected 1 row, got {count} (duplicate created)"

    conn.close()


def test_upsert_different_titles_with_different_years_no_collision(
    conn: sqlite3.Connection,
) -> None:
    """Two movies with different base titles must NOT collide."""
    item_repo.insert(conn, _make_item(title="Alpha (2020)", year=2020))
    item_repo.insert(conn, _make_item(title="Beta (2020)", year=2020))

    count = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
    assert count == 2, f"Expected 2 distinct rows, got {count}"


def test_upsert_same_title_different_kind_no_collision(conn: sqlite3.Connection) -> None:
    """Same title with different kind (movie vs show) must NOT collide."""
    item_repo.insert(conn, _make_item(title="Foo", kind="movie"))
    item_repo.insert(conn, _make_item(title="Foo", kind="show"))

    count_movies = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'movie'").fetchone()[0]
    count_shows = conn.execute("SELECT COUNT(*) FROM media_item WHERE kind = 'show'").fetchone()[0]
    assert count_movies == 1
    assert count_shows == 1


# ---------------------------------------------------------------------------
# UNIQUE constraint enforcement
# ---------------------------------------------------------------------------


def test_migration_007_glob_rejects_non_digit_suffix(tmp_path: Path) -> None:
    """CR-1: GLOB '* ([0-9][0-9][0-9][0-9])' must NOT match ``Movie (abcd)``."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    # Seed a row with a non-digit 4-char suffix — must NOT be canonicalised.
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Movie (abcd)', 'Movie (abcd)', 2020, 'movies', 1, 1, 0, 'fr')"
    )
    conn.commit()

    apply_migrations(conn, _MIGRATIONS_DIR)

    row = conn.execute("SELECT title FROM media_item WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "Movie (abcd)", f"Expected unchanged 'Movie (abcd)', got {row[0]!r}"

    # Verify the changes log has zero rows (nothing was canonicalised).
    counts = conn.execute("SELECT COUNT(*) FROM _migration_007_changes").fetchone()
    assert counts is not None
    assert counts[0] == 0

    conn.close()


def test_migration_007_length_guard_rejects_degenerate_title(tmp_path: Path) -> None:
    """LENGTH(title) > 7 guard prevents an empty title for ``' (2024)'`` (8 chars).

    Without the guard, GLOB matches and ``SUBSTR(title, 1, LENGTH(title) - 7)``
    yields ``" "`` (the leading space) which TRIMs to ``""``. The
    UNIQUE(title, kind) index added by step 6 would then conflict on
    subsequent empty rows, but more importantly the row would be
    orphaned semantically.
    """
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    # Seed a degenerate title that would canonicalise to "" without the guard.
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', ' (2024)', ' (2024)', 2024, 'movies', 1, 1, 0, 'fr')"
    )
    conn.commit()

    apply_migrations(conn, _MIGRATIONS_DIR)

    row = conn.execute("SELECT title FROM media_item WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == " (2024)", f"Expected unchanged ' (2024)', got {row[0]!r}"

    # Migration changes log must NOT contain the degenerate canonicalisation.
    counts = conn.execute("SELECT COUNT(*) FROM _migration_007_changes").fetchone()
    assert counts is not None
    assert counts[0] == 0, "LENGTH guard must skip degenerate titles"

    conn.close()


def test_migration_007_glob_matches_digit_suffix(tmp_path: Path) -> None:
    """CR-1: GLOB with [0-9] character class correctly matches year suffixes."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Inception (2010)', 'Inception (2010)', 2010, 'movies', 1, 1, 0, 'fr')"
    )
    conn.commit()

    apply_migrations(conn, _MIGRATIONS_DIR)

    row = conn.execute("SELECT title FROM media_item WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "Inception"

    # Verify logged in changes table.
    changes = conn.execute("SELECT old_title, new_title FROM _migration_007_changes").fetchall()
    assert len(changes) == 1
    assert changes[0][0] == "Inception (2010)"
    assert changes[0][1] == "Inception"

    conn.close()


def test_migration_007_media_release_not_exists_guard(tmp_path: Path) -> None:
    """SF-1: conflicting media_release rows stay with duplicate, NOT reparented."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    now = 1000
    # Seed two duplicate movie items (after canonicalisation both = "Foo").
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Foo', 'Foo', 2020, 'movies', ?, ?, 0, 'fr')",
        (now, now),
    )
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Foo (2020)', 'Foo (2020)', 2020, 'movies', ?, ?, 0, 'fr')",
        (now + 1, now + 1),
    )

    # Both have a release with the same non-NULL signature → collision.
    conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (1, NULL, '1080p', 'Director Cut', 'en')"
    )
    conn.execute(
        "INSERT INTO media_release (item_id, episode_id, quality, edition, primary_lang) "
        "VALUES (2, NULL, '1080p', 'Director Cut', 'en')"
    )
    conn.commit()

    # Apply migration 007 — the duplicate's release must NOT be reparented
    # (would violate UNIQUE) and instead gets CASCADE-deleted.
    apply_migrations(conn, _MIGRATIONS_DIR)

    # Verify: only 1 media_item survives (the keeper).
    items = conn.execute("SELECT id, title FROM media_item").fetchall()
    assert len(items) == 1
    assert items[0][1] == "Foo"

    # Verify: only 1 media_release survives (the keeper's).
    releases = conn.execute("SELECT id, item_id FROM media_release").fetchall()
    assert len(releases) == 1
    assert releases[0][1] == items[0][0]

    conn.close()


def test_migration_007_changes_table_populated(tmp_path: Path) -> None:
    """SF-M6: _migration_007_changes table logs every canonicalised title."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Alpha (2015)', 'Alpha (2015)', 2015, 'movies', 1, 1, 0, 'fr')"
    )
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', '1984 (1984)', '1984 (1984)', 1984, 'movies', 2, 2, 0, 'fr')"
    )
    conn.commit()

    apply_migrations(conn, _MIGRATIONS_DIR)

    changes = conn.execute("SELECT old_title, new_title FROM _migration_007_changes ORDER BY id").fetchall()
    assert len(changes) == 2
    assert changes[0] == ("Alpha (2015)", "Alpha")
    assert changes[1] == ("1984 (1984)", "1984")

    conn.close()


def test_unique_title_kind_rejects_duplicate_insert(conn: sqlite3.Connection) -> None:
    """Direct INSERT of same (title, kind) must raise IntegrityError."""
    item_repo.insert(conn, _make_item(title="UniqueMovie"))

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
            "date_created, date_modified, is_locked, preferred_lang) "
            "VALUES ('movie', 'UniqueMovie', 'UniqueMovie', 2024, 'movies', 1, 1, 0, 'fr')"
        )


# ---------------------------------------------------------------------------
# Migration 007: forward apply tests
# ---------------------------------------------------------------------------


def test_migration_007_canonicalises_existing_titles(tmp_path: Path) -> None:
    """Migration 007 strips `` (YYYY)`` from pre-existing rows."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    # Apply migrations 001–006 only (007 is the one under test).
    _apply_through_migration(conn, up_to_version=6)

    # Seed a pre-migration row with year-suffix title.
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Test (1999)', 'Test (1999)', 1999, 'movies', 1, 1, 0, 'fr')"
    )
    conn.commit()

    # Apply migration 007.
    apply_migrations(conn, _MIGRATIONS_DIR)

    row = conn.execute("SELECT title FROM media_item WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "Test", f"Expected canonicalised 'Test', got {row[0]!r}"

    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_version == 7

    conn.close()


def test_migration_007_dedups_post_canonicalisation(tmp_path: Path) -> None:
    """Two rows with same (title, kind) after canonicalisation → 1 row survives."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    # Seed: one clean, one with year suffix.  After canonicalisation both are
    # title="Test" kind="movie".
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Test', 'Test', 1999, 'movies', 100, 100, 0, 'fr')"
    )
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'Test (1999)', 'Test (1999)', 1999, 'movies', 200, 200, 0, 'fr')"
    )
    conn.commit()

    # Apply migration 007.
    apply_migrations(conn, _MIGRATIONS_DIR)

    rows = conn.execute("SELECT id, title, date_modified FROM media_item").fetchall()
    assert len(rows) == 1, f"Expected 1 row after dedup, got {len(rows)}: {rows}"
    row = rows[0]
    assert row[1] == "Test"  # canonicalised
    assert row[2] == 200  # date_modified merged to max

    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_version == 7

    conn.close()


def test_migration_007_idempotent(tmp_path: Path) -> None:
    """Applying migration 007 twice must be a no-op on second run."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    apply_migrations(conn, _MIGRATIONS_DIR)  # fresh 001–007

    user_v1 = conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_v1 == 7

    # Second apply — must be no-op.
    apply_migrations(conn, _MIGRATIONS_DIR)
    user_v2 = conn.execute("PRAGMA user_version").fetchone()[0]
    assert user_v2 == 7

    versions = [r[0] for r in conn.execute("SELECT version FROM schema_version ORDER BY version").fetchall()]
    assert versions == [1, 2, 3, 4, 5, 6, 7], f"Got {versions}"

    conn.close()


def test_migration_007_no_op_when_no_year_suffix_titles(tmp_path: Path) -> None:
    """Migration 007 is a no-op on a DB with only clean titles."""
    db_path = tmp_path / "library.db"
    conn = sqlite3.connect(str(db_path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")

    _apply_through_migration(conn, up_to_version=6)

    # Seed: only clean titles, no year suffix.
    conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, "
        "date_created, date_modified, is_locked, preferred_lang) "
        "VALUES ('movie', 'CleanTitle', 'CleanTitle', 2024, 'movies', 1, 1, 0, 'fr')"
    )
    conn.commit()

    apply_migrations(conn, _MIGRATIONS_DIR)

    row = conn.execute("SELECT title FROM media_item WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "CleanTitle"  # unchanged

    conn.close()


# ---------------------------------------------------------------------------
# _canonical_title helper
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_title, expected",
    [
        ("Inception (2010)", "Inception"),
        ("Inception", "Inception"),
        ("The Matrix (1999)", "The Matrix"),
        ("Year (2020) (2020)", "Year (2020)"),  # edge case: only last suffix stripped
        (" (2020)", ""),  # degenerate: just a year suffix
        ("Avatar (2009)", "Avatar"),
        ("", ""),
        ("NoYearSuffix", "NoYearSuffix"),
        ("A Beautiful Mind (2001)", "A Beautiful Mind"),
    ],
)
def test_canonical_title(input_title: str, expected: str) -> None:
    """_canonical_title strips trailing `` (YYYY)`` only."""
    assert item_repo._canonical_title(input_title) == expected


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_through_migration(conn: sqlite3.Connection, up_to_version: int) -> None:
    """Apply migration scripts 001..*up_to_version* on *conn*.

    Used to set up a DB state *before* migration 007 for forward-apply tests.

    Args:
        conn: Open :class:`sqlite3.Connection`.
        up_to_version: Highest migration version to apply (inclusive).
    """
    scripts = sorted(_MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    for script in scripts:
        version = int(script.name.split("_", 1)[0])
        if version > up_to_version:
            break
        conn.executescript(script.read_text(encoding="utf-8"))
