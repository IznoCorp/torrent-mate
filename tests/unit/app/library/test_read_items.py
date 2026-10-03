"""The library's listing: paging, the French order, the « missing » order, search, categories, counts."""

from __future__ import annotations

import unicodedata
from datetime import date

from personalscraper.app.library.service import LIBRARY_PAGE_SIZE, LibrarySort
from tests.unit.app.library.world import World, catalogued

# Two French titles, the collation's own test data: an accented initial sorts with its letter.
ELITE = "\u00c9lite"
SCREEN = "\u00c9cran"


def _titles(world: World, **kwargs: object) -> list[str]:
    """Read one page and return its titles.

    Args:
        world: The test world.
        **kwargs: ``read_items`` arguments replacing the defaults.

    Returns:
        The page's titles, in order.
    """
    asked: dict[str, object] = {
        "category": None,
        "sort": LibrarySort.RECENT,
        "reversed_": False,
        "query": None,
        "page": 0,
    }
    asked.update(kwargs)
    page = world.service.read_items(world.actor, **asked)  # type: ignore[arg-type]
    return [entry.title for entry in page.items]


def _movie(world: World, title: str, tmdb: str, **kwargs: object) -> int:
    """Insert a live movie.

    Args:
        world: The test world.
        title: Its title.
        tmdb: Its TMDB id.
        **kwargs: More ``FixtureIndex.item`` arguments.

    Returns:
        Its row id.
    """
    item = world.index.item(title, tmdb=tmdb, **kwargs)  # type: ignore[arg-type]
    world.index.movie_file(item, f"films/{title}")
    return item


def test_page_size_and_a_page_past_the_end(world: World) -> None:
    """A page holds 24 rows; a page past the end is empty and ``matching`` does not change."""
    for n in range(30):
        _movie(world, f"Film {n:02d}", str(100 + n))

    first = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=0
    )
    second = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=1
    )
    past = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=5
    )

    assert LIBRARY_PAGE_SIZE == 24
    assert len(first.items) == 24
    assert len(second.items) == 6
    assert past.items == ()
    assert (past.matching, past.total, past.loaded) == (30, 30, 30)


def test_recent_is_the_default_order(world: World) -> None:
    """With no sort, the most recently added comes first; ``reversed`` turns it round."""
    _movie(world, "Old", "1", created=1_000)
    _movie(world, "New", "2", created=3_000)
    _movie(world, "Middle", "3", created=2_000)

    assert _titles(world) == ["New", "Middle", "Old"]
    assert _titles(world, reversed_=True) == ["Old", "Middle", "New"]


def test_az_is_the_french_collation(world: World) -> None:
    """« Élite » sorts between « Eagle » and « Eternals », whatever its normal form."""
    _movie(world, "Eternals", "1")
    _movie(world, unicodedata.normalize("NFD", ELITE), "2")
    _movie(world, "Zorro", "3")
    _movie(world, "Eagle", "4")
    _movie(world, SCREEN, "5")
    _movie(world, "Emma", "6")

    titles = _titles(world, sort=LibrarySort.AZ)

    assert [unicodedata.normalize("NFC", t) for t in titles] == ["Eagle", SCREEN, ELITE, "Emma", "Eternals", "Zorro"]
    assert [unicodedata.normalize("NFC", t) for t in _titles(world, sort=LibrarySort.AZ, reversed_=True)] == [
        "Zorro",
        "Eternals",
        "Emma",
        ELITE,
        SCREEN,
        "Eagle",
    ]


def test_az_reads_the_sort_title(world: World) -> None:
    """The alphabetical order reads ``title_sort`` (the article stripped), not the title."""
    _movie(world, "Le Parrain", "1", title_sort="Parrain")
    _movie(world, "Avatar", "2")
    _movie(world, "Mulan", "3")

    assert _titles(world, sort=LibrarySort.AZ) == ["Avatar", "Mulan", "Le Parrain"]


def test_missing_most_first_unknown_last(world: World) -> None:
    """« missing » puts the show missing most first, a complete one after, unknown (never catalogued, a movie) last."""
    aired = date(2026, 1, 1)
    two_missing = world.index.item("Two Missing", kind="show", tvdb="10", created=10)
    world.index.episodes(two_missing, 1, [1])
    catalogued(world.store, "tvdb", "10", {1: [aired, aired, aired]})
    complete = world.index.item("Complete", kind="show", tvdb="11", created=20)
    world.index.episodes(complete, 1, [1, 2])
    catalogued(world.store, "tvdb", "11", {1: [aired, aired]})
    one_missing = world.index.item("One Missing", kind="show", tvdb="12", created=30)
    world.index.episodes(one_missing, 1, [1])
    catalogued(world.store, "tvdb", "12", {1: [aired, aired]})
    unknown = world.index.item("Never Catalogued", kind="show", tvdb="13", created=40)
    world.index.episodes(unknown, 1, [1])
    _movie(world, "A Movie", "14", created=50)

    assert _titles(world, sort=LibrarySort.MISSING) == [
        "Two Missing",
        "One Missing",
        "Complete",
        "A Movie",
        "Never Catalogued",
    ]
    assert _titles(world, sort=LibrarySort.MISSING, reversed_=True) == [
        "Never Catalogued",
        "A Movie",
        "Complete",
        "One Missing",
        "Two Missing",
    ]


