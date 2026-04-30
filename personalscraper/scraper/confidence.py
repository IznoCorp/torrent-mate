"""Confidence scoring and matching for media title identification.

Combines rapidfuzz WRatio (title similarity) with year validation
to score API results against local media files. Used by both movie
matching (TMDB) and TV show matching (TVDB/TMDB fallback).

The media_processor from text_utils handles French accent stripping
via NFD decomposition — critical because rapidfuzz default_process
does NOT strip accents.

See docs/rapidfuzz-reference.md for scorer details.
"""

from dataclasses import dataclass

import typer
from rapidfuzz import fuzz

from personalscraper.logger import get_logger
from personalscraper.text_utils import media_processor

log = get_logger("confidence")

# Confidence thresholds
HIGH_CONFIDENCE = 0.8  # Auto-accept in automatic mode
LOW_CONFIDENCE = 0.5  # Skip in automatic mode (no match)
# Between LOW and HIGH: caller decides (skip in auto, prompt in interactive)

# Above this fuzzy score, the content-aware season veto in
# match_tvshow_tvdb is bypassed: a 0.95+ title match is treated as
# unambiguous, even if the candidate's catalog does not cover the
# observed seasons (common for spin-offs whose releases mirror the
# main show's season numbering — e.g. S17 labels on a show with
# its own S01..S04 catalog).
SEASON_VETO_BYPASS = 0.95


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
    title_score = (
        fuzz.WRatio(
            local_title,
            api_title,
            processor=media_processor,
        )
        / 100.0
    )

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
        log.info("movie_no_tmdb_results", title=title, year=year)
        return None

    best_match: MatchResult | None = None
    best_score = -1.0

    for result in results:
        api_title = result.get("title", "")
        # Extract year from release_date (format: "2024-06-28")
        release_date = result.get("release_date", "")
        api_year = int(release_date[:4]) if release_date and len(release_date) >= 4 else None

        candidate_titles = [api_title]
        original_title = result.get("original_title", "")
        if original_title and original_title not in candidate_titles:
            candidate_titles.append(original_title)

        score = max(score_match(title, year, candidate_title, api_year) for candidate_title in candidate_titles)

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
        log.info(
            "movie_tmdb_match",
            title=title,
            api_title=best_match.api_title,
            api_year=best_match.api_year,
            confidence=round(best_match.confidence, 2),
        )
        # Warn early when the best candidate is below the acceptance threshold —
        # the caller will ultimately skip the item, but logging here captures
        # the candidates_count that the caller cannot see.
        if best_match.confidence < LOW_CONFIDENCE:
            log.warning(
                "scraper.match.below_threshold",
                title=title,
                year=year,
                candidates_count=len(results),
                top_score=round(best_match.confidence, 2),
                source="tmdb",
            )

    return best_match


def _candidate_has_any_season(
    tvdb_client: object,
    tvdb_id: int,
    wanted_seasons: set[int],
) -> bool:
    """Return True if a TVDB candidate's catalog covers any wanted season.

    Content-aware disambiguation: when several shows share a common keyword
    (e.g. "Top Chef"), the one whose catalog actually contains the seasons
    present in the local folder is almost certainly the right show. A 2016
    one-season spin-off cannot be the match for a file tagged S17.

    Args:
        tvdb_client: TVDBClient instance.
        tvdb_id: Candidate's TVDB series id.
        wanted_seasons: Seasons observed in the local folder.

    Returns:
        True if at least one wanted season exists in the candidate's
        TVDB seasons list. On any API error, returns True — we refuse to
        reject a candidate over a transient fetch failure.
    """
    if not wanted_seasons or tvdb_id <= 0:
        return True
    try:
        series = tvdb_client.get_series(tvdb_id)  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 — transient fetch failure; don't veto on infra
        log.warning("show_tvdb_candidate_seasons_fetch_failed", tvdb_id=tvdb_id)
        return True
    available: set[int] = set()
    for season in series.get("seasons", []) or []:
        s_num = season.get("number", season.get("season_number", 0))
        if isinstance(s_num, int) and s_num > 0:
            available.add(s_num)
    return bool(available & wanted_seasons)


