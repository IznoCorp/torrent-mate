"""Golden set for the interactive search ranking.

Every case below is a REAL query against a REAL provider payload captured by
``scripts/capture_search_fixtures.py``. That is deliberate: the defect these tests
guard against (the acquisition search served obscure media and hid mainstream ones)
came from scoring rules that read as reasonable in isolation and collapsed on real
data. A hand-written mock would have passed the broken code.

The two headline cases are the ones the operator reported on 2026-08-05:
``monarch`` never surfaced *Monarch: Legacy of Monsters* and ``spiderman`` never
surfaced *Spider-Man: Brand New Day* — both scored exactly 0.000 and were truncated
away, while the providers returned them at rank #3 and #1 of the raw results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from personalscraper.api.metadata._base import SearchResult
from personalscraper.api.metadata._tmdb_parsers import parse_search_result as parse_tmdb
from personalscraper.api.metadata._tvdb_parsers import parse_search_result as parse_tvdb
from personalscraper.api.metadata._tvdb_parsers import unwrap
from personalscraper.scraper.search_ranking import (
    gather_tv_candidates,
    merge_tv_results,
    rank_search_results,
)

FIXTURES = Path("tests/fixtures/search")

#: Year the golden set is scored against. Pinned so the recency component cannot
#: make these assertions drift as the wall clock moves.
NOW_YEAR = 2026


def _load(name: str) -> list[SearchResult]:
    """Parse a captured provider payload into SearchResult objects.

    Args:
        name: Fixture basename, e.g. ``tmdb-search-movie-monarch``.

    Returns:
        The parsed search results, in provider order.
    """
    raw: Any = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    if name.startswith("tvdb-"):
        return [parse_tvdb(item, "tvdb") for item in unwrap(raw)]
    return [parse_tmdb(item, "tmdb") for item in raw["results"]]


def _rank_of(ranked: list[Any], provider_id: str) -> int:
    """Return the 1-based rank of a provider id, or a large sentinel when absent.

    Args:
        ranked: The ranked results.
        provider_id: The provider id to locate.

    Returns:
        1-based rank, or 9999 when the id is not present at all.
    """
    for position, item in enumerate(ranked, start=1):
        if item.result.provider_id == str(provider_id):
            return position
    return 9999


# (fixture, query, kind, target provider_id, target label, max acceptable rank)
GOLDEN: tuple[tuple[str, str, str, str, str, int], ...] = (
    ("tvdb-search-monarch", "monarch", "tv", "422598", "Monarch: Legacy of Monsters", 3),
    ("tmdb-search-tv-monarch", "monarch", "tv", "202411", "Monarch: Legacy of Monsters", 3),
    ("tmdb-search-movie-spiderman", "spiderman", "movie", "969681", "Spider-Man: Brand New Day", 3),
    ("tmdb-search-movie-spider-man", "spider man", "movie", "969681", "Spider-Man: Brand New Day", 3),
    ("tmdb-search-movie-matrix", "matrix", "movie", "603", "Matrix (1999)", 3),
    ("tmdb-search-tv-top-chef", "top chef", "tv", "41822", "Top Chef (US)", 3),
    ("tmdb-search-movie-les-evades", "les evades", "movie", "278", "Les Évadés (1994)", 3),
    ("tmdb-search-movie-hangul-parasite", "기생충", "movie", "496243", "Parasite", 5),
    ("tmdb-search-tv-kanji-attack-on-titan", "進撃の巨人", "tv", "1429", "L'Attaque des Titans", 5),
)


class TestGoldenSet:
    """A real query surfaces the media a human meant."""

    @pytest.mark.parametrize(("fixture", "query", "kind", "target", "label", "max_rank"), GOLDEN)
    def test_target_is_near_the_top(
        self,
        fixture: str,
        query: str,
        kind: str,
        target: str,
        label: str,
        max_rank: int,
    ) -> None:
        """The media the query means ranks within the first few results."""
        ranked = rank_search_results(query, _load(fixture), kind=kind, now_year=NOW_YEAR)
        rank = _rank_of(ranked, target)
        assert rank <= max_rank, f"{label} ranked {rank} for {query!r} (max {max_rank})"


class TestReportedRegressions:
    """The two cases the operator reported — each has its own reproducing test."""

    def test_monarch_surfaces_legacy_of_monsters(self) -> None:
        """RC1: the target scored exactly 0.000 and sat at rank 27/50 on TVDB.

        On the TVDB payload ALONE the target reaches the top of the list but does
        not take first place: TVDB exposes no popularity, so the only separators
        left are title similarity and recency, and the exact-title homonym
        'Monarch' (2022) legitimately edges it. Ranking it FIRST needs TMDB's
        popularity signal — which is what the TVDB ∪ TMDB union delivers, and
        `TestUnionRanking` asserts there. Claiming first place here would be
        asking a provider without the data to produce the answer anyway.
        """
        ranked = rank_search_results("monarch", _load("tvdb-search-monarch"), kind="tv", now_year=NOW_YEAR)
        rank = _rank_of(ranked, "422598")
        assert rank <= 2, f"target ranked {rank} (was 27/50 with score 0.000 before the fix)"
        assert ranked[rank - 1].score > 0.0

    def test_monarch_takes_first_place_on_the_tmdb_payload(self) -> None:
        """The same query on TMDB, where the popularity signal exists."""
        ranked = rank_search_results("monarch", _load("tmdb-search-tv-monarch"), kind="tv", now_year=NOW_YEAR)
        assert ranked[0].result.provider_id == "202411"
        assert ranked[0].score > 0.0

    def test_spiderman_surfaces_brand_new_day(self) -> None:
        """RC1: the target scored exactly 0.000 and sat at rank 19/81."""
        ranked = rank_search_results("spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR)
        assert ranked[0].result.provider_id == "969681"
        assert ranked[0].score > 0.0

    def test_no_mass_zero_score_tie_block(self) -> None:
        """RC1's real damage: 63/81 candidates tied at exactly 0.000.

        A tie block that large makes the ordering inside it arbitrary provider
        order, so truncation discards the right answer for no reason. A ranking
        that separates its candidates has almost none.
        """
        ranked = rank_search_results("spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR)
        zeros = sum(1 for item in ranked if item.score == 0.0)
        assert zeros <= len(ranked) // 10

    def test_punctuation_does_not_change_the_answer(self) -> None:
        """`spiderman` and `spider man` must agree — the hyphen was decisive before.

        With the length-ratio guard, 'spiderman' scored 0.360 (rejected) while
        'spider-man' scored exactly 0.400 (accepted). The search result depended
        on how the operator typed the title.
        """
        joined = rank_search_results("spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR)
        spaced = rank_search_results(
            "spider man", _load("tmdb-search-movie-spider-man"), kind="movie", now_year=NOW_YEAR
        )
        assert _rank_of(joined, "969681") == _rank_of(spaced, "969681")


class TestPopularityDiscriminates:
    """Popularity is what separates same-title candidates (RC4)."""

    def test_famous_homonym_beats_the_obscure_one(self) -> None:
        """Two films are titled 'Les Évadés'; only one is The Shawshank Redemption.

        Title similarity alone scores them identically — 1.000 each. Without the
        popularity term the winner is decided by provider ordering, which is
        exactly how four unknown 'Monarch' films came to fill the results.
        """
        ranked = rank_search_results(
            "les evades", _load("tmdb-search-movie-les-evades"), kind="movie", now_year=NOW_YEAR
        )
        assert _rank_of(ranked, "278") < _rank_of(ranked, "202695")

    def test_original_title_carries_non_latin_queries(self) -> None:
        """A Hangul query matches through original_title, not the localised title."""
        ranked = rank_search_results(
            "기생충", _load("tmdb-search-movie-hangul-parasite"), kind="movie", now_year=NOW_YEAR
        )
        assert ranked[0].result.provider_id == "496243"


class TestEdgeCases:
    """Nothing here may raise — a search is an operator-facing surface."""

    def test_empty_result_set(self) -> None:
        """No candidates yields no ranking."""
        assert rank_search_results("anything", [], kind="movie", now_year=NOW_YEAR) == []

    def test_empty_query(self) -> None:
        """An empty query does not crash and does not invent an order."""
        ranked = rank_search_results("", _load("tmdb-search-movie-matrix"), kind="movie", now_year=NOW_YEAR)
        assert len(ranked) == len(_load("tmdb-search-movie-matrix"))

    def test_single_character_query(self) -> None:
        """A one-character query is degenerate but must still return."""
        ranked = rank_search_results("m", _load("tmdb-search-movie-matrix"), kind="movie", now_year=NOW_YEAR)
        assert len(ranked) > 0

    def test_candidate_without_year_or_popularity(self) -> None:
        """Missing signals degrade the score, they never raise."""
        bare = SearchResult(provider="tmdb", provider_id="1", title="Matrix", media_type="movie")
        ranked = rank_search_results("matrix", [bare], kind="movie", now_year=NOW_YEAR)
        assert len(ranked) == 1
        assert ranked[0].score > 0.0

    def test_all_candidates_without_popularity(self) -> None:
        """A TVDB-only lot has no popularity at all — normalisation must not divide by zero."""
        lot = [
            SearchResult(provider="tvdb", provider_id="1", title="Monarch", year=2022, media_type="tv"),
            SearchResult(
                provider="tvdb",
                provider_id="2",
                title="Monarch: Legacy of Monsters",
                year=2023,
                media_type="tv",
            ),
        ]
        ranked = rank_search_results("monarch", lot, kind="tv", now_year=NOW_YEAR)
        assert len(ranked) == 2
        assert all(item.score > 0.0 for item in ranked)

    def test_scores_are_sorted_descending(self) -> None:
        """The contract is a ranking, not a bag."""
        ranked = rank_search_results("spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR)
        scores = [item.score for item in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_every_candidate_survives_ranking(self) -> None:
        """Ranking reorders; it never drops. Truncation is the caller's decision."""
        lot = _load("tmdb-search-movie-spiderman")
        assert len(rank_search_results("spiderman", lot, kind="movie", now_year=NOW_YEAR)) == len(lot)


