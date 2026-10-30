"""The library's other reads: categories, recent, incomplete, membership, seasons."""

from __future__ import annotations

from datetime import date

import pytest

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.app.errors import AppNotFound, RefusalCode
from personalscraper.app.library.reads import RECENT_LIMIT
from personalscraper.core.identity import MediaRef
from tests.unit.app.library.world import World, catalogued

_AIRED = date(2026, 1, 1)


def test_categories_count_live_entries_per_leaf(world: World) -> None:
    """Each engine leaf with live entries is counted; a tombstoned row counts nowhere."""
    for n, category in enumerate(["movies", "movies", "movies_animation"]):
        item = world.index.item(f"Film {n}", tmdb=str(n + 1), category=category)
        world.index.movie_file(item, f"films/{n}")
    gone = world.index.item("Gone", tmdb="9", category="standup")
    world.index.movie_file(gone, "films/gone", deleted=True)

    counts = {c.category_id: c.count for c in world.library.read_categories(world.actor)}

    assert counts == {"movies": 2, "movies_animation": 1}


def test_recent_is_twelve_rows_by_date_added(world: World) -> None:
    """Recent answers the twelve most recently added live entries, newest first, by creation date.

    The creation dates are scrambled against the insertion order, so ordering by row id fails.
    """
    for n in range(15):
        item = world.index.item(f"Film {n:02d}", tmdb=str(n + 1), created=1_000 + (n * 7) % 15)
        world.index.movie_file(item, f"films/{n}")

    recent = world.library.read_recent(world.actor)

    newest_first = sorted(range(15), key=lambda n: (n * 7) % 15, reverse=True)
    assert RECENT_LIMIT == 12
    assert [entry.title for entry in recent] == [f"Film {n:02d}" for n in newest_first[:12]]
    assert [entry.title for entry in recent] != [f"Film {n:02d}" for n in range(14, 2, -1)]


def test_incomplete_is_aired_beyond_owned_only(world: World) -> None:
    """A show missing an aired episode is incomplete; complete, never-catalogued and future-only are not."""
    holes = world.index.item("Holes", kind="show", tvdb="1", year=2019)
    world.index.episodes(holes, 1, [1])
    catalogued(world.store, "tvdb", "1", {1: [_AIRED, _AIRED, _AIRED]})
    complete = world.index.item("Complete", kind="show", tvdb="2")
    world.index.episodes(complete, 1, [1, 2])
    catalogued(world.store, "tvdb", "2", {1: [_AIRED, _AIRED]})
    unknown = world.index.item("Unknown", kind="show", tvdb="3")
    world.index.episodes(unknown, 1, [1])
    future = world.index.item("Future", kind="show", tvdb="4")
    world.index.episodes(future, 1, [1])
    catalogued(world.store, "tvdb", "4", {1: [_AIRED, date(2027, 1, 1)]})

    incomplete = world.library.read_incomplete(world.actor)

    assert [(i.entry.title, i.owned, i.aired) for i in incomplete] == [("Holes", 1, 3)]
    assert incomplete[0].entry.kind == "show"
    assert incomplete[0].entry.year == 2019


def test_incomplete_reads_a_tmdb_keyed_show_under_its_canonical_id(world: World) -> None:
    """A show the refresh keyed by TMDB (its canonical provider) is read under that key."""
    show = world.index.item("Tmdb Show", kind="show", tvdb="5", tmdb="50", canonical="tmdb")
    world.index.episodes(show, 1, [1])
    catalogued(world.store, "tmdb", "50", {1: [_AIRED, _AIRED]})

    assert [(i.entry.title, i.owned, i.aired) for i in world.library.read_incomplete(world.actor)] == [
        ("Tmdb Show", 1, 2)
    ]


def test_membership_of_a_show_by_tvdb(world: World) -> None:
    """A show is found by its TVDB id, with its ids, its kind and its holes."""
    show = world.index.item("Holes", kind="show", tvdb="1", tmdb="10")
    world.index.episodes(show, 1, [1])
    catalogued(world.store, "tvdb", "1", {1: [_AIRED, _AIRED]})

    membership = world.library.read_membership(world.actor, MediaRef(tvdb_id=1))

    assert membership.in_library is True
    assert membership.rows == 1
    assert membership.incomplete is True
    assert dict(membership.ids or {}) == {"tvdb": 1, "tmdb": 10}
    assert membership.kind == "show"


