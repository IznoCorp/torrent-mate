"""Movie title matching against TMDB.

The movie side of the scraper's identification step: the language/year fallback
chain, the year-window merge that rescues films excluded by TMDB's region-aware
``year=`` filter, and the ranking that produces the best
:class:`~personalscraper.scraper._match_score.MatchResult` plus the top-N
:class:`~personalscraper.scraper.decision_candidate.DecisionCandidate` list for
the scrape-arbiter decision queue.

Scoring primitives live in :mod:`personalscraper.scraper._match_score`; TV
matching lives in :mod:`personalscraper.scraper._match_tv`.
"""

from __future__ import annotations

from personalscraper.api.metadata._base import SearchResult
from personalscraper.logger import get_logger
from personalscraper.scraper._match_score import (
    AMBIGUITY_DELTA,
    LOW_CONFIDENCE,
    MatchResult,
    _best_scored_match,
    _filter_by_year_window,
    _merge_results,
    _results_to_candidates,
    _score_result,
)
from personalscraper.scraper.decision_candidate import DecisionCandidate

log = get_logger("confidence")


def _search_with_language(
    tmdb_client: object,
    title: str,
    year: int | None,
    language: str,
) -> list[SearchResult]:
    """Search TMDB with an explicit language override.

    Args:
        tmdb_client: TMDBClient instance.
        title: Movie title.
        year: Optional release year.
        language: Language code (e.g. "fr-FR", "en-US").

    Returns:
        List of SearchResult items.
    """
    return tmdb_client.search_movie(  # type: ignore[attr-defined,no-any-return]
        title, year, language=language
    )


def match_movie_detailed(
    tmdb_client: object,
    title: str,
    year: int | None,
) -> tuple[MatchResult | None, list[DecisionCandidate]]:
    """Detailed variant of :func:`match_movie` returning scored candidates.

    Same search chain and scoring as :func:`match_movie`, but additionally
    returns the top-5 scored candidates as :class:`DecisionCandidate`
    instances for the scrape-arbiter decision queue.  No additional API
    calls are made — only the data already present in the search results
    is used.

    Applies a chain of fallbacks when the initial search returns no results:
    1. fr-FR with year
    2. fr-FR without year (year window filter)
    3. en-US with year
    4. en-US without year (year window filter)

    Languages are read from the TMDB client configuration.

    Args:
        tmdb_client: TMDBClient instance (typed as object to avoid circular import).
        title: Movie title from the local folder.
        year: Release year (None if not detected).

    Returns:
        Tuple of (best :class:`MatchResult` or None, top-5
        :class:`DecisionCandidate` list).
    """
    # Read languages from the TMDB client config
    fr = getattr(tmdb_client, "_language", "fr-FR")
    en = getattr(tmdb_client, "_fallback_language", "en-US")

    results: list[SearchResult] = []
    fallback_event: str | None = None
    fallback_meta: dict[str, int | str] = {}

    # 1. Initial search: configured language + year (TMDB hard year filter)
    results = _search_with_language(tmdb_client, title, year, fr)

    # 1b. Year-window merge: TMDB's `year=` param matches ANY region's release
    #     date, so a film whose only release is off by a year from a
    #     similarly-titled film's *regional* release is silently excluded from
    #     the year-filtered results (e.g. "La Cité des Anges" with year=1997
    #     returned only "The Crow: City of Angels" 1996 — which has a 1997
    #     regional release — and excluded "City of Angels" 1998). When a year
    #     is present, always fetch the no-year candidates within the fallback
    #     window and merge them so the correct film survives to ranking, even
    #     when the year-filtered search already returned a (possibly wrong)
    #     result.
    if year is not None:
        windowed = _filter_by_year_window(_search_with_language(tmdb_client, title, None, fr), year)
        if windowed:
            before = len(results)
            results = _merge_results(results, windowed)
            if before == 0:
                # Year-filtered search found nothing; the window rescued it.
                fallback_event = "movie_match_year_fallback"
                fallback_meta = {"original_year": year}
            elif len(results) > before:
                # Year-filtered search returned results, but the window added
                # candidates that TMDB's year= filter had excluded.
                fallback_event = "movie_match_year_window_merged"
                fallback_meta = {
                    "original_year": year,
                    "added": len(results) - before,
                }

    # 3. Language fallback: fallback language + year
    if not results and en != fr:
        results = _search_with_language(tmdb_client, title, year, en)
        if results:
            fallback_event = "movie_match_language_fallback"
            fallback_meta = {"language": en}

    # 4. Year + language fallback: fallback language, no year filter
    if not results and year is not None and en != fr:
        no_year_candidates = _search_with_language(tmdb_client, title, None, en)
        results = _filter_by_year_window(no_year_candidates, year)
        if results:
            fallback_event = "movie_match_year_language_fallback"
            fallback_meta = {"original_year": year, "language": en}

    if not results:
        log.info("movie_no_tmdb_results", title=title, year=year)
        return None, []

    best_match = _best_scored_match(((title, r) for r in results), year, "tmdb")

    if best_match:
        if fallback_event:
            log.info(
                fallback_event,
                title=title,
                confidence=round(best_match.confidence, 2),
                candidates_count=len(results),
                **fallback_meta,
            )
        log.info(
            "movie_tmdb_match",
            title=title,
            api_title=best_match.api_title,
            api_year=best_match.api_year,
            confidence=round(best_match.confidence, 2),
        )
        if best_match.confidence < LOW_CONFIDENCE:
            log.warning(
                "scraper.match.below_threshold",
                title=title,
                year=year,
                candidates_count=len(results),
                top_score=round(best_match.confidence, 2),
                source="tmdb",
            )
        elif len(results) > 1:
            # Ambiguity guard (observability only — no acceptance change).
            ranked = sorted((_score_result(title, year, r) for r in results), reverse=True)
            if ranked[1] >= LOW_CONFIDENCE and ranked[0] - ranked[1] < AMBIGUITY_DELTA:
                log.warning(
                    "movie_match_ambiguous",
                    title=title,
                    top_score=round(ranked[0], 2),
                    runner_up=round(ranked[1], 2),
                    candidates_count=len(results),
                )

    candidates = _results_to_candidates(results, title, year)
    return best_match, candidates


def match_movie(
    tmdb_client: object,
    title: str,
    year: int | None,
) -> MatchResult | None:
    """Match a local movie against TMDB search results.

    Applies a chain of fallbacks when the initial search returns no results:
    1. fr-FR with year
    2. fr-FR without year (year window filter)
    3. en-US with year
    4. en-US without year (year window filter)

    Languages are read from the TMDB client configuration.

    Args:
        tmdb_client: TMDBClient instance (typed as object to avoid circular import).
        title: Movie title from the local folder.
        year: Release year (None if not detected).

    Returns:
        Best MatchResult, or None if no results found.
        Confidence threshold evaluation is left to the caller.
    """
    return match_movie_detailed(tmdb_client, title, year)[0]
