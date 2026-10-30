"""Merging the items an older build split on one ``dispatch_path``.

Each test seeds the shape a split left in prod — an old item and a younger one
on the same folder, each with children — and checks that the merge keeps the
oldest item, re-points every child to it, and loses no file.
"""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from pathlib import Path

import pytest

from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.merge_items import MERGE_REASON, find_duplicate_groups, merge_duplicate_items

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "personalscraper" / "indexer" / "migrations"
SHOW_PATH = "/Volumes/Medias1/medias/series/Ted Lasso (2020)"
MOVIE_PATH = "/Volumes/Medias1/medias/films/The Gentlemen (2020)"


def _make_conn() -> sqlite3.Connection:
    """Return an in-memory store with the full schema and foreign keys on."""
    conn = sqlite3.connect(":memory:", isolation_level=None)
    conn.execute("PRAGMA foreign_keys=ON")
    apply_migrations(conn, MIGRATIONS_DIR)
    return conn


def _item(
    conn: sqlite3.Connection, title: str, kind: str, path: str, *, created: int, ids: str = "{}", year: int = 2020
) -> int:
    """Insert an item carrying *path* as its dispatch_path; return its id."""
    item_id = conn.execute(
        "INSERT INTO media_item (kind, title, title_sort, year, category_id, external_ids_json,"
        " nfo_status, date_created, date_modified) VALUES (?, ?, ?, ?, 'tv_shows', ?, 'valid', ?, ?)",
        (kind, title, title, year, ids, created, created),
    ).lastrowid
    conn.execute("INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'dispatch_path', ?)", (item_id, path))
    return int(item_id)  # type: ignore[arg-type]


def _file(conn: sqlite3.Connection, release_id: int, filename: str) -> int:
    """Insert a live media_file on *release_id*; return its id."""
    disk_id = conn.execute("SELECT id FROM disk").fetchone()
    if disk_id is None:
        conn.execute(
            "INSERT INTO disk (uuid, label, mount_path, is_mounted, unreachable_strikes) VALUES ('u', 'd', '/m', 1, 0)"
        )
    path_id = conn.execute(
        "INSERT INTO path (disk_id, rel_path) VALUES ((SELECT id FROM disk), ?) "
        "ON CONFLICT(disk_id, rel_path) DO UPDATE SET rel_path = excluded.rel_path RETURNING id",
        ("series/Ted Lasso (2020)",),
    ).fetchone()[0]
    return int(
        conn.execute(  # type: ignore[arg-type]
            "INSERT INTO media_file (release_id, path_id, filename, size_bytes, mtime_ns, oshash,"
            " scan_generation, last_verified_at) VALUES (?, ?, ?, 1, 1, 'h', 1, 1)",
            (release_id, path_id, filename),
        ).lastrowid
    )


def _season(conn: sqlite3.Connection, item_id: int, number: int) -> int:
    """Insert a season; return its id."""
    return int(
        conn.execute(  # type: ignore[arg-type]
            "INSERT INTO season (item_id, number) VALUES (?, ?)", (item_id, number)
        ).lastrowid
    )


def _episode(conn: sqlite3.Connection, season_id: int, number: int, title: str | None = None) -> int:
    """Insert an episode; return its id."""
    return int(
        conn.execute(  # type: ignore[arg-type]
            "INSERT INTO episode (season_id, number, title) VALUES (?, ?, ?)", (season_id, number, title)
        ).lastrowid
    )


def _episode_release(conn: sqlite3.Connection, episode_id: int, end_id: int | None = None) -> int:
    """Insert a default release of an episode; return its id."""
    return int(
        conn.execute(  # type: ignore[arg-type]
            "INSERT INTO media_release (episode_id, episode_end_id) VALUES (?, ?)", (episode_id, end_id)
        ).lastrowid
    )


def _split_show(conn: sqlite3.Connection) -> dict[str, int]:
    """Seed the split show: the old item has S01, the young one S01 (overlapping) and S02.

    Returns:
        The ids the assertions need.
    """
    old = _item(conn, "Ted Lasso (2020)", "show", SHOW_PATH, created=100, ids='{"tvdb": {"series_id": "383203"}}')
    young = _item(conn, "Ted Lasso", "show", SHOW_PATH, created=200, ids='{"tmdb": {"series_id": "97546"}}')
    old_s1 = _season(conn, old, 1)
    old_e1 = _episode(conn, old_s1, 1)
    young_s1 = _season(conn, young, 1)
    young_e1 = _episode(conn, young_s1, 1, "Pilot")
    young_e2 = _episode(conn, young_s1, 2)
    young_s2 = _season(conn, young, 2)
    _episode(conn, young_s2, 1)
    old_rel = _episode_release(conn, old_e1)
    young_rel_e1 = _episode_release(conn, young_e1)
    young_rel_span = _episode_release(conn, young_e1, end_id=young_e2)
    files = {
        "old_e1": _file(conn, old_rel, "S01E01.mkv"),
        "young_e1": _file(conn, young_rel_e1, "S01E01.nfo"),
        "span": _file(conn, young_rel_span, "S01E01-E02.mkv"),
    }
    conn.execute("INSERT INTO item_attribute (item_id, key, value) VALUES (?, 'trailer_found', '1')", (young,))
    conn.execute("INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at) VALUES ('item', ?, 'r', 1)", (young,))
    conn.execute("INSERT INTO scan_run (generation, mode, started_at) VALUES (1, 'full', 1)")
    conn.execute(
        "INSERT INTO scan_event (scan_id, ts, item_id, event) VALUES ((SELECT id FROM scan_run), 1, ?, 'e')", (young,)
    )
    return {"old": old, "young": young, "old_s1": old_s1, "old_e1": old_e1, **files}


