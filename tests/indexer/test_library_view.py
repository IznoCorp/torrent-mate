"""The library view's SQL listing against the Python listing it replaces.

The oracle below is the listing as the application computed it before the indexer did:
every live row read, the id-less ones dropped, then filtered, sorted (stable over the
recent order, reversed by a second pass) and sliced in Python. ``LibraryReader.page``
must give the same item ids and the same three counts for every order, direction,
question, category set and page.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from personalscraper.indexer.library_view import (
    LIBRARY_PAGE_SIZE,
    IndexUnavailable,
    LibraryIndex,
    ListingOrder,
    fold,
    french_key,
    parse_ids,
)
from tests.unit.app.library.world import FixtureIndex

# The listing's query before it moved: every live row, the most recently added first.
_ORACLE_SQL = (
    "SELECT m.id, m.title, m.title_sort, m.original_title, m.category_id, m.external_ids_json FROM media_item m"
    " WHERE (EXISTS (SELECT 1 FROM media_release r JOIN media_file f ON f.release_id = r.id"
    " WHERE r.item_id = m.id AND f.deleted_at IS NULL)"
    " OR EXISTS (SELECT 1 FROM season s JOIN episode e ON e.season_id = s.id"
    " JOIN media_release r ON r.episode_id = e.id JOIN media_file f ON f.release_id = r.id"
    " WHERE s.item_id = m.id AND f.deleted_at IS NULL))"
    " ORDER BY m.date_created DESC, m.id DESC"
)

_Row = tuple[int, str, str, str | None, str]


def _oracle_rows(conn: sqlite3.Connection) -> list[_Row]:
    """Every live, identified row as the Python listing read it: ``(id, title, sort title, original, category)``.

    Args:
        conn: The index.

    Returns:
        The rows, most recently added first.
    """
    return [
        (item_id, title, title_sort or title, original, category)
        for item_id, title, title_sort, original, category, ids in conn.execute(_ORACLE_SQL)
        if parse_ids(ids)
    ]


def _oracle_matches(row: _Row, query: str) -> bool:
    """The Python search: the folded question in the folded title or original title."""
    wanted = fold(query.strip())
    if not wanted:
        return True
    return wanted in fold(row[1]) or (row[3] is not None and wanted in fold(row[3]))


def _oracle_page(
    rows: Sequence[_Row],
    *,
    categories: frozenset[str],
    query: str | None,
    order: ListingOrder,
    reversed_: bool,
    page: int,
) -> tuple[list[int], int, int, int]:
    """One page as the Python listing cut it.

    Returns:
        ``(item ids, total, matching, loaded)``.
    """
    selected = [
        row
        for row in rows
        if (not categories or row[4] in categories) and (query is None or _oracle_matches(row, query))
    ]
    if order is ListingOrder.AZ:
        selected.sort(key=lambda row: french_key(row[2]))
    if reversed_:
        selected.reverse()
    filtered = bool(categories) or bool(query and query.strip())
    cut = selected[page * LIBRARY_PAGE_SIZE : (page + 1) * LIBRARY_PAGE_SIZE]
    return [row[0] for row in cut], len(selected) if filtered else len(rows), len(selected), len(rows)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory: pytest.TempPathFactory) -> FixtureIndex:
    """An index holding every case the orders and the search must agree on.

    Accented, ligatured, case-only-different and equal-key titles, equal creation times,
    an empty sort title, an original title, an id-less row, a placeholder-id row, a
    phantom 0-file row, a row whose only file is tombstoned, shows, several categories,
    and two full pages plus one row of listed entries.
    """
    index = FixtureIndex(tmp_path_factory.mktemp("view") / "library.db")
    listed: list[int] = []

    def movie(title: str, tmdb: str, **kwargs: object) -> int:
        item = index.item(title, tmdb=tmdb, **kwargs)  # type: ignore[arg-type]
        index.movie_file(item, f"films/{tmdb}")
        listed.append(item)
        return item

    movie("Eagle", "1")
    movie("Élite", "2")
    movie("élite", "3")
    movie("Eternals", "4", category="movies_animation")
    movie("cote", "5")
    movie("côte", "6")
    movie("Côte", "7", category="anime")
    movie("Œdipe", "8")
    movie("Oedipe", "9")
    movie("Œdipe", "10", year=2021, created=1_600_000_000)
    movie("Œdipe", "11", year=2022, created=1_600_000_000)
    movie("Same", "12", title_sort="Same")
    movie("Same", "13", year=2021, title_sort="Same", category="anime")
    movie("Le Bureau", "14", title_sort="Bureau", original_title="Le Bureau des légendes")
    movie("Ångström", "15", category="movies_animation")
    empty_sort = movie("Zèbre", "16")
    index.conn.execute("UPDATE media_item SET title_sort = '' WHERE id = ?", (empty_sort,))
    for number in range(17, 37):
        movie(f"Filler {number:02d}", str(number), category="movies" if number % 3 else "anime")
    show = index.item("Œuvre", kind="show", tvdb="501")
    index.episodes(show, 1, [1, 2], folder="series/Oeuvre")
    listed.append(show)
    imdb_only = index.item("Imdb Only", imdb="tt0000042")
    index.movie_file(imdb_only, "films/imdb")
    listed.append(imdb_only)
    for number in range(37, 48):
        movie(f"Late {number}", str(number), category="tv_shows")

    no_ids = index.item("No Id")
    index.movie_file(no_ids, "films/noid")
    placeholder = index.item("Placeholder", tmdb="0")
    index.movie_file(placeholder, "films/zero")
    index.item("Phantom", tmdb="900")
    gone = index.item("Gone", tmdb="901")
    index.movie_file(gone, "films/gone", deleted=True)

    assert len(listed) == 2 * LIBRARY_PAGE_SIZE + 1
    return index


_QUERIES: tuple[str | None, ...] = (None, "", "   ", "e", "ÉLI", "oedipe", "œ", "légendes", "cote", "zzz", "́")
_CATEGORIES: tuple[frozenset[str], ...] = (
    frozenset(),
    frozenset({"movies"}),
    frozenset({"anime", "movies_animation"}),
    frozenset({"nothing"}),
)


@pytest.mark.parametrize("order", list(ListingOrder))
@pytest.mark.parametrize("reversed_", [False, True])
@pytest.mark.parametrize("query", _QUERIES)
@pytest.mark.parametrize("categories", _CATEGORIES, ids=lambda c: "+".join(sorted(c)) or "all")
def test_page_matches_the_python_listing(
    seeded: FixtureIndex,
    order: ListingOrder,
    reversed_: bool,
    query: str | None,
    categories: frozenset[str],
) -> None:
    """Every page of every question holds the oracle's items, in its order, with its counts."""
    rows = _oracle_rows(seeded.conn)
    with LibraryIndex(seeded.path).reader() as reader:
        pages = 0
        while True:
            want_ids, total, matching, loaded = _oracle_page(
                rows, categories=categories, query=query, order=order, reversed_=reversed_, page=pages
            )
            got = reader.page(categories=categories, query=query, order=order, reversed_=reversed_, page=pages)

            assert [item.item_id for item in got.items] == want_ids, f"page {pages}"
            assert (got.total, got.matching, got.loaded) == (total, matching, loaded)
            if not want_ids:
                break
            pages += 1
    assert pages == -(-matching // LIBRARY_PAGE_SIZE)


def test_the_seed_spans_three_pages(seeded: FixtureIndex) -> None:
    """The unfiltered listing is two full pages and one row: the last page holds one."""
    with LibraryIndex(seeded.path).reader() as reader:
        last = reader.page(categories=frozenset(), query=None, order=ListingOrder.AZ, reversed_=False, page=2)

    assert (len(last.items), last.loaded) == (1, 2 * LIBRARY_PAGE_SIZE + 1)


def test_live_items_category_counts_and_recent_match_the_python_reads(seeded: FixtureIndex) -> None:
    """The whole live list, the per-category counts and the recent strip are the oracle's."""
    rows = _oracle_rows(seeded.conn)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row[4]] = counts.get(row[4], 0) + 1

    with LibraryIndex(seeded.path).reader() as reader:
        assert [item.item_id for item in reader.live_items()] == [row[0] for row in rows]
        assert reader.category_counts() == counts
        assert [item.item_id for item in reader.recent(12)] == [row[0] for row in rows[:12]]