class TestUnionRanking:
    """TV search merges TVDB and TMDB — TVDB alone cannot rank (RC5).

    ``match_tvshow_detailed`` returns as soon as TVDB yields anything, and the TVDB
    branch takes ``scored[0]`` with no threshold — so a single junk TVDB row blocked
    TMDB entirely. On 'monarch' that cost the operator the right answer: TMDB ranked
    *Monarch: Legacy of Monsters* first (popularity 34.4, 1368 votes) while TVDB,
    which publishes no popularity at all, could only offer title similarity.
    """

    def test_union_puts_the_target_first(self) -> None:
        """Merged, the target takes first place — neither provider does alone."""
        merged = merge_tv_results(_load("tvdb-search-monarch"), _load("tmdb-search-tv-monarch"))
        ranked = rank_search_results("monarch", merged, kind="tv", now_year=NOW_YEAR)
        assert ranked[0].result.title.startswith("Monarch: Legacy of Monsters")

    def test_merged_target_keeps_the_tvdb_identity(self) -> None:
        """The follow id must stay TVDB (§5: identity is the id chosen at add time)."""
        merged = merge_tv_results(_load("tvdb-search-monarch"), _load("tmdb-search-tv-monarch"))
        ranked = rank_search_results("monarch", merged, kind="tv", now_year=NOW_YEAR)
        assert ranked[0].result.provider == "tvdb"
        assert ranked[0].result.provider_id == "422598"

    def test_merged_target_carries_the_tmdb_popularity(self) -> None:
        """The TVDB row is grafted with TMDB's popularity — that is the whole point."""
        merged = merge_tv_results(_load("tvdb-search-monarch"), _load("tmdb-search-tv-monarch"))
        target = next(r for r in merged if r.provider_id == "422598")
        assert target.popularity is not None
        assert target.popularity > 0.0

    def test_dedup_by_external_id_yields_one_row(self) -> None:
        """remote_ids names the TMDB counterpart — one media, one row."""
        merged = merge_tv_results(_load("tvdb-search-monarch"), _load("tmdb-search-tv-monarch"))
        assert sum(1 for r in merged if "Legacy of Monsters" in r.title) == 1

    def test_dedup_by_title_and_year_when_external_id_absent(self) -> None:
        """10 of 50 live TVDB rows carry no remote_ids — fall back to title+year."""
        tvdb = [SearchResult(provider="tvdb", provider_id="9", title="Monarch", year=2022, media_type="tv")]
        tmdb = [
            SearchResult(
                provider="tmdb",
                provider_id="125713",
                title="Monarch",
                year=2022,
                media_type="tv",
                popularity=4.2,
            )
        ]
        merged = merge_tv_results(tvdb, tmdb)
        assert len(merged) == 1
        assert merged[0].provider == "tvdb"
        assert merged[0].popularity == 4.2

    def test_unmatched_rows_are_kept_not_dropped(self) -> None:
        """When nothing correlates, show both. Losing a row is worse than showing two.

        The operator can arbitrate between two candidates on screen; they cannot
        arbitrate one that silently vanished.
        """
        tvdb = [SearchResult(provider="tvdb", provider_id="9", title="Alpha", year=2001, media_type="tv")]
        tmdb = [SearchResult(provider="tmdb", provider_id="8", title="Beta", year=2015, media_type="tv")]
        merged = merge_tv_results(tvdb, tmdb)
        assert len(merged) == 2

    def test_tmdb_only_series_survives_with_tmdb_identity(self) -> None:
        """A show TVDB does not know is better followed by TMDB id than invisible."""
        tmdb = [SearchResult(provider="tmdb", provider_id="777", title="Gamma", year=2024, media_type="tv")]
        merged = merge_tv_results([], tmdb)
        assert len(merged) == 1
        assert merged[0].provider == "tmdb"

    def test_empty_both_sides(self) -> None:
        """No candidates anywhere yields no rows, not an exception."""
        assert merge_tv_results([], []) == []