def test_the_split_is_found_and_the_oldest_item_keeps_the_folder() -> None:
    """One group per shared path, its keeper the oldest item."""
    conn = _make_conn()
    ids = _split_show(conn)
    _item(conn, "Alone", "movie", "/Volumes/Medias1/medias/films/Alone (2020)", created=50)

    groups = find_duplicate_groups(conn)

    assert [(g.dispatch_path, g.keeper_id, g.duplicate_ids) for g in groups] == [
        (SHOW_PATH, ids["old"], (ids["young"],))
    ]


def test_a_dry_run_writes_nothing() -> None:
    """The dry run lists the group and leaves the store byte for byte as it was."""
    conn = _make_conn()
    _split_show(conn)
    before = list(conn.iterdump())

    report = merge_duplicate_items(conn, dry_run=True)

    assert len(report.groups) == 1 and report.merged == 0
    assert list(conn.iterdump()) == before


def test_the_merge_repoints_every_child_and_loses_no_file() -> None:
    """Seasons, episodes, releases, files, attributes, repairs and events all reach the keeper."""
    conn = _make_conn()
    ids = _split_show(conn)
    files_before = conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0]

    report = merge_duplicate_items(conn, dry_run=False, now_s=5000)

    assert report.merged == 1
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM media_file").fetchone()[0] == files_before, "no file is lost"
    seasons = conn.execute("SELECT number FROM season WHERE item_id = ? ORDER BY number", (ids["old"],)).fetchall()
    assert [s[0] for s in seasons] == [1, 2]
    s1_episodes = conn.execute(
        "SELECT number, title FROM episode WHERE season_id = ? ORDER BY number", (ids["old_s1"],)
    ).fetchall()
    assert s1_episodes == [(1, "Pilot"), (2, None)], "episode 1 keeps one row and gains the title"
    # Every file now hangs under the keeper, through its releases and episodes.
    reachable = conn.execute(
        "SELECT COUNT(*) FROM media_file mf JOIN media_release mr ON mr.id = mf.release_id "
        "JOIN episode e ON e.id = mr.episode_id JOIN season s ON s.id = e.season_id WHERE s.item_id = ?",
        (ids["old"],),
    ).fetchone()[0]
    assert reachable == files_before
    span_end = conn.execute(
        "SELECT e.number FROM media_release mr JOIN media_file mf ON mf.release_id = mr.id "
        "JOIN episode e ON e.id = mr.episode_end_id WHERE mf.id = ?",
        (ids["span"],),
    ).fetchone()
    assert span_end == (2,), "a span's end episode follows the merge"
    assert conn.execute(
        "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'trailer_found'", (ids["old"],)
    ).fetchone() == ("1",)
    assert conn.execute("SELECT scope_id FROM repair_queue").fetchone() == (ids["old"],)
    assert conn.execute("SELECT item_id FROM scan_event").fetchone() == (ids["old"],)
    title, eids = conn.execute("SELECT title, external_ids_json FROM media_item").fetchone()
    assert title == "Ted Lasso", "the keeper's drifted title is healed"
    assert set(json.loads(eids)) == {"tvdb", "tmdb"}, "provider ids of both rows are kept"
    tombstone = conn.execute(
        "SELECT original_id, reason, payload_json FROM deleted_item WHERE kind = 'item'"
    ).fetchone()
    assert tombstone[:2] == (ids["young"], MERGE_REASON)
    assert json.loads(tombstone[2])["merged_into"] == ids["old"]
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_item_level_releases_of_one_signature_fold_into_one() -> None:
    """Two default releases of one movie become one release holding both files."""
    conn = _make_conn()
    old = _item(conn, "The Gentlemen", "movie", MOVIE_PATH, created=100)
    young = _item(conn, "The Gentlemen (2020)", "movie", MOVIE_PATH, created=200)
    old_rel = int(conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (old,)).lastrowid)  # type: ignore[arg-type]
    young_rel = int(conn.execute("INSERT INTO media_release (item_id) VALUES (?)", (young,)).lastrowid)  # type: ignore[arg-type]
    _file(conn, old_rel, "The Gentlemen.mkv")
    _file(conn, young_rel, "The Gentlemen-poster.jpg")

    merge_duplicate_items(conn, dry_run=False)

    assert conn.execute("SELECT id FROM media_release").fetchall() == [(old_rel,)]
    assert conn.execute("SELECT COUNT(*) FROM media_file WHERE release_id = ?", (old_rel,)).fetchone()[0] == 2


