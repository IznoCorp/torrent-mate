"""Tests for the Follow D3 title-resolution query builder (``build_search_query``).

Before D3 the grab searched trackers with the bare numeric provider ID, which
title-based trackers (c411, torr9) never match → every wanted item abandoned.
``build_search_query`` turns a resolved series title into ``"{title} SxxEyy"``
(episodes) or ``"{title}"`` (movies), and falls back to the ID only when no
title is available.
"""

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import build_search_query
from personalscraper.core.identity import MediaRef


def _episode(tvdb: int, season: int, episode: int, followed_id: int | None = 1) -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb),
        kind="episode",
        status="pending",
        enqueued_at=0,
        followed_id=followed_id,
        season=season,
        episode=episode,
    )


def _movie(tvdb: int, followed_id: int | None = None) -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb),
        kind="movie",
        status="pending",
        enqueued_at=0,
        followed_id=followed_id,
        season=None,
        episode=None,
    )


class TestBuildSearchQuery:
    """The query is title-based when a title is resolved, ID-based otherwise."""

    def test_episode_with_title(self) -> None:
        """An episode with a resolved title → ``'{title} SxxEyy'`` (zero-padded)."""
        assert build_search_query(_episode(275274, 9, 4), "Rick and Morty") == "Rick and Morty S09E04"

    def test_episode_three_digit_episode(self) -> None:
        """Padding keeps ≥2 digits and does not truncate a 3-digit episode."""
        assert build_search_query(_episode(1, 2, 151), "Show") == "Show S02E151"

    def test_movie_with_title(self) -> None:
        """A movie with a resolved title → just the title (no SxxEyy)."""
        assert build_search_query(_movie(603), "The Matrix") == "The Matrix"

    def test_episode_no_title_falls_back_to_tvdb_id(self) -> None:
        """No title → the legacy bare-ID query (keeps it non-empty)."""
        assert build_search_query(_episode(275274, 9, 4), None) == "275274"

    def test_movie_no_title_falls_back_to_tvdb_id(self) -> None:
        """No title, movie → the bare ID too."""
        assert build_search_query(_movie(603), None) == "603"

    def test_fallback_prefers_tmdb_then_imdb(self) -> None:
        """When tvdb_id is absent the fallback walks tmdb → imdb."""
        item = WantedItem(
            media_ref=MediaRef(tmdb_id=42, imdb_id="tt0001"),
            kind="movie",
            status="pending",
            enqueued_at=0,
            followed_id=None,
            season=None,
            episode=None,
        )
        assert build_search_query(item, None) == "42"

    def test_episode_missing_numbers_uses_title_only(self) -> None:
        """A title-carrying episode with no season/episode degrades to the title."""
        item = WantedItem(
            media_ref=MediaRef(tvdb_id=1),
            kind="episode",
            status="pending",
            enqueued_at=0,
            followed_id=1,
            season=None,
            episode=None,
        )
        assert build_search_query(item, "Some Show") == "Some Show"