def test_a_negative_page_is_refused(seeded: FixtureIndex) -> None:
    """A page below zero names no page."""
    with LibraryIndex(seeded.path).reader() as reader, pytest.raises(ValueError):
        reader.page(categories=frozenset(), query=None, order=ListingOrder.RECENT, reversed_=False, page=-1)


def test_the_reader_opens_nothing_writable(seeded: FixtureIndex) -> None:
    """A write through the reader raises, even with ``query_only`` lifted: the file is opened read-only."""
    with LibraryIndex(seeded.path).reader() as reader:
        conn = reader._conn  # noqa: SLF001 - the connection under test is private
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM media_item")
        conn.execute("PRAGMA query_only=OFF")
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("DELETE FROM media_item")

    assert seeded.conn.execute("SELECT COUNT(*) FROM media_item").fetchone()[0] > 0


@pytest.mark.parametrize("content", [None, b"", b"not a database at all, just bytes" * 64])
def test_an_unreadable_index_is_unavailable(tmp_path: Path, content: bytes | None) -> None:
    """An absent file, an empty file and a file that is no database are refused at open, the cause kept."""
    path = tmp_path / "library.db"
    if content is not None:
        path.write_bytes(content)

    with pytest.raises(IndexUnavailable) as refused:
        LibraryIndex(path).reader()

    assert isinstance(refused.value.__cause__, sqlite3.Error)
    assert content is not None or not path.exists()


def test_any_disk_unmounted(tmp_path: Path) -> None:
    """The reader says whether the index knows a disk that is not mounted."""
    index = FixtureIndex(tmp_path / "library.db")
    with LibraryIndex(index.path).reader() as reader:
        assert reader.any_disk_unmounted() is False
    index.mount(2, None)
    with LibraryIndex(index.path).reader() as reader:
        assert reader.any_disk_unmounted() is True
    index.conn.close()


def test_parse_ids_keeps_the_wire_order_and_drops_placeholders() -> None:
    """TVDB, TMDB, IMDb in that order; placeholders and malformed values dropped."""
    raw = json.dumps({"imdb": {"series_id": "tt1"}, "tmdb": {"series_id": "0"}, "tvdb": {"series_id": " 7 "}})

    assert list(parse_ids(raw).items()) == [("tvdb", 7), ("imdb", "tt1")]
    assert parse_ids("not json") == {}
