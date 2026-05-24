"""Tests for the release linker.

Bridges Stage A (file walk) and Stage B (enrich) by populating
``media_release`` rows from the dispatch_path attribute chain. Covers
``parse_season_dir`` (FR + EN), ``parse_episode_number`` (SxxEyy +
xxXyy), ``find_item_for_path`` traversal through ``Saison NN``
intermediates, and ``link_file_to_release`` creating the
season/episode/release rows on demand with idempotent re-linking.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.release_linker import (
    find_item_for_path,
    get_or_create_default_release,
    get_or_create_episode,
    get_or_create_season,
    link_file_to_release,
    parse_episode_number,
    parse_season_dir,
    recompute_season_episode_counts,
)
from personalscraper.indexer.repos import disk_repo, file_repo, item_repo
from personalscraper.indexer.repos.item_repo import _ATTR_DISPATCH_PATH
from personalscraper.indexer.schema import (
    DiskRow,
    ItemAttributeRow,
    MediaFileRow,
    MediaItemRow,
    PathRow,
)

MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with the full migration chain applied."""
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, MIGRATIONS_DIR)
    return c


def _seed_movie(conn: sqlite3.Connection, *, title: str, dispatch_path: str | None) -> int:
    """Insert a movie media_item with a dispatch_path attribute. Returns item_id.

    When ``dispatch_path`` is ``None``, the item is inserted without the
    attribute — useful for testing fallback resolution paths.
    """
    now = int(time.time())
    item_id = item_repo.insert(
        conn,
        MediaItemRow(
            id=0,
            kind="movie",
            title=title,
            title_sort=title,
            original_title=None,
            year=None,
            category_id="movies",
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
        ),
    )
    if dispatch_path is not None:
        item_repo.upsert_attr(
            conn,
            ItemAttributeRow(item_id=item_id, key=_ATTR_DISPATCH_PATH, value=dispatch_path),
        )
    return item_id


def _seed_show(conn: sqlite3.Connection, *, title: str, dispatch_path: str) -> int:
    """Insert a show media_item with a dispatch_path attribute. Returns item_id."""
    now = int(time.time())
    item_id = item_repo.insert(
        conn,
        MediaItemRow(
            id=0,
            kind="show",
            title=title,
            title_sort=title,
            original_title=None,
            year=None,
            category_id="tv_shows",
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
        ),
    )
    item_repo.upsert_attr(
        conn,
        ItemAttributeRow(item_id=item_id, key=_ATTR_DISPATCH_PATH, value=dispatch_path),
    )
    return item_id


def _seed_disk_and_file(conn: sqlite3.Connection, *, mount_path: str, rel_path: str, filename: str) -> int:
    """Insert disk + path + media_file rows. Returns the file_id."""
    now = int(time.time())
    disk_id = disk_repo.insert(
        conn,
        DiskRow(
            id=0,
            uuid="test-disk-uuid",
            label="TestDisk",
            mount_path=mount_path,
            last_seen_at=now,
            merkle_root=None,
            is_mounted=1,
            unreachable_strikes=0,
        ),
    )
    path_id = disk_repo.insert_path(
        conn,
        PathRow(id=0, disk_id=disk_id, rel_path=rel_path, dir_mtime_ns=None, last_walked_at=None),
    )
    file_id = file_repo.insert(
        conn,
        MediaFileRow(
            id=0,
            release_id=None,
            path_id=path_id,
            filename=filename,
            size_bytes=1024,
            mtime_ns=now * 1_000_000_000,
            ctime_ns=None,
            oshash=None,
            xxh3_partial=None,
            xxh3_full=None,
            scan_generation=1,
            last_verified_at=now,
            enriched_at=None,
            miss_strikes=0,
            deleted_at=None,
        ),
    )
    return file_id


# ---------------------------------------------------------------------------
# parse_season_dir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Saison 01", 1),
        ("Saison 12", 12),
        ("Saison 1", 1),
        ("Season 03", 3),
        ("season 5", 5),
        ("Inception (2010)", None),
        ("Saison", None),
        ("S01", None),
    ],
)
def test_parse_season_dir(name: str, expected: int | None) -> None:
    """``parse_season_dir`` recognises French + English variants and rejects others."""
    assert parse_season_dir(name) == expected


