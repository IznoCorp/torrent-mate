"""U+F025 (NTFS/macFUSE private-use stand-in for « ? ») equals « ? » at every name comparison site."""

from __future__ import annotations

import sqlite3
import unicodedata
from pathlib import Path

from personalscraper._fs_utils import fold_ntfs_question_mark, name_key, name_variants
from personalscraper.dispatch.media_index import _normalize_key
from personalscraper.dispatch.post_maintenance import _rel_path_variants
from personalscraper.conf import ids as CID
from personalscraper.conf.models.disks import DiskConfig
from personalscraper.indexer.db import apply_migrations
from personalscraper.indexer.repos import item_repo
from personalscraper.indexer.repos.item_repo import _canonical_title
from personalscraper.indexer.scanner._modes._item_stage import build_item_row, scan_and_stage_dir
from personalscraper.indexer.schema import MediaItemRow

_NTFS_QMARK = ""
_WITH_NTFS_QMARK = f"Who Is Robin{_NTFS_QMARK} (2020)"
_WITH_QMARK = "Who Is Robin? (2020)"


def test_fold_maps_private_use_char_to_question_mark() -> None:
    """The private-use character becomes a real « ? »; a real « ? » is untouched."""
    assert fold_ntfs_question_mark(_WITH_NTFS_QMARK) == _WITH_QMARK
    assert fold_ntfs_question_mark(_WITH_QMARK) == _WITH_QMARK


def test_name_key_equates_both_spellings_and_unicode_forms() -> None:
    """Both spellings, in NFC or NFD, give one key."""
    nfd = unicodedata.normalize("NFD", _WITH_NTFS_QMARK.replace("Robin", "Zo\u00eb"))
    nfc = unicodedata.normalize("NFC", _WITH_QMARK.replace("Robin", "Zo\u00eb"))
    assert name_key(nfd) == name_key(nfc)


def test_name_variants_cover_each_character() -> None:
    """From either spelling the variants hold both spellings."""
    for source in (_WITH_NTFS_QMARK, _WITH_QMARK):
        variants = name_variants(source)
        assert _WITH_NTFS_QMARK in variants
        assert _WITH_QMARK in variants


def test_dispatch_lookup_key_equates_the_twins() -> None:
    """The dispatch index key of a U+F025 name equals that of its « ? » twin."""
    assert _normalize_key(_WITH_NTFS_QMARK) == _normalize_key(_WITH_QMARK)


def test_indexer_canonical_title_equates_the_twins() -> None:
    """The indexer's dedup title of a U+F025 name equals that of its « ? » twin."""
    assert _canonical_title(_WITH_NTFS_QMARK) == _canonical_title(_WITH_QMARK)


def test_refresh_path_variants_hold_both_characters() -> None:
    """A refresh given one spelling invalidates rows stored under the other."""
    for source in (f"series/{_WITH_NTFS_QMARK}", f"series/{_WITH_QMARK}"):
        variants = _rel_path_variants(source)
        assert f"series/{_WITH_NTFS_QMARK}" in variants
        assert f"series/{_WITH_QMARK}" in variants


# ---------------------------------------------------------------------------
# Rows stored BEFORE the fold keep U+F025: lookups must still find them
# ---------------------------------------------------------------------------

_PRE_FOLD_TITLE = "Who Is Robin"


def _migrated_db() -> sqlite3.Connection:
    """An in-memory database with the real indexer schema."""
    conn = sqlite3.connect(":memory:")
    apply_migrations(conn, Path(__file__).resolve().parents[1] / "personalscraper" / "indexer" / "migrations")
    return conn


def _insert_pre_fold_movie(conn: sqlite3.Connection) -> int:
    """A movie row as the code before the fold stored it: U+F025 in title and in the dispatch key."""
    conn.execute(
        "INSERT INTO media_item (id, kind, title, title_sort, year, category_id, date_created, date_modified,"
        " preferred_lang) VALUES (1, 'movie', ?, ?, 2020, 'movies', 1, 1, 'fr')",
        (_PRE_FOLD_TITLE, _PRE_FOLD_TITLE),
    )
    conn.execute(
        "INSERT INTO item_attribute (item_id, key, value) VALUES (1, 'dispatch_normalized_title', ?)",
        (f"{_PRE_FOLD_TITLE.lower()} (2020)",),
    )
    conn.commit()
    return 1


def test_upsert_finds_a_row_stored_with_the_private_use_character() -> None:
    """The next scan (title with « ? ») updates the pre-fold row instead of inserting a duplicate item."""
    conn = _migrated_db()
    existing_id = _insert_pre_fold_movie(conn)
    row = build_item_row(
        title="Who Is Robin? (2020)",
        kind="movie",
        year=2020,
        category_id="movies",
        tvdb_id=None,
        tmdb_id="1",
        nfo_status="valid",
    )
    row["date_created"] = row["date_modified"] = 2

    assert item_repo.upsert(conn, MediaItemRow(**row)) == existing_id
    assert conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] == 1


def test_dispatch_lookup_finds_a_row_whose_key_holds_the_private_use_character() -> None:
    """A dispatch lookup by the « ? » key finds the item indexed before the fold."""
    conn = _migrated_db()
    existing_id = _insert_pre_fold_movie(conn)

    found = item_repo.find_by_normalized_name(conn, _normalize_key("Who Is Robin? (2020)"), "movie")

    assert found is not None
    assert found[0].id == existing_id


def test_scanner_dispatch_key_equals_the_dispatch_normalisation(tmp_path: Path) -> None:
    """The ``dispatch_normalized_title`` the scanner stages equals ``_normalize_key`` of the U+F025 title."""
    conn = _migrated_db()
    disk_cfg = DiskConfig(id="drive_a", path=tmp_path / "drive_a", categories=[CID.MOVIES])
    movie = tmp_path / "drive_a" / "films" / "Who Is Robin (2020)"
    movie.mkdir(parents=True)
    (movie / "Who Is Robin.mkv").write_bytes(b"\x00" * 1000)
    (movie / "Who Is Robin.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')

    item_id = scan_and_stage_dir(conn, movie, disk_cfg, CID.MOVIES, "movie", now_s=1000)

    stored = conn.execute(
        "SELECT value FROM item_attribute WHERE item_id = ? AND key = 'dispatch_normalized_title'", (item_id,)
    ).fetchone()[0]
    assert stored == _normalize_key("Who Is Robin\uf025") == _normalize_key("Who Is Robin?")
    assert "" not in stored
