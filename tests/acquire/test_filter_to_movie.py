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
        kept = filter_to_movie([right, wrong], ["Wicker"], 2026)
        assert right in kept
        assert wrong not in kept, "a different-year film must never survive the identity filter"

    def test_high_seeded_wrong_film_never_wins(self) -> None:
        """Even a massively-seeded wrong-year release is filtered BEFORE ranking."""
        wrong = _result("Wicker.Park.2004.1080p.BluRay-XX", seeders=100000)
        kept = filter_to_movie([wrong], ["Wicker"], 2026)
        assert kept == []

    def test_matching_year_within_tolerance_kept(self) -> None:
        """A ±1-year release (production vs release year drift) survives."""
        near = _result("Wicker.2025.2160p.WEB-DL", seeders=3)
        assert near in filter_to_movie([near], ["Wicker"], 2026)

    def test_release_without_year_is_kept(self) -> None:
        """A release with no parseable year can't be refuted on the year axis."""
        no_year = _result("Wicker.1080p.WEB-DL.x265-GRP")
        assert no_year in filter_to_movie([no_year], ["Wicker"], 2026)

    def test_unrelated_title_is_dropped(self) -> None:
        """A wholly-unrelated film is dropped by the (loose) title guard."""
        unrelated = _result("Batman.2026.1080p.WEB-DL", seeders=50)
        assert unrelated not in filter_to_movie([unrelated], ["Wicker"], 2026)

    def test_no_year_wanted_disables_year_check(self) -> None:
        """When the follow has no year, only the title guard applies (degraded)."""
        a = _result("Wicker.2026.1080p")
        b = _result("The.Wicker.Man.2006.1080p")
        kept = filter_to_movie([a, b], ["Wicker"], None)
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


class TestFilterToMovieCrossLanguage:
    """#435 — a release named in the ORIGINAL language must match the follow.

    The prod incident, verbatim: « Avant d'aller dormir » (tmdb 204922, 2014)
    is released as `Before.I.Go.To.Sleep.2014.MULTI.VFI...` on C411. With only
    the French display title, the guard scored 25 < 60 and dropped the correct
    film before the year — the real discriminator — was even consulted.
    """

    PROD_RELEASE = "Before.I.Go.To.Sleep.2014.MULTI.VFI.1080p.BluRay.EAC3.5.1.x265-notag"

    def test_prod_release_kept_with_both_titles(self) -> None:
        """The exact prod pair: display + original title → the release survives."""
        release = _result(self.PROD_RELEASE, seeders=7)
        kept = filter_to_movie([release], ["Avant d'aller dormir", "Before I Go to Sleep"], 2014)
        assert release in kept, "#435 regression: the original-title release must survive the identity filter"

    def test_prod_release_dropped_with_display_title_only(self) -> None:
        """Documents the pre-#435 hole: the French title alone rejects the film."""
        release = _result(self.PROD_RELEASE, seeders=7)
        assert filter_to_movie([release], ["Avant d'aller dormir"], 2014) == []

    def test_unrelated_release_still_dropped_with_both_titles(self) -> None:
        """The loose guard still drops the wholly-unrelated against EVERY title."""
        unrelated = _result("Batman.2014.1080p.WEB-DL", seeders=50)
        kept = filter_to_movie([unrelated], ["Avant d'aller dormir", "Before I Go to Sleep"], 2014)
        assert kept == []

    def test_wrong_year_still_dropped_despite_original_title_match(self) -> None:
        """The year discriminator survives the multi-title change intact."""
        remake = _result("Before.I.Go.To.Sleep.1998.1080p.BluRay-OLD", seeders=9)
        kept = filter_to_movie([remake], ["Avant d'aller dormir", "Before I Go to Sleep"], 2014)
        assert kept == []

    def test_a_bare_string_is_rejected(self) -> None:
        """A str is a Sequence[str] of CHARACTERS — the filter must refuse it loudly."""
        import pytest

        with pytest.raises(TypeError):
            filter_to_movie([_result(self.PROD_RELEASE)], "Avant d'aller dormir", 2014)  # type: ignore[arg-type]

    def test_empty_and_none_titles_are_ignored(self) -> None:
        """None/empty entries (no original title stored) degrade to the single-title behavior."""
        release = _result(self.PROD_RELEASE, seeders=7)
        kept = filter_to_movie([release], ["Avant d'aller dormir", ""], 2014)
        assert kept == []

    def test_all_empty_titles_fail_closed(self) -> None:
        """A nameless follow (every title empty/None) drops every parseable release.

        Review finding on the first cut of #435: filtering out empty entries
        and then short-circuiting on an empty list DISABLED the title guard for
        exactly the rows carrying the least identity — a nameless follow with
        no year would have grabbed the highest-seeded unrelated release (the
        Wicker class of incident). The guard must stay fail-closed, matching
        the pre-#435 behavior of a nameless row (score vs "" was 0 → drop all).
        """
        release = _result(self.PROD_RELEASE, seeders=7)
        assert filter_to_movie([release], ["", None], 2014) == []
        assert filter_to_movie([release], ["", None], None) == [], "no year AND no title must never fail open"