# ---------------------------------------------------------------------------
# parse_episode_number
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("S01E01 - Pilot.mkv", 1),
        ("S02E15.mp4", 15),
        ("Show.S03E007.mkv", 7),
        ("Show.1x02.mkv", 2),
        ("S01E25-26 - Double feature.avi", 25),
        ("Inception.mkv", None),
        ("season01.mkv", None),
    ],
)
def test_parse_episode_number(filename: str, expected: int | None) -> None:
    """``parse_episode_number`` handles SxxEyy + xxXyy + multi-episode markers."""
    assert parse_episode_number(filename) == expected


# ---------------------------------------------------------------------------
# find_item_for_path
# ---------------------------------------------------------------------------


def test_find_item_for_path_movie(conn: sqlite3.Connection) -> None:
    """Movie file directly inside the item directory resolves to the movie."""
    item_id = _seed_movie(conn, title="Inception (2010)", dispatch_path="/Volumes/D/films/Inception (2010)")

    result = find_item_for_path(conn, "/Volumes/D/films/Inception (2010)")
    assert result == (item_id, "movie", None)


def test_find_item_for_path_tvshow_episode(conn: sqlite3.Connection) -> None:
    """File inside ``Saison NN`` resolves to the show with season_num set."""
    item_id = _seed_show(conn, title="H (1998)", dispatch_path="/Volumes/D/series/H (1998)")

    result = find_item_for_path(conn, "/Volumes/D/series/H (1998)/Saison 02")
    assert result == (item_id, "show", 2)


def test_find_item_for_path_tvshow_root(conn: sqlite3.Connection) -> None:
    """File at the show root (e.g. tvshow.nfo, poster.jpg) has no season_num."""
    item_id = _seed_show(conn, title="H (1998)", dispatch_path="/Volumes/D/series/H (1998)")

    result = find_item_for_path(conn, "/Volumes/D/series/H (1998)")
    assert result == (item_id, "show", None)


def test_find_item_for_path_no_match(conn: sqlite3.Connection) -> None:
    """File outside any indexed item returns None."""
    _seed_movie(conn, title="Other (2020)", dispatch_path="/Volumes/D/films/Other (2020)")

    result = find_item_for_path(conn, "/Volumes/E/random/dir")
    assert result is None


def test_find_item_for_path_falls_back_to_title_match(conn: sqlite3.Connection) -> None:
    """When dispatch_path is absent, the linker matches the folder name to media_item.title.

    Post-migration 007, stored titles are canonicalised (no year suffix),
    so the folder ``Inception (2010)`` matches stored title ``Inception``
    via ``_canonical_title``.  Dispatch-style items inserted through a path
    other than ``dispatch.MediaIndex`` are still found.
    """
    item_id = _seed_movie(conn, title="Inception", dispatch_path=None)

    result = find_item_for_path(conn, "/Volumes/D/films/Inception (2010)")
    assert result == (item_id, "movie", None)


def test_find_item_for_path_title_canonicalised(conn: sqlite3.Connection) -> None:
    """SF-H4: folder ``Inception (2010)`` matches stored canonical title ``Inception``.

    After migration 007, stored titles are canonicalised (no `` (YYYY)`` suffix).
    A folder name like ``Inception (2010)`` must still match via _canonical_title.
    Pre-fix: ``WHERE title = 'Inception (2010)'`` returned 0 rows silently.
    """
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        " external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, "
        " date_created, date_modified, date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES ('movie', 'Inception', 'Inception', NULL, 2010, 'movies', '{}', NULL, NULL, "
        "        NULL, NULL, ?, ?, NULL, 0, 'fr')",
        (now, now),
    )
    item_id = cur.lastrowid

    result = find_item_for_path(conn, "/Volumes/D/films/Inception (2010)")
    assert result == (item_id, "movie", None)


def test_find_item_for_path_falls_back_to_title_year_pair(conn: sqlite3.Connection) -> None:
    """Library-scanner-style items (stripped title + separate year) are matched too.

    When neither dispatch_path nor an exact title match the folder name,
    the linker parses ``Title (Year)`` from the folder and matches against
    ``media_item.(title, year)``.
    """
    now = int(time.time())
    cur = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, original_title, year, category_id, "
        " external_ids_json, ratings_json, canonical_provider, nfo_status, artwork_json, date_created, date_modified, "
        " date_metadata_refreshed, is_locked, preferred_lang) "
        "VALUES ('movie', 'Inception', 'Inception', NULL, 2010, 'movies', '{}', NULL, NULL, "
        "        NULL, NULL, ?, ?, NULL, 0, 'fr')",
        (now, now),
    )
    item_id = cur.lastrowid

    result = find_item_for_path(conn, "/Volumes/D/films/Inception (2010)")
    assert result == (item_id, "movie", None)


