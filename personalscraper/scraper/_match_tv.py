"""TV show title matching against TVDB (primary) and TMDB (fallback).

The TV side of the scraper's identification step. Strict project rule: TVDB is
the canonical source for TV shows; TMDB-for-TV is consulted **only** when TVDB
is silent, never as a confidence-delta override. Adds content-aware season
disambiguation (a same-keyword spin-off with a short catalog cannot win a file
tagged with a season beyond its range) and the subject-only query variant for
French documentary localisations.

Scoring primitives live in :mod:`personalscraper.scraper._match_score`; movie
matching lives in :mod:`personalscraper.scraper._match_movie`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from personalscraper.api.metadata._base import SearchResult
from personalscraper.logger import get_logger
from personalscraper.scraper._match_score import (
    AMBIGUITY_DELTA,
    LOW_CONFIDENCE,
    MatchResult,
    _best_scored_match,
    _filter_by_year_window,
    _merge_results,
    _result_to_match,
    _results_to_candidates,
    _score_result,
)
from personalscraper.scraper.decision_candidate import DecisionCandidate
from personalscraper.text_utils import media_processor

if TYPE_CHECKING:
    from personalscraper.api.metadata.tmdb import TMDBClient
    from personalscraper.api.metadata.tvdb import TVDBClient

log = get_logger("confidence")

# Above this fuzzy score, the content-aware season veto in
# match_tvshow_tvdb is bypassed: a 0.95+ title match is treated as
# unambiguous, even if the candidate's catalog does not cover the
# observed seasons (common for spin-offs whose releases mirror the
# main show's season numbering — e.g. S17 labels on a show with
# its own S01..S04 catalog).
SEASON_VETO_BYPASS = 0.95

_FRENCH_DOCUMENTARY_SUBJECT_RE = re.compile(
    r"^les?\s+secrets?\s+(?:du|de la|de l'|des|de)\s+(.+)$",
    re.IGNORECASE,
)


def _tv_fallback_title_variants(title: str) -> list[str]:
    """Return conservative alternate TMDB queries for TV documentary titles."""
    variants = [title]
    match = _FRENCH_DOCUMENTARY_SUBJECT_RE.match(title.strip())
    if match:
        subject = match.group(1).strip()
        if subject and media_processor(subject) != media_processor(title):
            variants.append(subject)
    return variants


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


def match_tvshow_tvdb_detailed(
    tvdb_client: object,
    title: str,
    year: int | None,
    local_seasons: set[int] | None = None,
) -> tuple[MatchResult | None, list[DecisionCandidate]]:
    """Detailed variant of :func:`match_tvshow_tvdb` returning scored candidates.

    Same search, scoring, and content-aware season disambiguation as
    :func:`match_tvshow_tvdb`, but additionally returns the top-5 scored
    candidates as :class:`DecisionCandidate` instances.  Also emits the
    ``tvshow_match_ambiguous`` warning when the top two candidates are
    within ``AMBIGUITY_DELTA`` — the same ambiguity detection movies have
    via ``movie_match_ambiguous``.

    Args:
        tvdb_client: TVDBClient instance.
        title: Show title from the local folder.
        year: First air date year (None if not detected).
        local_seasons: Season numbers observed in the folder's video files
            (e.g. {17} for a folder containing S17E08). When provided and
            more than one candidate survives the score filter, candidates
            whose TVDB seasons don't intersect this set are rejected.

    Returns:
        Tuple of (best :class:`MatchResult` with source="tvdb" or None,
        top-5 :class:`DecisionCandidate` list).
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
        return None, []

    # Build lookup for poster/overview enrichment (no extra API calls).
    _sr_by_id: dict[int, SearchResult] = {}
    for r in results:
        pid = int(r.provider_id) if r.provider_id.isdigit() else 0
        if pid and pid not in _sr_by_id:
            _sr_by_id[pid] = r

    # First pass: score every candidate.
    scored: list[tuple[float, MatchResult]] = []
    for result in results:
        score = _score_result(title, year, result)
        scored.append((score, _result_to_match(result, score, "tvdb")))

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

    # Build candidates from post-filter scored list.
    candidates: list[DecisionCandidate] = []
    for score, match in scored[:5]:
        sr = _sr_by_id.get(match.api_id)
        candidates.append(
            DecisionCandidate(
                provider="tvdb",
                provider_id=match.api_id,
                title=match.api_title,
                year=match.api_year,
                score=score,
                poster_url=sr.poster_url or None if sr else None,
                overview=sr.overview or None if sr else None,
            )
        )

    # TV ambiguity delta — same detection movies have (movie_match_ambiguous).
    if len(candidates) > 1:
        if candidates[1].score >= LOW_CONFIDENCE and candidates[0].score - candidates[1].score < AMBIGUITY_DELTA:
            log.warning(
                "tvshow_match_ambiguous",
                title=title,
                top_score=round(candidates[0].score, 2),
                runner_up=round(candidates[1].score, 2),
                candidates_count=len(candidates),
            )

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

    return best_match, candidates


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
    return match_tvshow_tvdb_detailed(tvdb_client, title, year, local_seasons=local_seasons)[0]


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

    Unknown provider names fall through to ``None`` rather than raising, so a
    chain that mixes future providers does not break the matching loop. The
    live TV scrape uses the candidate-returning
    :func:`personalscraper.scraper.tv_service_episodes.match_tvshow_single_detailed`
    (iterated via ``run_chain``); this match-only helper survives for the
    public façade + snapshot tests.

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
        best_match = _best_scored_match(tmdb_results, year, "tmdb")
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


