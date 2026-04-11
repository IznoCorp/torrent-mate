"""Confidence scoring and matching for media title identification.

Combines rapidfuzz WRatio (title similarity) with year validation
to score API results against local media files. Used by both movie
matching (TMDB) and TV show matching (TVDB/TMDB fallback).

The media_processor from text_utils handles French accent stripping
via NFD decomposition — critical because rapidfuzz default_process
does NOT strip accents.

See docs/rapidfuzz-reference.md for scorer details.
"""

import logging
from dataclasses import dataclass

from rapidfuzz import fuzz

from personalscraper.text_utils import media_processor

logger = logging.getLogger(__name__)

# Confidence thresholds
HIGH_CONFIDENCE = 0.8  # Auto-accept in automatic mode
LOW_CONFIDENCE = 0.5   # Skip in automatic mode (no match)
# Between LOW and HIGH: caller decides (skip in auto, prompt in interactive)


@dataclass
class MatchResult:
    """Result of matching a local media item to an API result.

    Attributes:
        api_id: Provider-specific media ID (TMDB or TVDB).
        api_title: Title from the API result.
        api_year: Release year from the API result.
        confidence: Match confidence score (0.0 to 1.0).
        source: Provider name ("tmdb" or "tvdb").
    """

    api_id: int
    api_title: str
    api_year: int | None
    confidence: float
    source: str


def score_match(
    local_title: str,
    local_year: int | None,
    api_title: str,
    api_year: int | None,
) -> float:
    """Score a match between local media and an API result.

    Combines title similarity (rapidfuzz WRatio, 0-100 scaled to 0.0-1.0)
    with year validation (bonus for exact match, penalty for mismatch).

    WRatio auto-selects the best strategy among ratio, token_sort,
    token_set, and partial ratios — weighted by string length ratio.

    Args:
        local_title: Title extracted from the local filename/folder.
        local_year: Year extracted from the local filename (None if absent).
        api_title: Title from the API result.
        api_year: Year from the API result (None if absent).

    Returns:
        Confidence score between 0.0 and 1.0.
    """
    # Title similarity via WRatio with accent-stripping processor
    title_score = fuzz.WRatio(
        local_title, api_title, processor=media_processor,
    ) / 100.0

    # Year adjustment
    year_bonus = 0.0
    if local_year is not None and api_year is not None:
        year_diff = abs(local_year - api_year)
        if year_diff == 0:
            year_bonus = 0.1  # Exact year match
        elif year_diff == 1:
            year_bonus = 0.0  # Off by one — neutral (common for late-year releases)
        else:
            year_bonus = -0.15  # Different year — significant penalty

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, title_score + year_bonus))


def match_movie(
    tmdb_client: object,
    title: str,
    year: int | None,
) -> MatchResult | None:
    """Match a local movie against TMDB search results.

    Searches TMDB, scores each result, and returns the best match.
    The year parameter boosts TMDB relevance but does NOT filter strictly —
    client-side scoring validates the year.

    Args:
        tmdb_client: TMDBClient instance (typed as object to avoid circular import).
        title: Movie title from the local folder.
        year: Release year (None if not detected).

    Returns:
        Best MatchResult, or None if no results found.
        Confidence threshold evaluation is left to the caller.
    """
    results = tmdb_client.search_movie(title, year)  # type: ignore[attr-defined]
    if not results:
        logger.info("No TMDB results for movie: %s (%s)", title, year)
        return None

    best_match: MatchResult | None = None
    best_score = -1.0

    for result in results:
        api_title = result.get("title", "")
        # Extract year from release_date (format: "2024-06-28")
        release_date = result.get("release_date", "")
        api_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

        score = score_match(title, year, api_title, api_year)

        if score > best_score:
            best_score = score
            best_match = MatchResult(
                api_id=result["id"],
                api_title=api_title,
                api_year=api_year,
                confidence=score,
                source="tmdb",
            )

    if best_match:
        logger.info(
            "Best TMDB match for '%s': '%s' (%s) — confidence %.2f",
            title, best_match.api_title, best_match.api_year, best_match.confidence,
        )

    return best_match


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

    print(f"\nMatching: {local_title}")
    print("-" * 50)
    for i, r in enumerate(results, 1):
        year_str = f" ({r.api_year})" if r.api_year else ""
        print(f"  [{i}] {r.api_title}{year_str} — {r.confidence:.0%} [{r.source}]")
    print("  [0] Aucun de ces résultats")

    while True:
        try:
            choice = int(input("\nChoix : "))
        except (ValueError, EOFError):
            continue
        if choice == 0:
            return None
        if 1 <= choice <= len(results):
            return results[choice - 1]
