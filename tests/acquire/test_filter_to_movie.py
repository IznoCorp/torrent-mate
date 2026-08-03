"""acq-identity #28 — the movie grab must respect the added media's identity.

A bare movie title query (« Wicker ») pulls every « Wicker* » film from the
title-based trackers; with no provider-ID on a tracker result, ranking would
pick the highest-seeded one — a DIFFERENT film (the Wicker incident, §5/§7).
``filter_to_movie`` verifies each release's parsed title+year against the wanted
movie, and ``build_search_query`` narrows the query with the year.
"""

from __future__ import annotations

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.orchestrator import build_search_query, filter_to_movie
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.core.identity import MediaRef


def _result(title: str, seeders: int = 10) -> TrackerResult:
    """A TrackerResult with only the fields the filter reads (title)."""
    return TrackerResult(
        provider="c411",
        tracker_id=title[:8],
        title=title,
        size=ByteSize(4_000_000_000),
        seeders=seeders,
        leechers=0,
    )


def _movie(tvdb: int | None = None, tmdb: int | None = 1195803) -> WantedItem:
    """A movie WantedItem."""
    return WantedItem(
        media_ref=MediaRef(tvdb_id=tvdb, tmdb_id=tmdb),
        kind="movie",
        status="searching",
        enqueued_at=0,
    )


class TestFilterToMovie:
    """filter_to_movie keeps the wanted film, drops the wrong ones (#28)."""

    def test_wrong_year_film_is_dropped(self) -> None:
        """« Wicker » (2026) query returns « The Wicker Man » (2006) — dropped on year."""
        right = _result("Wicker.2026.1080p.WEB-DL.x265-GRP", seeders=5)
        wrong = _result("The.Wicker.Man.2006.1080p.BluRay.x264-OLD", seeders=999)
        kept = filter_to_movie([right, wrong], "Wicker", 2026)
        assert right in kept
        assert wrong not in kept, "a different-year film must never survive the identity filter"

    def test_high_seeded_wrong_film_never_wins(self) -> None:
        """Even a massively-seeded wrong-year release is filtered BEFORE ranking."""
        wrong = _result("Wicker.Park.2004.1080p.BluRay-XX", seeders=100000)
        kept = filter_to_movie([wrong], "Wicker", 2026)
        assert kept == []

    def test_matching_year_within_tolerance_kept(self) -> None:
        """A ±1-year release (production vs release year drift) survives."""
        near = _result("Wicker.2025.2160p.WEB-DL", seeders=3)
        assert near in filter_to_movie([near], "Wicker", 2026)

    def test_release_without_year_is_kept(self) -> None:
        """A release with no parseable year can't be refuted on the year axis."""
        no_year = _result("Wicker.1080p.WEB-DL.x265-GRP")
        assert no_year in filter_to_movie([no_year], "Wicker", 2026)

    def test_unrelated_title_is_dropped(self) -> None:
        """A wholly-unrelated film is dropped by the (loose) title guard."""
        unrelated = _result("Batman.2026.1080p.WEB-DL", seeders=50)
        assert unrelated not in filter_to_movie([unrelated], "Wicker", 2026)

    def test_no_year_wanted_disables_year_check(self) -> None:
        """When the follow has no year, only the title guard applies (degraded)."""
        a = _result("Wicker.2026.1080p")
        b = _result("The.Wicker.Man.2006.1080p")
        kept = filter_to_movie([a, b], "Wicker", None)
        # Both are title-similar and the year check is off → both survive.
        assert a in kept and b in kept


class TestMovieQueryYear:
    """build_search_query narrows a movie query with the year (#28)."""

    def test_movie_query_appends_year(self) -> None:
        """A movie query with a known year becomes « {title} {year} »."""
        assert build_search_query(_movie(), "Wicker", 2026) == "Wicker 2026"

    def test_movie_query_without_year_is_title_only(self) -> None:
        """A movie query with no year stays « {title} » (legacy)."""
        assert build_search_query(_movie(), "Wicker", None) == "Wicker"

    def test_episode_query_ignores_year(self) -> None:
        """An episode query is « {title} SxxEyy » — the year is not appended."""
        ep = WantedItem(
            media_ref=MediaRef(tvdb_id=382389),
            kind="episode",
            status="searching",
            enqueued_at=0,
            season=3,
            episode=9,
        )
        assert build_search_query(ep, "Star Trek", 2022) == "Star Trek S03E09"