def test_membership_of_a_movie_by_tmdb(world: World) -> None:
    """A movie is found by its TMDB id; a movie is never incomplete."""
    movie = world.index.item("Heat", tmdb="949", imdb="tt0113277")
    world.index.movie_file(movie, "films/Heat")

    membership = world.library.read_membership(world.actor, MediaRef(tmdb_id=949))

    assert (membership.in_library, membership.rows, membership.incomplete, membership.kind) == (
        True,
        1,
        False,
        "movie",
    )
    assert dict(membership.ids or {}) == {"tmdb": 949, "imdb": "tt0113277"}


def test_membership_counts_a_duplicate_row(world: World) -> None:
    """An id held by a row with files and a 0-file phantom is two rows: a duplicate."""
    real = world.index.item("House of the Dragon (2022)", kind="show", tvdb="371572")
    world.index.episodes(real, 1, [1])
    world.index.item("House of the Dragon", kind="show", tvdb="371572")

    membership = world.library.read_membership(world.actor, MediaRef(tvdb_id=371572))

    assert membership.in_library is True
    assert membership.rows == 2


def test_membership_counts_one_row_in_two_folders(world: World) -> None:
    """One row whose live files lie in two media folders is a duplicate too."""
    friends = world.index.item("Friends", kind="show", tvdb="79168")
    world.index.episodes(friends, 1, [1], folder="series/Friends/Saison 01")
    world.index.episodes(friends, 2, [1], folder="series/Friends [UNCUT]/Saison 02", disk=2)

    assert world.library.read_membership(world.actor, MediaRef(tvdb_id=79168)).rows == 2


def test_membership_of_an_unknown_id(world: World) -> None:
    """An id no row holds: not in the library, no ids, no kind."""
    membership = world.library.read_membership(world.actor, MediaRef(tvdb_id=4242))

    assert (membership.in_library, membership.rows, membership.incomplete, membership.ids, membership.kind) == (
        False,
        0,
        False,
        None,
        None,
    )


def test_membership_of_a_tombstoned_row(world: World) -> None:
    """A row whose files are all tombstoned holds the id but is not in the library."""
    gone = world.index.item("Gone", tmdb="7")
    world.index.movie_file(gone, "films/Gone", deleted=True)

    membership = world.library.read_membership(world.actor, MediaRef(tmdb_id=7))

    assert (membership.in_library, membership.rows, membership.ids, membership.kind) == (False, 1, None, None)


def test_seasons_aired_by_date_and_off_catalogue(world: World) -> None:
    """``aired`` counts the episodes whose date has come; a held episode above the catalogue is off it."""
    show = world.index.item("Airing", kind="show", tvdb="30")
    world.index.episodes(show, 1, [1, 2])
    world.index.episodes(show, 2, [1, 4])
    catalogued(
        world.store,
        "tvdb",
        "30",
        {1: [date(2025, 1, 1), date(2025, 1, 8)], 2: [date(2026, 9, 1), date(2026, 10, 4), date(2026, 12, 1)]},
    )

    facts = world.library.read_seasons(world.actor, MediaRef(tvdb_id=30))

    assert [(s.number, s.episodes, s.air_date, s.off_catalogue) for s in facts.seasons] == [
        (1, 2, date(2025, 1, 1), ()),
        (2, 3, date(2026, 9, 1), (4,)),
    ]
    assert dict(facts.owned) == {1: (1, 2), 2: (1, 4)}
    assert dict(facts.aired) == {1: 2, 2: 2}


def test_seasons_of_a_show_never_catalogued(world: World) -> None:
    """Never catalogued: the held seasons are listed with nothing known of them, never « complete »."""
    show = world.index.item("Unknown", kind="show", tvdb="31")
    world.index.episodes(show, 1, [1, 2])

    facts = world.library.read_seasons(world.actor, MediaRef(tvdb_id=31))

    assert [(s.number, s.episodes, s.off_catalogue) for s in facts.seasons] == [(1, None, ())]
    assert dict(facts.owned) == {1: (1, 2)}
    assert dict(facts.aired) == {1: None}


