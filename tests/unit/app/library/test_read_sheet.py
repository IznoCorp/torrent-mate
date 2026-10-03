"""The media sheet's facts: a held movie, a held show, a medium the library does not hold, a provider down."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from personalscraper.api.metadata._base import ArtworkItem, MediaDetails, SeasonInfo
from personalscraper.app.errors import AppNotFound, AppUnavailable, RefusalCode
from personalscraper.app.library.facts import GenreId, MediaStatus
from personalscraper.core.identity import MediaRef
from tests.unit.app.library.world import World, catalogued


def _movie_details() -> MediaDetails:
    """TMDB's answer for « Heat »."""
    return MediaDetails(
        provider="tmdb",
        provider_id="949",
        title="Heat",
        year=1995,
        overview="Provider synopsis.",
        genres=["Action", "Crime", "Drame"],
        genre_ids=[28, 80, 18],
        runtime_minutes=170,
        rating=7.9,
        images=[
            ArtworkItem(type="poster", url="https://image.tmdb.org/poster.jpg"),
            ArtworkItem(type="backdrop", url="https://image.tmdb.org/backdrop.jpg"),
        ],
        external_ids={"imdb": "tt0113277"},
        director="Michael Mann",
        trailer_url="https://www.youtube.com/watch?v=0xbBLJ1WGwQ",
    )


def _show_details() -> MediaDetails:
    """TVDB's answer for « Outer Range »."""
    return MediaDetails(
        provider="tvdb",
        provider_id="391101",
        title="Outer Range",
        year=2022,
        overview="Provider synopsis.",
        genres=["Drama", "Science Fiction", "Western", "Soap"],
        seasons=[SeasonInfo(season_number=1, episode_count=8), SeasonInfo(season_number=2, episode_count=0)],
        external_ids={"tmdb": "113985", "imdb": "tt11685912"},
        series_status="Ended",
        creator="Brian Watkins",
    )


def test_a_held_movie(world: World) -> None:
    """The film variant: no seasons, no episodes, no TMDB television id; the NFO's synopsis wins."""
    movie = world.index.item("Heat", tmdb="949", year=1995, overview="Library synopsis.", provider_read=1_700_000_000.0)
    world.index.movie_file(movie, "films/Heat")
    world.tmdb.movies["949"] = _movie_details()

    sheet = world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))

    assert sheet.title == "Heat"
    assert sheet.kind == "movie"
    assert sheet.year == 1995
    assert sheet.rating == 7.9
    assert sheet.genres == (GenreId.ACTION, GenreId.CRIME, GenreId.DRAMA)
    assert sheet.runtime == 170
    assert sheet.overview == "Library synopsis."
    assert sheet.director == "Michael Mann"
    assert sheet.trailer_key == "0xbBLJ1WGwQ"
    assert dict(sheet.ids) == {"tmdb": 949, "imdb": "tt0113277"}
    assert sheet.owned is True
    assert (sheet.seasons, sheet.episodes, sheet.tmdb_television_id) == (None, None, None)
    assert sheet.poster_url == "https://image.tmdb.org/poster.jpg"
    assert sheet.hero_url == "https://image.tmdb.org/backdrop.jpg"
    assert sheet.local_poster is False
    assert sheet.cast is None
    assert sheet.cast_portraits is None
    assert world.tmdb.calls == [("movie", "949")]


def test_metadata_refreshed_at_is_the_provider_read_date(world: World) -> None:
    """« Metadata refreshed » is when the provider data was read (the NFO), never the scan's clock."""
    movie = world.index.item("Heat", tmdb="949", provider_read=1_700_000_000.0)
    world.index.movie_file(movie, "films/Heat")
    world.tmdb.movies["949"] = _movie_details()

    sheet = world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))

    assert sheet.metadata_refreshed_at == datetime.fromtimestamp(1_700_000_000.0).astimezone()


