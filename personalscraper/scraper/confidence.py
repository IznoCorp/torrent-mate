"""Confidence scoring and matching for media title identification (public façade).

This module is the stable import surface for scraper matching. The
implementation is split across three cohesive modules:

- :mod:`personalscraper.scraper._match_score` — shared scoring kernel
  (thresholds, :class:`MatchResult`, ``score_match``/``_score_result``, the
  candidate-building + best-of ranking helpers).
- :mod:`personalscraper.scraper._match_movie` — movie matching against TMDB.
- :mod:`personalscraper.scraper._match_tv` — TV matching (TVDB primary, TMDB
  fallback) + episode-title retrieval.

Everything those modules expose is re-exported here so existing callers and
test suites keep importing (and monkeypatching) ``personalscraper.scraper.
confidence.<name>`` unchanged. Only the interactive ``prompt_user_choice``
selector lives directly in this façade.

The media_processor from text_utils handles French accent stripping via NFD
decomposition — critical because rapidfuzz default_process does NOT strip
accents. See docs/rapidfuzz-reference.md for scorer details.
"""

from __future__ import annotations

import typer

from personalscraper.logger import get_logger
from personalscraper.scraper._match_movie import (
    _search_with_language,
    match_movie,
    match_movie_detailed,
)
from personalscraper.scraper._match_score import (
    AMBIGUITY_DELTA,
    HIGH_CONFIDENCE,
    LOW_CONFIDENCE,
    YEAR_FALLBACK_WINDOW,
    MatchResult,
    _best_scored_match,
    _filter_by_year_window,
    _length_ratio_guard,
    _merge_results,
    _result_to_match,
    _results_to_candidates,
    _score_result,
    _significant_tokens,
    _superstring_penalty,
    score_match,
)
from personalscraper.scraper._match_tv import (
    SEASON_VETO_BYPASS,
    _candidate_has_any_season,
    _match_tvshow_tmdb_detailed,
    _tv_fallback_title_variants,
    _tv_tmdb_candidates,
    get_episode_titles,
    match_tvshow,
    match_tvshow_detailed,
    match_tvshow_single,
    match_tvshow_tvdb,
    match_tvshow_tvdb_detailed,
)

log = get_logger("confidence")

__all__ = [
    # Thresholds / tuning constants
    "AMBIGUITY_DELTA",
    "HIGH_CONFIDENCE",
    "LOW_CONFIDENCE",
    "SEASON_VETO_BYPASS",
    "YEAR_FALLBACK_WINDOW",
    # Result container
    "MatchResult",
    # Shared scoring primitives
    "score_match",
    "_score_result",
    "_superstring_penalty",
    "_significant_tokens",
    "_length_ratio_guard",
    "_filter_by_year_window",
    "_merge_results",
    "_results_to_candidates",
    "_result_to_match",
    "_best_scored_match",
    # Movie matching
    "match_movie",
    "match_movie_detailed",
    "_search_with_language",
    # TV matching
    "match_tvshow",
    "match_tvshow_detailed",
    "match_tvshow_tvdb",
    "match_tvshow_tvdb_detailed",
    "match_tvshow_single",
    "_match_tvshow_tmdb_detailed",
    "_tv_tmdb_candidates",
    "_tv_fallback_title_variants",
    "_candidate_has_any_season",
    "get_episode_titles",
    # Interactive selection
    "prompt_user_choice",
]


def prompt_user_choice(
    results: list[MatchResult],
    local_title: str,
) -> MatchResult | None:
    """Prompt the user to choose from matching results (interactive mode).

    Displays numbered results with confidence scores and lets the user
    pick one or skip. Used when confidence is between LOW and HIGH
    thresholds and --interactive is enabled.

    Args:
        results: List of MatchResult candidates to display.
        local_title: Local media title for display context.

    Returns:
        Selected MatchResult, or None if the user chose to skip.
    """
    if not results:
        return None

    typer.echo(f"\nMatching: {local_title}")
    typer.echo("-" * 50)
    for i, r in enumerate(results, 1):
        year_str = f" ({r.api_year})" if r.api_year else ""
        typer.echo(f"  [{i}] {r.api_title}{year_str} — {r.confidence:.0%} [{r.source}]")
    typer.echo("  [0] Aucun de ces résultats")

    while True:
        try:
            choice = int(input("\nChoix : "))
        except EOFError:
            # Non-interactive context (launchd, cron) — skip prompt
            log.warning("prompt_non_interactive")
            return None
        except ValueError:
            continue
        if choice == 0:
            return None
        if 1 <= choice <= len(results):
            return results[choice - 1]
