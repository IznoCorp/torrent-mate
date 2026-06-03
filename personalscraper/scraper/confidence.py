"""Confidence scoring and matching for media title identification.

Combines rapidfuzz WRatio (title similarity) with year validation
to score API results against local media files. Used by both movie
matching (TMDB) and TV show matching (TVDB/TMDB fallback).

The media_processor from text_utils handles French accent stripping
via NFD decomposition — critical because rapidfuzz default_process
does NOT strip accents.

See docs/rapidfuzz-reference.md for scorer details.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer
from rapidfuzz import fuzz

from personalscraper.api.metadata._base import SearchResult
from personalscraper.logger import get_logger
from personalscraper.text_utils import media_processor

if TYPE_CHECKING:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient

log = get_logger("confidence")

# Confidence thresholds
HIGH_CONFIDENCE = 0.8  # Auto-accept in automatic mode
LOW_CONFIDENCE = 0.5  # Skip in automatic mode (no match)
# Between LOW and HIGH: caller decides (skip in auto, prompt in interactive)

# When the runner-up candidate scores within this delta of the winner (and is
# itself >= LOW_CONFIDENCE), the auto-accepted match is ambiguous. Surfaced as a
# warning for operator visibility; does NOT change acceptance behaviour.
AMBIGUITY_DELTA = 0.05

# Above this fuzzy score, the content-aware season veto in
# match_tvshow_tvdb is bypassed: a 0.95+ title match is treated as
# unambiguous, even if the candidate's catalog does not cover the
# observed seasons (common for spin-offs whose releases mirror the
# main show's season numbering — e.g. S17 labels on a show with
# its own S01..S04 catalog).
SEASON_VETO_BYPASS = 0.95

# Maximum year difference for fallback matching when the initial search
# with year filter returns zero results. Remakes are typically 10-20+
# years apart, so a 5-year window is safe against false positives.
YEAR_FALLBACK_WINDOW = 5

_FRENCH_DOCUMENTARY_SUBJECT_RE = re.compile(
    r"^les?\s+secrets?\s+(?:du|de la|de l'|des|de)\s+(.+)$",
    re.IGNORECASE,
)


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


def _tv_fallback_title_variants(title: str) -> list[str]:
    """Return conservative alternate TMDB queries for TV documentary titles."""
    variants = [title]
    match = _FRENCH_DOCUMENTARY_SUBJECT_RE.match(title.strip())
    if match:
        subject = match.group(1).strip()
        if subject and media_processor(subject) != media_processor(title):
            variants.append(subject)
    return variants


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


# Tokens that carry no disambiguating weight when deciding whether one title is
# a strict content-expansion of another (articles / prepositions / conjunctions,
# EN + FR). Without dropping these, "The Matrix" vs "Matrix" would wrongly count
# as a superstring expansion.
_TITLE_NOISE_TOKENS = frozenset(
    {
        "the",
        "a",
        "an",
        "le",
        "la",
        "les",
        "l",
        "un",
        "une",
        "de",
        "des",
        "du",
        "of",
        "and",
        "et",
    }
)


def _significant_tokens(text: str) -> frozenset[str]:
    """Return the disambiguating tokens of a title.

    Normalises via media_processor (lowercase + accent strip) and drops
    articles/prepositions, leaving only content words.

    Args:
        text: Title to tokenise.

    Returns:
        Frozenset of significant (content) tokens.
    """
    return frozenset(tok for tok in media_processor(text).split() if tok and tok not in _TITLE_NOISE_TOKENS)


def _superstring_penalty(query: str, candidate: str) -> float:
    """Penalty (<= 0) when ``candidate`` is a strict content-expansion of ``query``.

    A candidate whose content words are a PROPER SUPERSET of the query's — a
    making-of ("The Making of X"), a sequel ("X 2"), an "X: Subtitle", or a
    prefixed work ("The Crow: <query>") — matches the query only by containment
    and should not outrank the exact title. The penalty scales with the number
    of extra content words and is capped, so a single-word subtitle is nudged
    while a far-expanded title is pushed down. It stays modest so a lone correct
    candidate is never dropped below the acceptance threshold by this alone.

    Returns 0.0 when the candidate is not a strict expansion (equal content, or
    disjoint/partial), so exact and clean localized matches are never penalised.

    Args:
        query: Local title being matched.
        candidate: Candidate API title.

    Returns:
        A penalty in [-0.20, 0.0].
    """
    q = _significant_tokens(query)
    c = _significant_tokens(candidate)
    if not q or q == c or not (q < c):
        return 0.0
    extra = len(c - q)
    return max(-0.20, -0.08 * extra)


def _score_result(
    local_title: str,
    local_year: int | None,
    result: SearchResult,
) -> float:
    """Score a SearchResult against a local title/year (matching-grade score).

    Refines the base WRatio+year :func:`score_match` with two signals, taking
    the best (score + superstring penalty) across the localized title and the
    original-language title:

    - **original_title**: an English-named folder ("The Frighteners") matches a
      localized TMDB/TVDB title ("Fantômes contre fantômes") poorly but the
      original_title exactly — so a localized result is not unfairly beaten.
    - **aliases**: a folder named with a translated/alternate title ("Murder
      Mindfully") matches a foreign-primary candidate ("Achtsam Morden") via one
      of its alias/translation titles (DEV #2). Best-of scoring only RAISES the
      score, so the season-veto and ambiguity guards still protect the ranking.
    - **superstring penalty**: a content-expansion candidate (sequel, making-of,
      "X: Subtitle") is demoted so it does not outrank the exact title.

    Shared by movie and TV ranking so behaviour is uniform across providers.

    Args:
        local_title: Title extracted from the local folder.
        local_year: Year extracted from the local folder (None if absent).
        result: Candidate API search result.

    Returns:
        Confidence score in [0.0, 1.0].
    """
    titles = [result.title]
    if result.original_title and result.original_title != result.title:
        titles.append(result.original_title)
    titles.extend(alias for alias in result.aliases if alias and alias not in titles)
    best = -1.0
    for api_title in titles:
        scored = score_match(local_title, local_year, api_title, result.year) + _superstring_penalty(
            local_title, api_title
        )
        best = max(best, scored)
    return max(0.0, best)


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


def _filter_by_year_window(
    results: list[SearchResult],
    year: int,
    window: int = YEAR_FALLBACK_WINDOW,
) -> list[SearchResult]:
    """Filter search results to those within a year window of the expected year.

    Args:
        results: Raw TMDB search results.
        year: Expected release year.
        window: Maximum allowed year difference.

    Returns:
        Filtered results where abs(result.year - year) <= window.
    """
    return [r for r in results if r.year is not None and abs(r.year - year) <= window]


def _merge_results(
    primary: list[SearchResult],
    extra: list[SearchResult],
) -> list[SearchResult]:
    """Union two TMDB result lists, de-duplicating by provider_id.

    Primary results keep their order and precedence; extra results not already
    present (matched by provider_id) are appended. Used to merge year-filtered
    results with no-year window candidates, so a film excluded by TMDB's
    region-aware ``year=`` filter is still considered during ranking.

    Args:
        primary: First-priority results (e.g. year-filtered search).
        extra: Additional candidates to merge in (e.g. no-year window).

    Returns:
        Merged list with duplicates removed and primary order preserved.
    """
    seen = {r.provider_id for r in primary}
    return primary + [r for r in extra if r.provider_id not in seen]


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
        candidates = _search_with_language(tmdb_client, title, None, en)
        results = _filter_by_year_window(candidates, year)
        if results:
            fallback_event = "movie_match_year_language_fallback"
            fallback_meta = {"original_year": year, "language": en}

    if not results:
        log.info("movie_no_tmdb_results", title=title, year=year)
        return None

    best_match: MatchResult | None = None
    best_score = -1.0

    for result in results:
        api_title = result.title
        api_year = result.year
        api_id = int(result.provider_id) if result.provider_id.isdigit() else 0

        score = _score_result(title, year, result)

        if score > best_score:
            best_score = score
            best_match = MatchResult(
                api_id=api_id,
                api_title=api_title,
                api_year=api_year,
                confidence=score,
                source="tmdb",
            )

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
    # api-unify: get_series returns a typed MediaDetails whose ``seasons``
    # field is list[SeasonInfo]. The phase-27 TVDB parser populates each
    # entry from the raw extended response.
    available = {s.season_number for s in series.seasons if s.season_number > 0}
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
    # Year-window merge: TVDB's year filter (like TMDB's) can exclude the correct
    # show when its first-air year differs by a year or two from a similarly-titled
    # show's. When a year is present, also fetch the no-year candidates within the
    # fallback window and merge them so the right show survives to scoring. Same
    # bug class as the movie path (fixed there first); TVDB previously had no
    # no-year fallback at all, so this also closes that gap.
    if year is not None:
        windowed = _filter_by_year_window(
            tvdb_client.search_series(title, None),  # type: ignore[attr-defined]
            year,
        )
        results = _merge_results(results, windowed)
    if not results:
        log.info("show_no_tvdb_results", title=title, year=year)
        return None

    # First pass: score every candidate.
    scored: list[tuple[float, MatchResult]] = []
    for result in results:
        # api-unify: typed SearchResult — title/year/provider_id replace the
        # old TVDB-specific name/year/tvdb_id fields.
        api_title = result.title
        api_year = result.year
        api_id = int(result.provider_id) if result.provider_id.isdigit() else 0

        score = _score_result(title, year, result)

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


def _tv_tmdb_candidates(
    search_tv: Callable[[str, int | None], list[SearchResult]],
    title: str,
    year: int | None,
) -> list[tuple[str, SearchResult]]:
    """Collect ``(query_title, SearchResult)`` TMDB-TV candidates over title variants.

    Searches each conservative title variant (see
    :func:`_tv_fallback_title_variants`) with the year filter, then — when a year
    is present — merges the no-year candidates within the fallback window,
    de-duplicated by ``provider_id``. The no-year merge closes the same
    year-filter exclusion gap fixed for movies: TMDB's ``first_air_date_year``
    filter can hide the correct show when its first-air year differs by a year
    or two from a similarly-titled show's.

    Args:
        search_tv: The provider's ``search_tv(title, year)`` bound method.
        title: Local show title.
        year: First-air year (None if absent).

    Returns:
        ``(query_title, result)`` pairs, de-duplicated by ``provider_id``.
    """
    out: list[tuple[str, SearchResult]] = []
    seen: set[str] = set()

    def _add(query_title: str, items: list[SearchResult]) -> None:
        for r in items:
            if r.provider_id not in seen:
                seen.add(r.provider_id)
                out.append((query_title, r))

    for query_title in _tv_fallback_title_variants(title):
        _add(query_title, search_tv(query_title, year))
    if year is not None:
        for query_title in _tv_fallback_title_variants(title):
            _add(query_title, _filter_by_year_window(search_tv(query_title, None), year))
    return out


def match_tvshow_single(
    provider: object,
    title: str,
    year: int | None,
    local_seasons: set[int] | None = None,
) -> MatchResult | None:
    """Match a TV show against a SINGLE provider (chain-step helper).

    Per-provider counterpart to :func:`match_movie`. Dispatches by
    ``provider.provider_name`` to the appropriate search routine:

    - ``tvdb`` → :func:`match_tvshow_tvdb` (TVDB search + content-aware
      season disambiguation when ``local_seasons`` is supplied).
    - ``tmdb`` → TMDB ``search_tv`` over the conservative title variants
      returned by :func:`_tv_fallback_title_variants` (the historical
      "narrow subject-only query" path for French documentary
      localisations).

    Unknown provider names fall through to ``None`` rather than raising,
    so a chain that mixes future providers does not break the matching
    loop. The caller (``TvServiceMixin._match_tvshow_candidates``) is
    responsible for the chain iteration, fallback events, and the
    cross-provider rule that TVDB takes precedence over TMDB — that
    invariant is now expressed via the provider chain order in
    ``config.metadata.priorities`` rather than hardcoded inside this
    helper.

    Args:
        provider: A chain-eligible TV provider (currently TVDB or TMDB)
            with the legacy method names (``search_series`` for TVDB,
            ``search_tv`` for TMDB).
        title: Show title from the local folder.
        year: First air date year (None if not detected).
        local_seasons: Season numbers observed in the folder's video
            files; forwarded to :func:`match_tvshow_tvdb`.

    Returns:
        Best :class:`MatchResult` for that provider, or ``None`` when the
        provider returned no candidates.
    """
    name = getattr(provider, "provider_name", "")
    if name == "tvdb":
        return match_tvshow_tvdb(provider, title, year, local_seasons=local_seasons)
    if name == "tmdb":
        # TMDB search path lifted from the legacy ``match_tvshow`` TMDB
        # fallback branch — keeps the subject-only query variant for
        # French documentary localisations.
        tmdb_results = _tv_tmdb_candidates(provider.search_tv, title, year)  # type: ignore[attr-defined]
        if not tmdb_results:
            log.info("show_no_tmdb_results", title=title, year=year)
            return None
        best_match: MatchResult | None = None
        best_score = -1.0
        for query_title, result in tmdb_results:
            api_title = result.title
            api_year = result.year
            api_id = int(result.provider_id) if result.provider_id.isdigit() else 0
            score = _score_result(query_title, year, result)
            if score > best_score:
                best_score = score
                best_match = MatchResult(
                    api_id=api_id,
                    api_title=api_title,
                    api_year=api_year,
                    confidence=score,
                    source="tmdb",
                )
        if best_match is not None:
            log.info(
                "show_tmdb_match",
                title=title,
                api_title=best_match.api_title,
                api_year=best_match.api_year,
                confidence=round(best_match.confidence, 2),
            )
        return best_match
    # Unknown provider — refuse to guess. Future TV providers must
    # extend this dispatch table explicitly.
    log.debug("tvshow_match_unknown_provider", provider=name)
    return None


def match_tvshow(
    tvdb_client: object,
    tmdb_client: object,
    title: str,
    year: int | None,
    local_seasons: set[int] | None = None,
) -> MatchResult | None:
    """Match a TV show using TVDB. TMDB is consulted ONLY when TVDB is silent.

    Strict invariant (project rule): TVDB is the canonical source for TV
    shows. TMDB-for-TV is permitted **only** when TVDB has no match for
    the show — never as a "TVDB returned a low-confidence match, maybe
    TMDB scores higher" override. Allowing TMDB to override TVDB even
    occasionally is what produced the historical year mismatches (e.g.
    South Park indexed as 1992 instead of 1997) that this guardrail now
    forbids.

    Behaviour:
    1. Query TVDB. If TVDB returns *any* match (regardless of confidence),
       return it. The caller is responsible for the confidence threshold;
       a low-confidence TVDB match is still a TVDB match, and we'd rather
       skip than silently retag the show against TMDB.
    2. If TVDB returns ``None`` (no candidates) or raises, fall through to
       TMDB. This keeps shows that are present on TMDB but missing from
       TVDB scrapable.

    Args:
        tvdb_client: TVDBClient instance.
        tmdb_client: TMDBClient instance (used only when TVDB is silent).
        title: Show title from the local folder.
        year: First air date year (None if not detected).
        local_seasons: Seasons observed in the folder (content-aware
            disambiguation — see ``match_tvshow_tvdb``).

    Returns:
        TVDB MatchResult when TVDB found anything; otherwise the best TMDB
        MatchResult; otherwise ``None``.
    """
    # Query TVDB first. Any TVDB error (circuit open, 5xx, timeout) is
    # treated as "TVDB is silent" and lets the TMDB fallback run.
    tvdb_match: MatchResult | None = None
    try:
        tvdb_match = match_tvshow_tvdb(tvdb_client, title, year, local_seasons=local_seasons)
    except Exception as e:  # noqa: BLE001 — TVDB adapter raises a mix of ApiError, CircuitOpenError, and requests exceptions; narrowing requires lazy imports
        log.warning("show_tvdb_fallback_tmdb", title=title, exc_info=True, error=str(e))

    if tvdb_match is not None:
        # TVDB found something — return it. We never let TMDB override
        # a TVDB match for TV shows, regardless of confidence delta.
        return tvdb_match

    # TVDB is silent → consult TMDB as the documented fallback. Some
    # French documentary releases are localised as "Les secrets de
    # <subject>" while TMDB indexes the original title under the subject
    # name, so try a narrow subject-only query as well.
    tmdb_results = _tv_tmdb_candidates(tmdb_client.search_tv, title, year)  # type: ignore[attr-defined]
    tmdb_match: MatchResult | None = None
    best_score = -1.0

    for query_title, result in tmdb_results:
        # api-unify: SearchResult.title is unified across movie ("title") and
        # tv ("name") TMDB endpoints; year is pre-extracted.
        api_title = result.title
        api_year = result.year
        api_id = int(result.provider_id) if result.provider_id.isdigit() else 0

        score = _score_result(query_title, year, result)
        if score > best_score:
            best_score = score
            tmdb_match = MatchResult(
                api_id=api_id,
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

    return tmdb_match


def get_episode_titles(
    match: MatchResult,
    season: int,
    tvdb_client: TVDBClient,
    tmdb_client: TMDBClient,
    lang: str = "fra",
) -> dict[int, str]:
    """Get episode titles for a season from the matched provider.

    Both TMDB and TVDB now return typed ``SeasonDetails`` (via ``get_tv_season``
    / ``get_series_episodes``). Episode titles are taken directly from the API
    response — TVDB v4 has no per-episode translation endpoint.

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
        season_details = tvdb_client.get_series_episodes(match.api_id, season)
        if not season_details or not season_details.episodes:
            log.warning("season_not_found_tvdb", season=season, title=match.api_title)
            return titles

        for ep in season_details.episodes:
            ep_num = ep.episode_number
            titles[ep_num] = ep.title or f"Episode {ep_num}"

    elif match.source == "tmdb":
        season_details = tmdb_client.get_tv_season(match.api_id, season)
        if not season_details or not season_details.episodes:
            log.warning("season_not_found_tmdb", season=season, title=match.api_title)
            return titles

        for ep in season_details.episodes:
            ep_num = ep.episode_number
            titles[ep_num] = ep.title or f"Episode {ep_num}"

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