class TestProviderFailSoft:
    """One provider failing degrades the search; it never kills it — and it is logged."""

    class _Boom:
        """A client whose search always raises."""

        def search_series(self, query: str, year: int | None) -> list[SearchResult]:
            raise RuntimeError("tvdb down")

        def search_tv(self, query: str, year: int | None) -> list[SearchResult]:
            raise RuntimeError("tmdb down")

    class _Ok:
        """A client returning one canned row."""

        def __init__(self, row: SearchResult) -> None:
            self.row = row

        def search_series(self, query: str, year: int | None) -> list[SearchResult]:
            return [self.row]

        def search_tv(self, query: str, year: int | None) -> list[SearchResult]:
            return [self.row]

    def test_tvdb_failure_still_serves_tmdb(self, caplog: pytest.LogCaptureFixture) -> None:
        """TVDB down: the TMDB rows are still served, and the failure is logged."""
        row = SearchResult(provider="tmdb", provider_id="1", title="Monarch", year=2023, media_type="tv")
        with caplog.at_level("WARNING"):
            out = gather_tv_candidates(self._Boom(), self._Ok(row), "monarch")
        assert [r.provider for r in out] == ["tmdb"]
        assert "search_tv_provider_degraded" in caplog.text

    def test_tmdb_failure_still_serves_tvdb(self, caplog: pytest.LogCaptureFixture) -> None:
        """TMDB down: the TVDB rows are still served, and the failure is logged."""
        row = SearchResult(provider="tvdb", provider_id="2", title="Monarch", year=2023, media_type="tv")
        with caplog.at_level("WARNING"):
            out = gather_tv_candidates(self._Ok(row), self._Boom(), "monarch")
        assert [r.provider for r in out] == ["tvdb"]
        assert "search_tv_provider_degraded" in caplog.text

    def test_both_down_returns_empty_without_raising(self) -> None:
        """Total provider outage yields no candidates — never an exception."""
        assert gather_tv_candidates(self._Boom(), self._Boom(), "monarch") == []