def test_a_movie_and_a_show_on_one_folder_are_left_alone() -> None:
    """Mixed kinds are not a split the merge can decide; nothing is written."""
    conn = _make_conn()
    _item(conn, "Odd", "movie", MOVIE_PATH, created=100)
    _item(conn, "Odd", "show", MOVIE_PATH, created=200)

    report = merge_duplicate_items(conn, dry_run=False)

    assert report.merged == 0 and [why for _g, why in report.skipped] == ["mixed_kinds"]
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 2


def test_an_nfd_and_a_case_variant_of_one_folder_are_one_group() -> None:
    """The dispatch writes NFC, an HFS+ walk reads NFD, the volume ignores case: one folder."""
    conn = _make_conn()
    nfc = "/Volumes/Medias1/medias/séries/Pokémon (1997)"
    old = _item(conn, "Pokémon", "show", nfc, created=100)
    nfd = _item(conn, "Pokémon (1997)", "show", unicodedata.normalize("NFD", nfc), created=200)
    upper = _item(conn, "POKÉMON", "show", nfc.upper(), created=300)

    groups = find_duplicate_groups(conn)

    assert [(g.keeper_id, set(g.duplicate_ids)) for g in groups] == [(old, {nfd, upper})]


@pytest.mark.parametrize(
    ("young_year", "young_ids", "reason"),
    [
        (2019, '{"tmdb": {"series_id": "1"}}', "different_years"),
        (2020, '{"tmdb": {"series_id": "2"}}', "conflicting_provider_ids"),
    ],
)
def test_a_remake_and_its_original_on_one_folder_are_left_alone(young_year: int, young_ids: str, reason: str) -> None:
    """Two explicit years, or two ids of one provider, are two works: the dry run and the run both skip them."""
    conn = _make_conn()
    _item(conn, "The Office", "show", SHOW_PATH, created=100, ids='{"tmdb": {"series_id": "1"}}', year=2020)
    _item(conn, "The Office (2020)", "show", SHOW_PATH, created=200, ids=young_ids, year=young_year)

    dry = merge_duplicate_items(conn, dry_run=True)
    report = merge_duplicate_items(conn, dry_run=False)

    assert [why for _g, why in dry.skipped] == [reason] and dry.groups == []
    assert report.merged == 0 and [why for _g, why in report.skipped] == [reason]
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 2


def test_a_yearless_member_and_complementary_ids_still_merge() -> None:
    """One year unknown and ids of different providers are no conflict: the split merges."""
    conn = _make_conn()
    _item(conn, "Ted Lasso", "show", SHOW_PATH, created=100, ids='{"tvdb": {"series_id": "383203"}}')
    young = _item(conn, "Ted Lasso (2020)", "show", SHOW_PATH, created=200, ids='{"tmdb": {"series_id": "97546"}}')
    conn.execute("UPDATE media_item SET year = NULL WHERE id = ?", (young,))

    report = merge_duplicate_items(conn, dry_run=False)

    assert report.merged == 1 and report.skipped == []


def test_both_items_with_a_pending_repair_merge_and_keep_one_pending_row() -> None:
    """The partial UNIQUE(scope, scope_id) WHERE pending admits one pending repair per item."""
    conn = _make_conn()
    ids = _split_show(conn)  # the young item carries a pending repair
    conn.execute(
        "INSERT INTO repair_queue (scope, scope_id, reason, enqueued_at) VALUES ('item', ?, 'r', 1)", (ids["old"],)
    )

    report = merge_duplicate_items(conn, dry_run=False)

    assert report.merged == 1
    rows = conn.execute("SELECT scope_id, status FROM repair_queue ORDER BY id").fetchall()
    assert rows == [(ids["old"], "done"), (ids["old"], "pending")]


def test_a_year_the_keeper_cannot_take_skips_its_group_only() -> None:
    """A third row already holds the keeper's (title, kind, year): that group is reported, the others merge."""
    conn = _make_conn()
    keeper = _item(conn, "Dune", "movie", MOVIE_PATH, created=100)
    conn.execute("UPDATE media_item SET year = NULL WHERE id = ?", (keeper,))
    _item(conn, "Dune (2021)", "movie", MOVIE_PATH, created=200, year=2021)
    _item(conn, "Dune", "movie", "/Volumes/Medias1/medias/films/Dune (2021) bis", created=50, year=2021)
    ids = _split_show(conn)

    dry = merge_duplicate_items(conn, dry_run=True)
    report = merge_duplicate_items(conn, dry_run=False)

    assert [(g.keeper_id, why) for g, why in dry.skipped] == [(keeper, "year_taken")]
    assert [(g.keeper_id, why) for g, why in report.skipped] == [(keeper, "year_taken")]
    assert report.merged == 1, "the other group still merges"
    assert conn.execute("SELECT COUNT(*) FROM media_item WHERE id = ?", (ids["young"],)).fetchone() == (0,)
