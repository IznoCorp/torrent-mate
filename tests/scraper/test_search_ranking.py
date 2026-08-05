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
from personalscraper.scraper.search_ranking import rank_search_results

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
        """RC1: the target scored exactly 0.000 and sat at rank 27/50."""
        ranked = rank_search_results("monarch", _load("tvdb-search-monarch"), kind="tv", now_year=NOW_YEAR)
        top = ranked[0]
        assert top.result.provider_id == "422598"
        assert top.score > 0.0

    def test_spiderman_surfaces_brand_new_day(self) -> None:
        """RC1: the target scored exactly 0.000 and sat at rank 19/81."""
        ranked = rank_search_results(
            "spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR
        )
        assert ranked[0].result.provider_id == "969681"
        assert ranked[0].score > 0.0

    def test_no_mass_zero_score_tie_block(self) -> None:
        """RC1's real damage: 63/81 candidates tied at exactly 0.000.

        A tie block that large makes the ordering inside it arbitrary provider
        order, so truncation discards the right answer for no reason. A ranking
        that separates its candidates has almost none.
        """
        ranked = rank_search_results(
            "spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR
        )
        zeros = sum(1 for item in ranked if item.score == 0.0)
        assert zeros <= len(ranked) // 10

    def test_punctuation_does_not_change_the_answer(self) -> None:
        """`spiderman` and `spider man` must agree — the hyphen was decisive before.

        With the length-ratio guard, 'spiderman' scored 0.360 (rejected) while
        'spider-man' scored exactly 0.400 (accepted). The search result depended
        on how the operator typed the title.
        """
        joined = rank_search_results(
            "spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR
        )
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
        ranked = rank_search_results(
            "spiderman", _load("tmdb-search-movie-spiderman"), kind="movie", now_year=NOW_YEAR
        )
        scores = [item.score for item in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_every_candidate_survives_ranking(self) -> None:
        """Ranking reorders; it never drops. Truncation is the caller's decision."""
        lot = _load("tmdb-search-movie-spiderman")
        assert len(rank_search_results("spiderman", lot, kind="movie", now_year=NOW_YEAR)) == len(lot)