class TestYearAgreement:
    """The resolution deck knows a year; the acquisition search does not (DESIGN §8)."""

    @staticmethod
    def _pair() -> list[SearchResult]:
        """Two same-title films a decade apart."""
        return [
            SearchResult(provider="tmdb", provider_id="1", title="Alpha", year=1999, media_type="movie"),
            SearchResult(provider="tmdb", provider_id="2", title="Alpha", year=2011, media_type="movie"),
        ]

    def test_matching_year_wins(self) -> None:
        """With a year in hand, the matching release comes first."""
        ranked = rank_search_results("Alpha", self._pair(), kind="movie", now_year=NOW_YEAR, query_year=1999)
        assert ranked[0].result.provider_id == "1"

    def test_without_a_year_recency_decides(self) -> None:
        """No year supplied: the term vanishes and the newer release leads."""
        ranked = rank_search_results("Alpha", self._pair(), kind="movie", now_year=NOW_YEAR)
        assert ranked[0].result.provider_id == "2"

    def test_year_mismatch_demotes_but_never_rejects(self) -> None:
        """A wrong year must not delete a candidate — a remake stays findable.

        This is the deliberate difference from the scrape matcher, where a year
        mismatch is grounds for rejection because identity is the question.
        """
        ranked = rank_search_results("Alpha", self._pair(), kind="movie", now_year=NOW_YEAR, query_year=1999)
        assert len(ranked) == 2
        assert all(item.score > 0.0 for item in ranked)

    def test_off_by_one_year_is_neutral(self) -> None:
        """Regional release dates straddle year boundaries; ±1 must not penalise."""
        lot = [SearchResult(provider="tmdb", provider_id="1", title="Alpha", year=2000, media_type="movie")]
        exact = rank_search_results("Alpha", lot, kind="movie", now_year=NOW_YEAR, query_year=2001)
        far = rank_search_results("Alpha", lot, kind="movie", now_year=NOW_YEAR, query_year=2010)
        assert exact[0].score > far[0].score
