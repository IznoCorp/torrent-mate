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


def match_tvshow_tvdb(
    tvdb_client: object,
    title: str,
    year: int | None,
) -> MatchResult | None:
    """Match a local TV show against TVDB search results.

    TVDB is the primary provider for TV shows. Search results use
    snake_case fields and tvdb_id (string) as the identifier.

    Args:
        tvdb_client: TVDBClient instance.
        title: Show title from the local folder.
        year: First air date year (None if not detected).

    Returns:
        Best MatchResult with source="tvdb", or None if no results.
    """
    results = tvdb_client.search_series(title, year)  # type: ignore[attr-defined]
    if not results:
        logger.info("No TVDB results for show: %s (%s)", title, year)
        return None

    best_match: MatchResult | None = None
    best_score = -1.0

    for result in results:
        api_title = result.get("name", "")
        # TVDB search returns year as string in the "year" field
        year_str = result.get("year", "")
        api_year = int(year_str) if year_str and str(year_str).isdigit() else None

        score = score_match(title, year, api_title, api_year)

        if score > best_score:
            best_score = score
            # TVDB search uses tvdb_id (string), not id
            tvdb_id_str = result.get("tvdb_id", "")
            api_id = int(tvdb_id_str) if tvdb_id_str and str(tvdb_id_str).isdigit() else 0
            best_match = MatchResult(
                api_id=api_id,
                api_title=api_title,
                api_year=api_year,
                confidence=score,
                source="tvdb",
            )

    if best_match:
        logger.info(
            "Best TVDB match for '%s': '%s' (%s) — confidence %.2f",
            title, best_match.api_title, best_match.api_year, best_match.confidence,
        )

    return best_match


def match_tvshow(
    tvdb_client: object,
    tmdb_client: object,
    title: str,
    year: int | None,
) -> MatchResult | None:
    """Match a TV show using TVDB (primary) with TMDB fallback.

    Tries TVDB first. If TVDB returns no results or low confidence,
    falls back to TMDB search. Returns the best match from either.

    Args:
        tvdb_client: TVDBClient instance.
        tmdb_client: TMDBClient instance (fallback).
        title: Show title from the local folder.
        year: First air date year (None if not detected).

    Returns:
        Best MatchResult (source="tvdb" or "tmdb"), or None.
    """
    # Try TVDB first (primary for TV shows)
    tvdb_match = match_tvshow_tvdb(tvdb_client, title, year)
    if tvdb_match and tvdb_match.confidence >= HIGH_CONFIDENCE:
        return tvdb_match

    # Fallback to TMDB
    tmdb_results = tmdb_client.search_tv(title, year)  # type: ignore[attr-defined]
    tmdb_match: MatchResult | None = None
    best_score = -1.0

    for result in tmdb_results:
        api_title = result.get("name", "")
        first_air = result.get("first_air_date", "")
        api_year = int(first_air[:4]) if first_air and len(first_air) >= 4 else None

        score = score_match(title, year, api_title, api_year)
        if score > best_score:
            best_score = score
            tmdb_match = MatchResult(
                api_id=result["id"],
                api_title=api_title,
                api_year=api_year,
                confidence=score,
                source="tmdb",
            )

    if tmdb_match:
        logger.info(
            "TMDB fallback for '%s': '%s' (%s) — confidence %.2f",
            title, tmdb_match.api_title, tmdb_match.api_year, tmdb_match.confidence,
        )

    # Return whichever is better (TVDB preferred at equal confidence)
    if tvdb_match and tmdb_match:
        if tvdb_match.confidence >= tmdb_match.confidence:
            return tvdb_match
        return tmdb_match
    return tvdb_match or tmdb_match


def get_episode_titles(
    match: MatchResult,
    season: int,
    tvdb_client: object,
    tmdb_client: object,
    lang: str = "fra",
) -> dict[int, str]:
    """Get episode titles for a season from the matched provider.

    For TVDB matches: fetches episodes, then translates each one.
    For TMDB matches: episodes are already in the requested language.
    Falls back from French to English, then to the original title.

    Args:
        match: MatchResult from match_tvshow() or match_movie().
        season: Season number to fetch.
        tvdb_client: TVDBClient instance.
        tmdb_client: TMDBClient instance.
        lang: Target language code (3-char for TVDB, auto-converted).

    Returns:
        Dict mapping episode number to episode title.
        Empty dict if the season doesn't exist in the API.
    """
    titles: dict[int, str] = {}

    if match.source == "tvdb":
        episodes = tvdb_client.get_season_episodes(match.api_id, season)  # type: ignore[attr-defined]
        if not episodes:
            logger.warning("Season %d not found on TVDB for %s", season, match.api_title)
            return titles

        for ep in episodes:
            ep_num = ep.get("number", 0)
            ep_id = ep.get("id", 0)
            # Try French translation first
            translation = tvdb_client.get_episode_translation(ep_id, lang)  # type: ignore[attr-defined]
            if translation and translation.get("name"):
                titles[ep_num] = translation["name"]
            else:
                # Fallback to English translation
                en_trans = tvdb_client.get_episode_translation(ep_id, "eng")  # type: ignore[attr-defined]
                if en_trans and en_trans.get("name"):
                    titles[ep_num] = en_trans["name"]
                else:
                    # Final fallback: original name from episode data
                    titles[ep_num] = ep.get("name", f"Episode {ep_num}")

    elif match.source == "tmdb":
        season_data = tmdb_client.get_tv_season(match.api_id, season)  # type: ignore[attr-defined]
        episodes = season_data.get("episodes", [])
        if not episodes:
            logger.warning("Season %d not found on TMDB for %s", season, match.api_title)
            return titles

        for ep in episodes:
            ep_num = ep.get("episode_number", 0)
            # TMDB episodes are already in the requested language (fr-FR)
            titles[ep_num] = ep.get("name", f"Episode {ep_num}")

    return titles


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
