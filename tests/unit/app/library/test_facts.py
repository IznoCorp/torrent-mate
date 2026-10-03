"""Provider facts mapped onto the contract's closed tokens."""

from __future__ import annotations

from personalscraper.api.metadata._base import ArtworkItem, MediaDetails
from personalscraper.app.library.facts import (
    GenreId,
    MediaStatus,
    genres_of,
    hero_of,
    status_of,
    trailer_key_of,
)


def test_tmdb_genres_are_read_by_id() -> None:
    """TMDB's localised names are ignored; its ids name the tokens, unknown ids are dropped."""
    details = MediaDetails(provider="tmdb", provider_id="1", genres=["Drame", "Soap"], genre_ids=[18, 10766, 10765])

    assert genres_of(details) == (GenreId.DRAMA, GenreId.SCI_FI_FANTASY)


def test_tvdb_genres_are_read_by_name() -> None:
    """TVDB's names, English or French, accents and case ignored; duplicates kept once."""
    details = MediaDetails(
        provider="tvdb", provider_id="1", genres=["Science Fiction", "Com\u00e9die", "Comedy", "Soap"]
    )

    assert genres_of(details) == (GenreId.SCIENCE_FICTION, GenreId.COMEDY)


def test_statuses() -> None:
    """TMDB's and TVDB's status names map to the tokens; an unknown one says nothing."""

    def status(raw: str | None) -> MediaStatus | None:
        return status_of(MediaDetails(provider="tmdb", provider_id="1", series_status=raw))

    assert status("Returning Series") is MediaStatus.CONTINUING
    assert status("Continuing") is MediaStatus.CONTINUING
    assert status("Ended") is MediaStatus.ENDED
    assert status("Canceled") is MediaStatus.CANCELED
    assert status("Upcoming") is MediaStatus.PLANNED
    assert status("In Production") is MediaStatus.IN_PRODUCTION
    assert status("Pilot") is None
    assert status(None) is None


def test_trailer_key() -> None:
    """The YouTube key is read out of the trailer URL."""

    def key(url: str | None) -> str | None:
        return trailer_key_of(MediaDetails(provider="tmdb", provider_id="1", trailer_url=url))

    assert key("https://www.youtube.com/watch?v=0xbBLJ1WGwQ") == "0xbBLJ1WGwQ"
    assert key("https://youtu.be/0xbBLJ1WGwQ") == "0xbBLJ1WGwQ"
    assert key("https://vimeo.com/1") is None
    assert key(None) is None


def test_hero_falls_back_to_the_top_level_backdrop() -> None:
    """The first backdrop image, else the provider's top-level backdrop."""
    with_image = MediaDetails(
        provider="tmdb",
        provider_id="1",
        images=[ArtworkItem(type="backdrop", url="https://a/b.jpg")],
        primary_backdrop_url="https://a/top.jpg",
    )
    without = MediaDetails(provider="tmdb", provider_id="1", primary_backdrop_url="https://a/top.jpg")

    assert hero_of(with_image) == "https://a/b.jpg"
    assert hero_of(without) == "https://a/top.jpg"
    assert hero_of(MediaDetails(provider="tmdb", provider_id="1")) is None