def match_tvshow_detailed(
    tvdb_client: object,
    tmdb_client: object,
    title: str,
    year: int | None,
    local_seasons: set[int] | None = None,
) -> tuple[MatchResult | None, list[DecisionCandidate]]:
    """Detailed variant of :func:`match_tvshow` returning scored candidates.

    Same provider chain (TVDB first, TMDB fallback) as :func:`match_tvshow`,
    but additionally returns the top-5 scored candidates as
    :class:`DecisionCandidate` instances for the scrape-arbiter decision
    queue.

    Strict invariant (project rule): TVDB is the canonical source for TV
    shows. TMDB-for-TV is permitted **only** when TVDB has no match for
    the show — never as a "TVDB returned a low-confidence match, maybe
    TMDB scores higher" override.

    Args:
        tvdb_client: TVDBClient instance.
        tmdb_client: TMDBClient instance (used only when TVDB is silent).
        title: Show title from the local folder.
        year: First air date year (None if not detected).
        local_seasons: Seasons observed in the folder (content-aware
            disambiguation — see ``match_tvshow_tvdb``).

    Returns:
        Tuple of (best :class:`MatchResult` or None, top-5
        :class:`DecisionCandidate` list). TVDB candidates when TVDB
        returned any match; otherwise TMDB candidates; otherwise empty.
    """
    # Query TVDB first. Any TVDB error (circuit open, 5xx, timeout) is
    # treated as "TVDB is silent" and lets the TMDB fallback run.
    tvdb_match: MatchResult | None = None
    tvdb_candidates: list[DecisionCandidate] = []
    try:
        tvdb_match, tvdb_candidates = match_tvshow_tvdb_detailed(tvdb_client, title, year, local_seasons=local_seasons)
    except Exception as e:  # noqa: BLE001 — TVDB adapter raises a mix of ApiError, CircuitOpenError, and requests exceptions; narrowing requires lazy imports
        log.warning("show_tvdb_fallback_tmdb", title=title, exc_info=True, error=str(e))

    if tvdb_match is not None:
        # TVDB found something — return it. We never let TMDB override
        # a TVDB match for TV shows, regardless of confidence delta.
        return tvdb_match, tvdb_candidates

    # TVDB is silent → consult TMDB as the documented fallback.
    return _match_tvshow_tmdb_detailed(tmdb_client, title, year)


def _match_tvshow_tmdb_detailed(
    tmdb_client: object,
    title: str,
    year: int | None,
) -> tuple[MatchResult | None, list[DecisionCandidate]]:
    """Match a TV show against TMDB, returning scored candidates.

    Shared TMDB-for-TV path: :func:`match_tvshow_detailed` uses it as the
    TVDB-silent fallback; :func:`personalscraper.scraper.tv_service_episodes.match_tvshow_single_detailed`
    uses it for the TMDB chain step. Also tries a narrow subject-only query
    (via :func:`_tv_tmdb_candidates`) for French documentary localisations.

    Args:
        tmdb_client: TMDBClient instance.
        title: Show title from the local folder.
        year: First air date year (None if not detected).

    Returns:
        Tuple of (best :class:`MatchResult` with source="tmdb" or None,
        top-5 :class:`DecisionCandidate` list).
    """
    tmdb_results = _tv_tmdb_candidates(tmdb_client.search_tv, title, year)  # type: ignore[attr-defined]
    tmdb_match = _best_scored_match(tmdb_results, year, "tmdb")
    tmdb_candidates: list[DecisionCandidate] = []

    if tmdb_match:
        log.info(
            "show_tmdb_fallback_match",
            title=title,
            api_title=tmdb_match.api_title,
            api_year=tmdb_match.api_year,
            confidence=round(tmdb_match.confidence, 2),
        )
        # Build candidates from TMDB fallback results.
        sr_list = [sr for _, sr in tmdb_results]
        tmdb_candidates = _results_to_candidates(sr_list, title, year)

    return tmdb_match, tmdb_candidates


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
    return match_tvshow_detailed(tvdb_client, tmdb_client, title, year, local_seasons=local_seasons)[0]


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