# ---------------------------------------------------------------------------
# get_or_create helpers — idempotent
# ---------------------------------------------------------------------------


def test_get_or_create_season_idempotent(conn: sqlite3.Connection) -> None:
    """Re-creating the same season returns the same id; different number → new row."""
    item_id = _seed_show(conn, title="Show", dispatch_path="/x")

    s1 = get_or_create_season(conn, item_id, 1)
    s2 = get_or_create_season(conn, item_id, 1)
    s3 = get_or_create_season(conn, item_id, 2)

    assert s1 == s2
    assert s3 != s1


def test_get_or_create_episode_idempotent(conn: sqlite3.Connection) -> None:
    """Re-creating the same episode returns the same id."""
    item_id = _seed_show(conn, title="Show", dispatch_path="/x")
    season_id = get_or_create_season(conn, item_id, 1)

    e1 = get_or_create_episode(conn, season_id, 5)
    e2 = get_or_create_episode(conn, season_id, 5)
    e3 = get_or_create_episode(conn, season_id, 6)

    assert e1 == e2
    assert e3 != e1


def test_get_or_create_default_release_movie(conn: sqlite3.Connection) -> None:
    """Movie default release is keyed by ``(item_id, NULL, NULL, NULL, NULL)``."""
    item_id = _seed_movie(conn, title="Movie", dispatch_path="/x")

    r1 = get_or_create_default_release(conn, item_id=item_id)
    r2 = get_or_create_default_release(conn, item_id=item_id)
    assert r1 == r2

    row = conn.execute("SELECT item_id, episode_id, quality FROM media_release WHERE id = ?", (r1,)).fetchone()
    assert row == (item_id, None, None)


def test_get_or_create_default_release_episode(conn: sqlite3.Connection) -> None:
    """Episode default release is keyed by episode_id with NULL item_id."""
    item_id = _seed_show(conn, title="Show", dispatch_path="/x")
    season_id = get_or_create_season(conn, item_id, 1)
    episode_id = get_or_create_episode(conn, season_id, 1)

    r1 = get_or_create_default_release(conn, episode_id=episode_id)
    r2 = get_or_create_default_release(conn, episode_id=episode_id)
    assert r1 == r2

    row = conn.execute("SELECT item_id, episode_id FROM media_release WHERE id = ?", (r1,)).fetchone()
    assert row == (None, episode_id)


def test_get_or_create_default_release_requires_exclusive_args(conn: sqlite3.Connection) -> None:
    """``get_or_create_default_release`` rejects both-or-neither arg combos."""
    with pytest.raises(ValueError):
        get_or_create_default_release(conn)
    with pytest.raises(ValueError):
        get_or_create_default_release(conn, item_id=1, episode_id=1)


# ---------------------------------------------------------------------------
# link_file_to_release — end-to-end
# ---------------------------------------------------------------------------


def test_link_file_to_release_movie_creates_release(conn: sqlite3.Connection) -> None:
    """Movie file gets a brand-new default release pointing at the item."""
    item_id = _seed_movie(conn, title="Inception (2010)", dispatch_path="/Volumes/D/films/Inception (2010)")
    file_id = _seed_disk_and_file(
        conn,
        mount_path="/Volumes/D",
        rel_path="films/Inception (2010)",
        filename="Inception.mkv",
    )

    release_id = link_file_to_release(conn, file_id, "/Volumes/D/films/Inception (2010)/Inception.mkv")

    assert release_id is not None
    file_row = conn.execute("SELECT release_id FROM media_file WHERE id = ?", (file_id,)).fetchone()
    assert file_row[0] == release_id

    release_row = conn.execute("SELECT item_id, episode_id FROM media_release WHERE id = ?", (release_id,)).fetchone()
    assert release_row == (item_id, None)


