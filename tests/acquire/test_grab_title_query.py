"""Tests for the Follow D3 title-resolution query builder (``build_search_query``).

Before D3 the grab searched trackers with the bare numeric provider ID, which
title-based trackers (c411, torr9) never match → every wanted item abandoned.
``build_search_query`` turns a resolved series title into ``"{title} SxxEyy"``
(episodes) or ``"{title}"`` (movies), and falls back to the ID only when no
title is available.
"""

from dataclasses import dataclass

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import build_search_query, filter_to_episode
from personalscraper.core.identity import MediaRef


@dataclass
class _Result:
    """Minimal stand-in for a TrackerResult (only ``title`` is read here)."""

    title: str


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


class TestFilterToEpisode:
    """Only releases naming the exact SxxEyy survive (the wrong-episode fix)."""

    def _titles(self, results: list[_Result]) -> list[str]:
        return [r.title for r in results]

    def test_keeps_exact_episode_only(self) -> None:
        """S09E05 wanted keeps E05 (+ ranges), drops other episodes + packs."""
        res = [
            _Result("Rick.and.Morty.S09E01.MULTi"),
            _Result("Rick.and.Morty.S09E05.MULTi"),
            _Result("Rick.and.Morty.S09E05-E06"),
            _Result("Rick.and.Morty.S09.COMPLETE"),
        ]
        assert self._titles(filter_to_episode(res, 9, 5)) == [
            "Rick.and.Morty.S09E05.MULTi",
            "Rick.and.Morty.S09E05-E06",
        ]

    def test_regression_wrong_episode_dropped(self) -> None:
        """The observed bug: S09E05 want must NOT keep an S09E01 release."""
        res = [_Result("Rick.and.Morty.S09E01.MULTi.VFF.1080p")]
        assert filter_to_episode(res, 9, 5) == []

    def test_tolerates_zero_padding(self) -> None:
        """S9E5 and S09E05 both match; S09E50 does not (boundary)."""
        res = [_Result("Show.S9E5.x"), _Result("Show.S09E05.y"), _Result("Show.S09E50.z")]
        assert self._titles(filter_to_episode(res, 9, 5)) == ["Show.S9E5.x", "Show.S09E05.y"]

    def test_season_boundary_no_confusion(self) -> None:
        """S01E09 must not match S19E09 (leading digit is bounded)."""
        res = [_Result("Show.S19E09"), _Result("Show.S01E09")]
        assert self._titles(filter_to_episode(res, 1, 9)) == ["Show.S01E09"]

    def test_empty_when_nothing_matches(self) -> None:
        """No release names the episode → empty (grab abandons as no_matching_episode)."""
        assert filter_to_episode([_Result("Show.S09E01"), _Result("Show.S09E02")], 9, 5) == []