def test_missing_counts_aired_episodes_not_announced_ones(world: World) -> None:
    """An announced, not yet aired episode is not missing; one held beyond the catalogue offsets nothing."""
    show = world.index.item("Airing", kind="show", tvdb="20", created=10)
    world.index.episodes(show, 1, [1, 9])
    catalogued(world.store, "tvdb", "20", {1: [date(2026, 1, 1), date(2026, 10, 4), date(2027, 1, 1)]})
    other = world.index.item("Other", kind="show", tvdb="21", created=20)
    world.index.episodes(other, 1, [1])
    catalogued(world.store, "tvdb", "21", {1: [date(2026, 1, 1)]})

    # « Airing »: e1 and e2 aired (e2 airs today), e3 is announced; e1 held, e9 off the catalogue → 1 missing.
    assert _titles(world, sort=LibrarySort.MISSING) == ["Airing", "Other"]


def test_query_is_case_and_accent_insensitive(world: World) -> None:
    """« elite », « ÉLITE » and an NFD « Élite » all find the same row; the original title is searched too."""
    _movie(world, unicodedata.normalize("NFD", ELITE), "1")
    _movie(world, "La Casa de papel", "2", original_title="Money Heist")
    _movie(world, "Avatar", "3")

    held = [unicodedata.normalize("NFD", ELITE)]
    assert _titles(world, query="elite") == held
    assert _titles(world, query=ELITE.upper()) == held
    assert _titles(world, query=unicodedata.normalize("NFD", ELITE.lower())) == held
    assert _titles(world, query="heist") == ["La Casa de papel"]


def test_category_keeps_the_asked_leaves(world: World) -> None:
    """The lens sends its engine leaves; rows of other leaves are left out."""
    _movie(world, "Toy Story", "1", category="movies_animation")
    _movie(world, "Heat", "2", category="movies")
    show = world.index.item("Bluey", kind="show", tvdb="3", category="tv_shows_animation")
    world.index.episodes(show, 1, [1])

    assert sorted(_titles(world, category=["movies_animation", "tv_shows_animation"])) == ["Bluey", "Toy Story"]
    assert _titles(world, category=["movies"]) == ["Heat"]


def test_total_matching_and_loaded(world: World) -> None:
    """Unfiltered, the counts agree; filtered, ``total`` and ``matching`` are the answer, ``loaded`` the library."""
    _movie(world, "Avatar", "1")
    _movie(world, "Avatar 2", "2")
    _movie(world, "Heat", "3")

    unfiltered = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=0
    )
    filtered = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query="avatar", page=0
    )

    assert (unfiltered.total, unfiltered.matching, unfiltered.loaded) == (3, 3, 3)
    assert (filtered.total, filtered.matching, filtered.loaded) == (2, 2, 3)


def test_only_live_identified_rows_are_served(world: World) -> None:
    """A row with no live file, or with no provider id, is not a library entry."""
    _movie(world, "Live", "1")
    gone = world.index.item("Gone", tmdb="2")
    world.index.movie_file(gone, "films/Gone", deleted=True)
    world.index.item("Phantom", tmdb="3")
    unidentified = world.index.item("No Id")
    world.index.movie_file(unidentified, "films/No Id")

    page = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=0
    )

    assert [entry.title for entry in page.items] == ["Live"]
    assert page.loaded == 1


def test_an_entry_carries_its_facts(world: World) -> None:
    """An entry carries its year, kind, leaf, synopsis, every id and its poster URL."""
    item = world.index.item(
        "Outer Range",
        kind="show",
        year=2022,
        tvdb="391101",
        tmdb="113985",
        imdb="tt11685912",
        overview="A rancher finds a void.",
        poster_url="https://artworks.thetvdb.com/poster.jpg",
    )
    world.index.episodes(item, 1, [1])

    (entry,) = world.service.read_items(
        world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=0
    ).items

    assert entry.year == 2022
    assert entry.kind == "show"
    assert entry.category_id == "tv_shows"
    assert entry.overview == "A rancher finds a void."
    assert dict(entry.ids) == {"tvdb": 391101, "tmdb": 113985, "imdb": "tt11685912"}
    assert entry.poster_url == "https://artworks.thetvdb.com/poster.jpg"
    assert entry.local_poster is False


def test_a_show_with_no_nfo_poster_points_at_its_folder_poster(world: World) -> None:
    """No ``<thumb aspect="poster">`` in the NFO but a poster file in the folder: the entry says « local poster »."""
    item = world.index.item("Outer Range", kind="show", tvdb="391101", poster_url=None, poster_file=True)
    world.index.episodes(item, 1, [1])
    bare = world.index.item("Bare", kind="show", tvdb="391102", poster_url=None, poster_file=False)
    world.index.episodes(bare, 1, [1])

    entries = {
        entry.title: entry
        for entry in world.service.read_items(
            world.actor, category=None, sort=LibrarySort.RECENT, reversed_=False, query=None, page=0
        ).items
    }

    assert (entries["Outer Range"].poster_url, entries["Outer Range"].local_poster) == (None, True)
    assert (entries["Bare"].poster_url, entries["Bare"].local_poster) == (None, False)