def test_a_held_show(world: World) -> None:
    """A show: status and genres as tokens, seasons from the provider, episodes from the catalogue."""
    show = world.index.item("Outer Range", kind="show", tvdb="391101", tmdb="113985", poster_url=None, poster_file=True)
    world.index.episodes(show, 1, [1, 2])
    catalogued(world.store, "tvdb", "391101", {1: [date(2022, 4, 15), date(2022, 4, 22)]})
    world.tvdb.shows["391101"] = _show_details()

    sheet = world.service.read_sheet(world.actor, MediaRef(tvdb_id=391101))

    assert sheet.kind == "show"
    assert sheet.status is MediaStatus.ENDED
    assert sheet.genres == (GenreId.DRAMA, GenreId.SCIENCE_FICTION, GenreId.WESTERN)
    assert sheet.creator == "Brian Watkins"
    assert sheet.owned is True
    assert sheet.tmdb_television_id == "113985"
    assert dict(sheet.ids) == {"tvdb": 391101, "tmdb": 113985, "imdb": "tt11685912"}
    assert [(s.number, s.episodes, s.air_date) for s in sheet.seasons or ()] == [
        (1, 8, date(2022, 4, 15)),
        (2, None, None),
    ]
    assert sheet.episodes is not None
    assert [(e.number, e.title, e.air_date) for e in sheet.episodes[1]] == [
        (1, "S1E1", date(2022, 4, 15)),
        (2, "S1E2", date(2022, 4, 22)),
    ]
    assert (sheet.poster_url, sheet.local_poster) == (None, True)
    assert sheet.metadata_refreshed_at is None


def test_a_medium_the_library_does_not_hold(world: World) -> None:
    """Opened from Découvrir: still answered, not owned; the show is asked first, the movie on its 404."""
    world.tmdb.movies["949"] = _movie_details()

    sheet = world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))

    assert sheet.owned is False
    assert sheet.kind == "movie"
    assert sheet.title == "Heat"
    assert sheet.overview == "Provider synopsis."
    assert world.tmdb.calls == [("tv", "949"), ("movie", "949")]


def test_an_id_no_provider_knows(world: World) -> None:
    """An id the provider answers 404 for, as a show and as a movie: ``media.not_found``."""
    with pytest.raises(AppNotFound) as refused:
        world.service.read_sheet(world.actor, MediaRef(tmdb_id=1))

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND


def test_an_imdb_id_the_library_does_not_hold(world: World) -> None:
    """No client reads a sheet by IMDb id: an IMDb id the library does not hold is not found."""
    with pytest.raises(AppNotFound) as refused:
        world.service.read_sheet(world.actor, MediaRef(imdb_id="tt0113277"))

    assert refused.value.code is RefusalCode.MEDIA_NOT_FOUND


def test_an_imdb_id_the_library_holds(world: World) -> None:
    """An IMDb id the library holds is read at the row's TMDB id."""
    movie = world.index.item("Heat", tmdb="949", imdb="tt0113277")
    world.index.movie_file(movie, "films/Heat")
    world.tmdb.movies["949"] = _movie_details()

    assert world.service.read_sheet(world.actor, MediaRef(imdb_id="tt0113277")).title == "Heat"


def test_a_provider_down(world: World) -> None:
    """A provider that does not answer: ``provider.unavailable``, never a 500."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")
    world.tmdb.down = True

    with pytest.raises(AppUnavailable) as refused:
        world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))

    assert refused.value.code is RefusalCode.PROVIDER_UNAVAILABLE
    assert refused.value.params == {"provider": "tmdb"}


def test_the_provider_answer_is_cached_five_minutes(world: World) -> None:
    """A second read within 300 s asks the provider nothing; past it, the provider is asked again."""
    movie = world.index.item("Heat", tmdb="949")
    world.index.movie_file(movie, "films/Heat")
    world.tmdb.movies["949"] = _movie_details()

    world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))
    world.clock[0] += 299
    world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))
    world.clock[0] += 2
    world.service.read_sheet(world.actor, MediaRef(tmdb_id=949))

    assert world.tmdb.calls == [("movie", "949"), ("movie", "949")]
