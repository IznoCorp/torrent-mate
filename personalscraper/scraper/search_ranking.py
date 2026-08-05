"""Relevance ranking for the interactive media search.

This module answers a different question from the scrape matcher
(:mod:`personalscraper.scraper._match_score` and friends), and the distinction is
the whole reason it exists.

The scrape matcher decides **identity**: "is this release folder the same media as
this API result?". A folder name is a complete title, so a candidate whose title is
far longer than the query is evidence of a WRONG match — hence the length-ratio
guard and the superstring penalty, which are correct there.

This module decides **relevance**: "which media does this keyword mean?". An operator
types a short prefix precisely because they want the longer title back. Applying the
scrape guards here produced the defect diagnosed on 2026-08-05: 'monarch' scored
*Monarch: Legacy of Monsters* at exactly 0.000 (the guard skipped the title outright)
and 'spiderman' did the same to *Spider-Man: Brand New Day*, while 63 of 81
candidates tied at zero and the truncation to five discarded the right answer.

So the guards are absent here by design, replaced by positive prefix/subset bonuses,
and the ranking additionally consults popularity and recency — the signals that
separate four identically-titled unknown films from the one the operator meant.

Nothing in this module is imported by the scrape path.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from personalscraper.api.metadata._base import SearchResult
from personalscraper.text_utils import media_processor

# ── Scoring weights ───────────────────────────────────────────────────────────
# Calibrated against the golden set in tests/scraper/test_search_ranking.py — every
# change here must keep that set green. They sum to 1.0 so a score stays in [0, 1].
WEIGHT_TITLE = 0.55
WEIGHT_POPULARITY = 0.30
WEIGHT_RECENCY = 0.10
WEIGHT_EXACT = 0.05

# Positive signals replacing the scrape guards. A query that prefixes the candidate,
# or whose tokens are all present in it, is what a keyword search LOOKS like — the
# scrape path reads the same shape as evidence of a wrong match.
BONUS_PREFIX = 0.15
BONUS_TOKEN_SUBSET = 0.12

#: Age past which the recency component contributes nothing. Wide on purpose: a
#: 40-year-old classic should still be findable, just not boosted.
RECENCY_HORIZON_YEARS = 40


@dataclass(frozen=True)
class RankedResult:
    """A search result with its relevance score.

    Attributes:
        result: The provider search result, unmodified.
        score: Relevance score in [0.0, 1.0], higher is better.
    """

    result: SearchResult
    score: float


def _candidate_titles(result: SearchResult) -> list[str]:
    """Collect every title a query could legitimately match against.

    The localised title is not always the one the operator typed: a Hangul query
    matches '기생충' through ``original_title`` while the display title reads
    'Parasite'.

    Args:
        result: The provider search result.

    Returns:
        Non-empty titles: display, original, then aliases, de-duplicated.
    """
    titles = [result.title]
    if result.original_title and result.original_title not in titles:
        titles.append(result.original_title)
    titles.extend(alias for alias in result.aliases if alias and alias not in titles)
    return [t for t in titles if t]


def _title_similarity(query: str, result: SearchResult) -> float:
    """Best title similarity across the candidate's titles, with prefix bonuses.

    Deliberately has NO length-ratio guard and NO superstring penalty: both are
    correct for scrape identity and wrong for keyword retrieval (see module
    docstring).

    Args:
        query: The raw operator query.
        result: The candidate.

    Returns:
        Similarity in [0.0, 1.0].
    """
    # Imported here rather than at module scope so this module stays independent of
    # rapidfuzz's import cost for callers that only need the dataclass.
    from rapidfuzz import fuzz

    normalised_query = media_processor(query)
    if not normalised_query:
        return 0.0
    query_tokens = set(normalised_query.split())
    query_squashed = normalised_query.replace(" ", "")

    best = 0.0
    for title in _candidate_titles(result):
        normalised_title = media_processor(title)
        if not normalised_title:
            continue
        score = fuzz.WRatio(normalised_query, normalised_title) / 100.0

        bonus = 0.0
        if normalised_title.startswith(normalised_query):
            bonus = BONUS_PREFIX
        elif normalised_title.replace(" ", "").startswith(query_squashed):
            # 'spiderman' vs 'spider man': the same words, typed without the space.
            bonus = BONUS_PREFIX
        elif query_tokens and query_tokens <= set(normalised_title.split()):
            bonus = BONUS_TOKEN_SUBSET

        best = max(best, min(1.0, score + bonus))
    return best


def _popularity_component(result: SearchResult, log_max: float) -> float:
    """Normalise a provider popularity onto [0.0, 1.0].

    Logarithmic on purpose: TMDB popularities span three orders of magnitude
    (1990.6 for a current blockbuster against 0.31 for an obscure entry in the same
    result set), so a linear normalisation would flatten every non-blockbuster to
    approximately zero and hand the ranking entirely to one candidate.

    Args:
        result: The candidate.
        log_max: ``log1p`` of the highest popularity in the lot, or 0.0 when the
            whole lot lacks the signal (TVDB search carries none).

    Returns:
        Normalised popularity, or a neutral 0.0 when unknown.
    """
    if log_max <= 0.0 or result.popularity is None or result.popularity <= 0.0:
        return 0.0
    return min(1.0, math.log1p(result.popularity) / log_max)


def _recency_component(result: SearchResult, now_year: int) -> float:
    """Score how recent a candidate is, on [0.0, 1.0].

    Args:
        result: The candidate.
        now_year: The reference year (injected — never read from the clock, so the
            golden set cannot rot as the wall clock moves).

    Returns:
        1.0 for the current year, decaying to 0.0 at RECENCY_HORIZON_YEARS.
    """
    if result.year is None:
        return 0.0
    age = now_year - result.year
    if age < 0:
        # An announced-but-unreleased title is as current as it gets.
        return 1.0
    return max(0.0, 1.0 - age / RECENCY_HORIZON_YEARS)


def _exact_title_component(query: str, result: SearchResult) -> float:
    """1.0 when the query IS one of the candidate's titles, else 0.0.

    Args:
        query: The raw operator query.
        result: The candidate.

    Returns:
        1.0 on an exact normalised title match, otherwise 0.0.
    """
    normalised_query = media_processor(query)
    if not normalised_query:
        return 0.0
    return 1.0 if any(media_processor(t) == normalised_query for t in _candidate_titles(result)) else 0.0


def rank_search_results(
    query: str,
    results: list[SearchResult],
    *,
    kind: str,
    now_year: int,
) -> list[RankedResult]:
    """Rank provider search results by relevance to an operator query.

    Reorders; never drops. Truncation to a page is the caller's decision, so the
    caller can report an honest total (a search that silently discards candidates
    tells the operator they have seen everything when they have not).

    Args:
        query: The raw operator query.
        results: Provider search results, in provider order.
        kind: ``"movie"`` or ``"tv"`` — carried for the caller's tagging; the score
            itself is kind-agnostic.
        now_year: Reference year for the recency component.

    Returns:
        Every input result, wrapped with its score, best first. Ties keep provider
        order (the sort is stable), which is the least surprising fallback.
    """
    del kind  # Scoring is kind-agnostic; the parameter documents the caller's intent.
    if not results:
        return []

    popularities = [r.popularity for r in results if r.popularity is not None and r.popularity > 0.0]
    log_max = math.log1p(max(popularities)) if popularities else 0.0

    scored = [
        RankedResult(
            result=result,
            score=min(
                1.0,
                WEIGHT_TITLE * _title_similarity(query, result)
                + WEIGHT_POPULARITY * _popularity_component(result, log_max)
                + WEIGHT_RECENCY * _recency_component(result, now_year)
                + WEIGHT_EXACT * _exact_title_component(query, result),
            ),
        )
        for result in results
    ]
    scored.sort(key=lambda item: item.score, reverse=True)
    return scored