def test_link_file_to_release_tv_episode(conn: sqlite3.Connection) -> None:
    """TV file inside Saison NN creates season + episode + episode-level release."""
    item_id = _seed_show(conn, title="H (1998)", dispatch_path="/Volumes/D/series/H (1998)")
    file_id = _seed_disk_and_file(
        conn,
        mount_path="/Volumes/D",
        rel_path="series/H (1998)/Saison 02",
        filename="S02E15 - Pilot.mkv",
    )

    release_id = link_file_to_release(conn, file_id, "/Volumes/D/series/H (1998)/Saison 02/S02E15 - Pilot.mkv")

    assert release_id is not None
    release_row = conn.execute("SELECT item_id, episode_id FROM media_release WHERE id = ?", (release_id,)).fetchone()
    assert release_row[0] is None
    episode_id = release_row[1]
    assert episode_id is not None

    episode_row = conn.execute("SELECT season_id, number FROM episode WHERE id = ?", (episode_id,)).fetchone()
    season_id, episode_num = episode_row
    assert episode_num == 15

    season_row = conn.execute("SELECT item_id, number FROM season WHERE id = ?", (season_id,)).fetchone()
    assert season_row == (item_id, 2)


def test_link_file_to_release_idempotent(conn: sqlite3.Connection) -> None:
    """Re-linking the same file returns the same release without duplicates."""
    _seed_show(conn, title="H (1998)", dispatch_path="/Volumes/D/series/H (1998)")
    file_id = _seed_disk_and_file(
        conn,
        mount_path="/Volumes/D",
        rel_path="series/H (1998)/Saison 01",
        filename="S01E01.mkv",
    )

    r1 = link_file_to_release(conn, file_id, "/Volumes/D/series/H (1998)/Saison 01/S01E01.mkv")
    r2 = link_file_to_release(conn, file_id, "/Volumes/D/series/H (1998)/Saison 01/S01E01.mkv")
    assert r1 == r2

    season_count = conn.execute("SELECT COUNT(*) FROM season").fetchone()[0]
    episode_count = conn.execute("SELECT COUNT(*) FROM episode").fetchone()[0]
    release_count = conn.execute("SELECT COUNT(*) FROM media_release").fetchone()[0]
    assert season_count == 1
    assert episode_count == 1
    assert release_count == 1


def test_link_file_to_release_no_match(conn: sqlite3.Connection) -> None:
    """File not under any indexed item returns None and does not write."""
    file_id = _seed_disk_and_file(
        conn,
        mount_path="/Volumes/D",
        rel_path="orphan/dir",
        filename="thing.mkv",
    )

    result = link_file_to_release(conn, file_id, "/Volumes/D/orphan/dir/thing.mkv")
    assert result is None

    file_row = conn.execute("SELECT release_id FROM media_file WHERE id = ?", (file_id,)).fetchone()
    assert file_row[0] is None


def test_link_file_to_release_tv_no_episode_marker_falls_back(conn: sqlite3.Connection) -> None:
    """Show file in Saison NN with unparseable filename falls back to item-level release."""
    item_id = _seed_show(conn, title="Show", dispatch_path="/Volumes/D/series/Show")
    file_id = _seed_disk_and_file(
        conn,
        mount_path="/Volumes/D",
        rel_path="series/Show/Saison 01",
        filename="random.jpg",
    )

    release_id = link_file_to_release(conn, file_id, "/Volumes/D/series/Show/Saison 01/random.jpg")
    assert release_id is not None

    release_row = conn.execute("SELECT item_id, episode_id FROM media_release WHERE id = ?", (release_id,)).fetchone()
    assert release_row == (item_id, None)


# ---------------------------------------------------------------------------
# recompute_season_episode_counts
# ---------------------------------------------------------------------------


def test_recompute_season_episode_counts_resyncs_stale_counter(conn: sqlite3.Connection) -> None:
    """``recompute_season_episode_counts`` resyncs the cached counter to actual episodes."""
    item_id = _seed_show(conn, title="Show", dispatch_path="/x")
    season_id = get_or_create_season(conn, item_id, 1)

    # Seed three episodes — linker leaves season.episode_count at 0.
    for ep in (1, 2, 3):
        get_or_create_episode(conn, season_id, ep)

    stale = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()
    assert stale[0] == 0

    updated = recompute_season_episode_counts(conn)
    assert updated == 1

    fresh = conn.execute("SELECT episode_count FROM season WHERE id = ?", (season_id,)).fetchone()
    assert fresh[0] == 3


def test_recompute_season_episode_counts_idempotent(conn: sqlite3.Connection) -> None:
    """Running the recompute twice returns 0 the second time."""
    item_id = _seed_show(conn, title="Show", dispatch_path="/x")
    season_id = get_or_create_season(conn, item_id, 1)
    get_or_create_episode(conn, season_id, 1)

    assert recompute_season_episode_counts(conn) == 1
    assert recompute_season_episode_counts(conn) == 0