def test_seasons_aired_is_null_when_no_episode_carries_a_date(world: World) -> None:
    """A season the catalogue lists with no dates has no aired count to give."""
    show = world.index.item("Undated", kind="show", tvdb="32")
    world.index.episodes(show, 1, [1])
    catalogued(world.store, "tvdb", "32", {1: [None, None]})

    assert dict(world.library.read_seasons(world.actor, MediaRef(tvdb_id=32)).aired) == {1: None}


def test_incomplete_joins_the_rows_of_one_identity(world: World) -> None:
    """Two live rows under one TVDB id, each holding one season, hold the show whole between them."""
    first = world.index.item("Split", kind="show", tvdb="40")
    world.index.episodes(first, 1, [1])
    second = world.index.item("Split [UNCUT]", kind="show", tvdb="40")
    world.index.episodes(second, 2, [1], disk=2)
    catalogued(world.store, "tvdb", "40", {1: [_AIRED], 2: [_AIRED]})

    assert world.library.read_incomplete(world.actor) == []


def test_seasons_of_an_id_no_provider_knows_is_not_found(world: World) -> None:
    """An id neither the library nor the provider holds answers ``media.not_found``, never empty seasons."""
    with pytest.raises(AppNotFound) as refusal:
        world.library.read_seasons(world.actor, MediaRef(tvdb_id=9999))

    assert refusal.value.code is RefusalCode.MEDIA_NOT_FOUND


def test_seasons_of_a_movie_is_not_found(world: World) -> None:
    """A movie's id names no show: ``media.not_found``."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")

    with pytest.raises(AppNotFound) as refusal:
        world.library.read_seasons(world.actor, MediaRef(tmdb_id=949))

    assert refusal.value.code is RefusalCode.MEDIA_NOT_FOUND


def test_seasons_of_an_imdb_id_the_library_does_not_hold_is_not_found(world: World) -> None:
    """No client reads seasons by an IMDb id the library does not hold: ``media.not_found``."""
    with pytest.raises(AppNotFound) as refusal:
        world.library.read_seasons(world.actor, MediaRef(imdb_id="tt0113277"))

    assert refusal.value.code is RefusalCode.MEDIA_NOT_FOUND


def _film_and_show_sharing_a_tmdb_id(world: World) -> None:
    """Hold one TMDB id twice: as a film and as a show (TMDB's two id spaces overlap)."""
    film = world.index.item("Film", tmdb="2290")
    world.index.movie_file(film, "films/Film")
    show = world.index.item("Show", kind="show", tvdb="77", tmdb="2290")
    world.index.episodes(show, 1, [1])


def test_membership_reads_one_kind_of_a_tmdb_id_held_by_a_film_and_a_show(world: World) -> None:
    """A TMDB id resolves to the movie holders first: the show sharing the number is no duplicate."""
    _film_and_show_sharing_a_tmdb_id(world)

    membership = world.library.read_membership(world.actor, MediaRef(tmdb_id=2290))

    assert (membership.rows, membership.kind, dict(membership.ids or {})) == (1, "movie", {"tmdb": 2290})


def test_membership_of_a_tvdb_id_is_a_show_only(world: World) -> None:
    """A TVDB id names a show, whatever a film's TMDB id may be."""
    _film_and_show_sharing_a_tmdb_id(world)

    membership = world.library.read_membership(world.actor, MediaRef(tvdb_id=77))

    assert (membership.rows, membership.kind) == (1, "show")


def test_seasons_of_a_tmdb_show_no_movie_holds_still_work(world: World) -> None:
    """A TMDB id held by a show alone resolves to the show holders."""
    show = world.index.item("Show", kind="show", tvdb="78", tmdb="2291")
    world.index.episodes(show, 1, [1, 2])

    facts = world.library.read_seasons(world.actor, MediaRef(tmdb_id=2291))

    assert dict(facts.owned) == {1: (1, 2)}


def test_the_sheet_of_a_shared_tmdb_id_is_the_films(world: World) -> None:
    """The sheet's held row is the film, not whichever row comes first."""
    show = world.index.item("Show", kind="show", tvdb="77", tmdb="2290")
    world.index.episodes(show, 1, [1])
    film = world.index.item("Film", tmdb="2290")
    world.index.movie_file(film, "films/Film")
    world.tmdb.movies["2290"] = MediaDetails(provider="tmdb", provider_id="2290", title="Film")

    sheet = world.sheets.read_sheet(world.actor, MediaRef(tmdb_id=2290))

    assert (sheet.kind, sheet.title) == ("movie", "Film")