def match_tvshow_tvdb(
    tvdb_client: object,
    title: str,
    year: int | None,
    local_seasons: set[int] | None = None,
) -> MatchResult | None:
    """Match a local TV show against TVDB search results.

    TVDB is the primary provider for TV shows. Search results use
    snake_case fields and tvdb_id (string) as the identifier.

    When ``local_seasons`` is provided and the search returns multiple
    candidates above LOW_CONFIDENCE, candidates whose TVDB catalog does
    not overlap the local seasons are filtered out before picking the
    best score. This prevents a same-keyword spin-off (short catalog)
    from winning over the main show for a file tagged Sxx where xx is
    beyond the spin-off's range.

    Args:
        tvdb_client: TVDBClient instance.
        title: Show title from the local folder.
        year: First air date year (None if not detected).
        local_seasons: Season numbers observed in the folder's video files
            (e.g. {17} for a folder containing S17E08). When provided and
            more than one candidate survives the score filter, candidates
            whose TVDB seasons don't intersect this set are rejected.

    Returns:
        Best MatchResult with source="tvdb", or None if no results.
    """
    results = tvdb_client.search_series(title, year)  # type: ignore[attr-defined]
    if not results:
        log.info("show_no_tvdb_results", title=title, year=year)
        return None

    # First pass: score every candidate.
    scored: list[tuple[float, MatchResult]] = []
    for result in results:
        api_title = result.get("name", "")
        # TVDB search returns year as string in the "year" field
        year_str = result.get("year", "")
        api_year = int(year_str) if year_str and str(year_str).isdigit() else None

        score = score_match(title, year, api_title, api_year)

        # TVDB search uses tvdb_id (string), not id
        tvdb_id_str = result.get("tvdb_id", "")
        api_id = int(tvdb_id_str) if tvdb_id_str and str(tvdb_id_str).isdigit() else 0
        scored.append(
            (
                score,
                MatchResult(
                    api_id=api_id,
                    api_title=api_title,
                    api_year=api_year,
                    confidence=score,
                    source="tvdb",
                ),
            )
        )

    scored.sort(key=lambda x: x[0], reverse=True)

    # Content-aware filter: when local_seasons known and multiple viable
    # candidates, reject those whose catalog doesn't cover the wanted seasons.
    # Capped to the top 5 to avoid hammering TVDB on pathological searches.
    # A candidate with a very high fuzzy score (>= SEASON_VETO_BYPASS) is
    # kept regardless — e.g. a parallel-numbering spin-off like "Top Chef:
    # Le Concours Parallèle" whose own catalog is S01..S04 but whose releases
    # mirror the main show's S17 numbering. Fuzzy > content only at the very
    # top of the score curve, where the title itself is unambiguous.
    viable = [(s, m) for s, m in scored if s >= LOW_CONFIDENCE]
    if local_seasons and len(viable) >= 2:
        survivors: list[tuple[float, MatchResult]] = []
        for score, cand in viable[:5]:
            if score >= SEASON_VETO_BYPASS or _candidate_has_any_season(tvdb_client, cand.api_id, local_seasons):
                survivors.append((score, cand))
            else:
                log.info(
                    "show_tvdb_candidate_rejected_by_seasons",
                    tvdb_id=cand.api_id,
                    api_title=cand.api_title,
                    wanted_seasons=sorted(local_seasons),
                )
        if survivors:
            scored = survivors

    _, best_match = scored[0]
    if best_match is not None:
        log.info(
            "show_tvdb_match",
            title=title,
            api_title=best_match.api_title,
            api_year=best_match.api_year,
            confidence=round(best_match.confidence, 2),
        )
        # Warn early when the best candidate is below the acceptance threshold —
        # the caller will ultimately skip the item, but logging here captures
        # the candidates_count that the caller cannot see.
        if best_match.confidence < LOW_CONFIDENCE:
            log.warning(
                "scraper.match.below_threshold",
                title=title,
                year=year,
                candidates_count=len(results),
                top_score=round(best_match.confidence, 2),
                source="tvdb",
            )

    return best_match


def match_tvshow(
    tvdb_client: object,
    tmdb_client: object,
    title: str,
    year: int | None,
    local_seasons: set[int] | None = None,
) -> MatchResult | None:
    """Match a TV show using TVDB (primary) with TMDB fallback.

    Tries TVDB first. If TVDB returns no results or low confidence,
    falls back to TMDB search. Returns the best match from either.

    Args:
        tvdb_client: TVDBClient instance.
        tmdb_client: TMDBClient instance (fallback).
        title: Show title from the local folder.
        year: First air date year (None if not detected).
        local_seasons: Seasons observed in the folder (content-aware
            disambiguation — see ``match_tvshow_tvdb``).

    Returns:
        Best MatchResult (source="tvdb" or "tmdb"), or None.
    """
    # Try TVDB first (primary for TV shows)
    # Any TVDB error (circuit open, 5xx, timeout) falls through to TMDB.
    # TVDB is optional/advisory — TMDB is authoritative. Programming bugs in the TVDB adapter
    # are masked here, but the circuit breaker prevents cascading adapter failures from
    # impacting the pipeline; TMDB fallback ensures metadata is still populated.
    tvdb_match: MatchResult | None = None
    try:
        tvdb_match = match_tvshow_tvdb(tvdb_client, title, year, local_seasons=local_seasons)
        if tvdb_match and tvdb_match.confidence >= HIGH_CONFIDENCE:
            return tvdb_match
    except Exception as e:  # noqa: BLE001 — see block comment above; narrowing requires lazy imports for TVDBError/CircuitOpenError/requests and still masks adapter bugs
        log.warning("show_tvdb_fallback_tmdb", title=title, exc_info=True, error=str(e))

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
        log.info(
            "show_tmdb_fallback_match",
            title=title,
            api_title=tmdb_match.api_title,
            api_year=tmdb_match.api_year,
            confidence=round(tmdb_match.confidence, 2),
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
            log.warning("season_not_found_tvdb", season=season, title=match.api_title)
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
            log.warning("season_not_found_tmdb", season=season, title=match.api_title)
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
