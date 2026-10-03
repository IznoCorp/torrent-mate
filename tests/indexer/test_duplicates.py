"""Provider-id duplicates: ids held by two rows, or by one row spread over two media folders.

The index never merges a duplicate (identity is the provider id, Q15); this read
names them so the library service and the 0-file phantom action can act on them.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path

import pytest

from personalscraper.core.identity import MediaRef
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.duplicates import (
    DuplicateGroup,
    DuplicateRow,
    find_provider_id_duplicates,
    rows_holding,
)

_MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "personalscraper" / "indexer" / "migrations"


@pytest.fixture()
def conn() -> sqlite3.Connection:
    """Open an in-memory SQLite DB with every indexer migration applied.

    Returns:
        An open :class:`sqlite3.Connection` with two disks (id 1 ``Disk1``, id 2 ``Disk2``).
    """
    c = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    apply_migrations(c, _MIGRATIONS_DIR)
    c.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u1', 'Disk1', '/d1', 1)")
    c.execute("INSERT INTO disk(uuid, label, mount_path, is_mounted) VALUES ('u2', 'Disk2', '/d2', 1)")
    return c


def _item(
    conn: sqlite3.Connection,
    title: str,
    *,
    kind: str = "show",
    year: int | None = None,
    tvdb: str | None = None,
    tmdb: str | None = None,
    canonical: str | None = None,
) -> int:
    """Insert one ``media_item`` and return its id.

    Args:
        conn: Open connection.
        title: Row title.
        kind: ``'movie'`` or ``'show'``.
        year: Release year.
        tvdb: TVDB series id, if any.
        tmdb: TMDB series id, if any.
        canonical: ``canonical_provider`` value.

    Returns:
        The new ``media_item.id``.
    """
    ids = {}
    if tvdb is not None:
        ids["tvdb"] = {"series_id": tvdb, "episode_id": None}
    if tmdb is not None:
        ids["tmdb"] = {"series_id": tmdb, "episode_id": None}
    cur = conn.execute(
        "INSERT INTO media_item(kind, title, title_sort, year, category_id, date_created, date_modified,"
        " external_ids_json, canonical_provider) VALUES (?,?,?,?,?,0,0,?,?)",
        (kind, title, title, year, "cat", json.dumps(ids), canonical),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def _file(
    conn: sqlite3.Connection, item_id: int, rel_path: str, name: str, *, deleted: bool = False, disk: int = 1
) -> None:
    """Attach one file to a movie row (``rel_path`` is the movie folder) or a show row.

    A show row gets the file through season → episode → release; a movie row through its release.

    Args:
        conn: Open connection.
        item_id: Owning ``media_item.id``.
        rel_path: The file's folder (``films/X (2020)`` or ``series/X/Saison 01``).
        name: File name.
        deleted: Whether the file is soft-deleted.
        disk: ``disk.id`` the file lies on.
    """
    kind = conn.execute("SELECT kind FROM media_item WHERE id = ?", (item_id,)).fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO path(disk_id, rel_path) VALUES (?, ?)", (disk, rel_path))
    path_id = conn.execute("SELECT id FROM path WHERE disk_id = ? AND rel_path = ?", (disk, rel_path)).fetchone()[0]
    if kind == "movie":
        cur = conn.execute("INSERT INTO media_release(item_id, quality) VALUES (?, ?)", (item_id, name))
    else:
        season = conn.execute("INSERT INTO season(item_id, number) VALUES (?, ?)", (item_id, path_id)).lastrowid
        episode = conn.execute("INSERT INTO episode(season_id, number) VALUES (?, 1)", (season,)).lastrowid
        cur = conn.execute("INSERT INTO media_release(episode_id, quality) VALUES (?, ?)", (episode, name))
    conn.execute(
        "INSERT INTO media_file(release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
        " scan_generation, last_verified_at, deleted_at) VALUES (?,?,?,1,1,'0',1,1,?)",
        (cur.lastrowid, path_id, name, 5 if deleted else None),
    )


def test_two_rows_sharing_a_tvdb_id_form_one_group(conn: sqlite3.Connection) -> None:
    """A row with files and its 0-file phantom beside it are one group of two rows."""
    real = _item(conn, "House of the Dragon (2022)", tvdb="371572")
    phantom = _item(conn, "House of the Dragon", tvdb="371572")
    _file(conn, real, "series/House of the Dragon (2022)/Saison 01", "e01.mkv")

    groups = find_provider_id_duplicates(conn)

    assert groups == [
        DuplicateGroup(
            provider="tvdb",
            provider_id="371572",
            kind="show",
            rows=(
                DuplicateRow(
                    item_id=real,
                    title="House of the Dragon (2022)",
                    live_files=1,
                    folders=("Disk1:series/House of the Dragon (2022)",),
                ),
                DuplicateRow(item_id=phantom, title="House of the Dragon", live_files=0, folders=()),
            ),
        )
    ]


def test_one_row_with_files_in_two_media_folders_is_a_group_of_one_row(conn: sqlite3.Connection) -> None:
    """A single row whose live files lie in two media folders is reported with both folders."""
    item = _item(conn, "Friends", tvdb="79168")
    _file(conn, item, "series/Friends (1994)/Saison 01", "a.mkv")
    _file(conn, item, "series/Friends [UNCUT] (1994)/Saison 01", "b.mkv")

    (group,) = find_provider_id_duplicates(conn)

    assert len(group.rows) == 1
    assert group.rows[0].live_files == 2
    assert group.rows[0].folders == ("Disk1:series/Friends (1994)", "Disk1:series/Friends [UNCUT] (1994)")


def test_one_row_with_the_same_folder_on_two_disks_is_a_group_of_one_row(conn: sqlite3.Connection) -> None:
    """A medium copied whole on two disks is two folders: one group, one row, two folders."""
    item = _item(conn, "Enemy", kind="movie", year=2014, tmdb="77")
    _file(conn, item, "films/Enemy (2014)", "a.mkv", disk=1)
    _file(conn, item, "films/Enemy (2014)", "a.mkv", disk=2)

    (group,) = find_provider_id_duplicates(conn)

    assert len(group.rows) == 1
    assert group.rows[0].folders == ("Disk1:films/Enemy (2014)", "Disk2:films/Enemy (2014)")


def test_two_seasons_of_one_folder_are_not_a_duplicate(conn: sqlite3.Connection) -> None:
    """Season sub-folders belong to the one media folder."""
    item = _item(conn, "Lost", tvdb="73739")
    _file(conn, item, "series/Lost (2004)/Saison 01", "a.mkv")
    _file(conn, item, "series/Lost (2004)/Saison 02", "b.mkv")

    assert find_provider_id_duplicates(conn) == []


def test_distinct_ids_and_soft_deleted_files_are_not_duplicates(conn: sqlite3.Connection) -> None:
    """Distinct ids give no group; a tombstoned file in a second folder does not count."""
    _item(conn, "A", tvdb="1")
    _item(conn, "B", tvdb="2")
    item = _item(conn, "C", tvdb="3")
    _file(conn, item, "series/C (2000)/Saison 01", "a.mkv")
    _file(conn, item, "series/C other (2000)/Saison 01", "b.mkv", deleted=True)

    assert find_provider_id_duplicates(conn) == []


def test_nfc_and_nfd_folder_names_count_once(conn: sqlite3.Connection) -> None:
    """The same accented folder stored in NFC and NFD is one folder."""
    item = _item(conn, "Élite", kind="movie", tmdb="9")
    nfc = unicodedata.normalize("NFC", "films/Élite (2020)")
    nfd = unicodedata.normalize("NFD", "films/Élite (2020)")
    _file(conn, item, nfc, "a.mkv")
    _file(conn, item, nfd, "b.mkv")

    assert find_provider_id_duplicates(conn) == []


def test_movies_are_keyed_by_tmdb_and_shows_by_tvdb(conn: sqlite3.Connection) -> None:
    """A movie sharing a TMDB id is a movie group; a tmdb-canonical show is keyed by its tmdb id."""
    _item(conn, "M1", kind="movie", year=2000, tmdb="50")
    _item(conn, "M2", kind="movie", year=2001, tmdb="50")
    _item(conn, "S1", tvdb="7", tmdb="60", canonical="tmdb")
    _item(conn, "S2", tvdb="8", tmdb="60", canonical="tmdb")

    groups = find_provider_id_duplicates(conn)

    assert {(g.provider, g.provider_id, g.kind, len(g.rows)) for g in groups} == {
        ("tmdb", "50", "movie", 2),
        ("tmdb", "60", "show", 2),
    }


def test_placeholder_ids_never_group(conn: sqlite3.Connection) -> None:
    """The leaked placeholder ids 0 and none never name a medium."""
    _item(conn, "P1", tvdb="0")
    _item(conn, "P2", tvdb="0")
    _item(conn, "P3", kind="movie", year=1, tmdb="none")
    _item(conn, "P4", kind="movie", year=2, tmdb="none")

    assert find_provider_id_duplicates(conn) == []


def test_rows_holding_returns_every_holder_live_or_not(conn: sqlite3.Connection) -> None:
    """``rows_holding`` lists the rows holding the ref's canonical id, files or none."""
    a = _item(conn, "A (2020)", tvdb="11")
    b = _item(conn, "A", tvdb="11")
    _item(conn, "Other", tvdb="12")
    movie = _item(conn, "Film", kind="movie", year=2020, tmdb="11")
    _file(conn, a, "series/A (2020)/Saison 01", "a.mkv")

    assert rows_holding(conn, MediaRef(tvdb_id=11), "show") == [a, b]
    assert rows_holding(conn, MediaRef(tmdb_id=11), "movie") == [movie]
    assert rows_holding(conn, MediaRef(tvdb_id=11)) == [a, b]
    assert rows_holding(conn, MediaRef(tvdb_id=999), "show") == []


def test_rows_holding_kind_filter_separates_a_show_from_a_movie(conn: sqlite3.Connection) -> None:
    """A tmdb-canonical show and a movie sharing tmdb 11: ``kind`` picks one, ``None`` both."""
    show = _item(conn, "Show", kind="show", tmdb="11", canonical="tmdb")
    movie = _item(conn, "Film", kind="movie", year=2020, tmdb="11")

    assert rows_holding(conn, MediaRef(tmdb_id=11), "show") == [show]
    assert rows_holding(conn, MediaRef(tmdb_id=11), "movie") == [movie]
    assert rows_holding(conn, MediaRef(tmdb_id=11)) == [show, movie]
