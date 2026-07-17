"""Shared scoring kernel for media title identification.

Confidence thresholds, the :class:`MatchResult` container, the rapidfuzz-based
scorers, and the candidate-building/best-of helpers shared by movie matching
(:mod:`personalscraper.scraper._match_movie`) and TV matching
(:mod:`personalscraper.scraper._match_tv`).

Combines rapidfuzz WRatio (title similarity) with year validation to score API
results against local media files. The media_processor from text_utils handles
French accent stripping via NFD decomposition — critical because rapidfuzz
default_process does NOT strip accents.

See docs/rapidfuzz-reference.md for scorer details.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from rapidfuzz import fuzz

from personalscraper.api.metadata._base import SearchResult
from personalscraper.scraper.decision_candidate import DecisionCandidate
from personalscraper.text_utils import media_processor

# Confidence thresholds
HIGH_CONFIDENCE = 0.8  # Auto-accept in automatic mode
LOW_CONFIDENCE = 0.5  # Skip in automatic mode (no match)
# Between LOW and HIGH: caller decides (skip in auto, prompt in interactive)

# When the runner-up candidate scores within this delta of the winner (and is
# itself >= LOW_CONFIDENCE), the auto-accepted match is ambiguous. Surfaced as a
# warning for operator visibility; does NOT change acceptance behaviour.
AMBIGUITY_DELTA = 0.05

# Maximum year difference for fallback matching when the initial search
# with year filter returns zero results. Remakes are typically 10-20+
# years apart, so a 5-year window is safe against false positives.
YEAR_FALLBACK_WINDOW = 5


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


_DEFAULT_MIN_LENGTH_RATIO: float = 0.40  # directional guard: query-too-short direction only;
# lower than FuzzyMatchConfig.min_length_ratio (0.67, bidirectional) because subject-query
# variants like "Prince Andrew" vs "Andrew: The Problem Prince" (ratio 0.50) are legit matches.


def _length_ratio_guard(query: str, api_title: str, min_ratio: float = _DEFAULT_MIN_LENGTH_RATIO) -> bool:
    """Return True when the query is too short relative to ``api_title``.

    Implements a DIRECTIONAL guard: only fires when the query title is much
    shorter than the API candidate title (the query-too-short direction).
    It must NOT fire when the local title is longer than the API title —
    that direction covers legit subtitle expansions like
    ``"The Hack sur ecoute"`` → ``"The Hack"`` or
    ``"Top Chef France"`` → ``"Top Chef"``.

    Uses ``media_processor`` (accent-stripping + lowercase) to normalise
    both strings before length comparison, matching the pre-processing done
    inside ``score_match``.

    Args:
        query: Local title extracted from the folder name.
        api_title: Candidate title from the API result (title, original_title, or alias).
        min_ratio: Minimum ``len(query) / len(api_title)`` ratio below which
            the candidate is rejected. Default 0.40 (lower than FuzzyMatchConfig's
            bidirectional 0.67 because subject-query variants like "Prince Andrew"
            vs "Andrew: The Problem Prince" sit at 0.50 and are legit matches).

    Returns:
        True if the guard fires (candidate should be rejected), False otherwise.
    """
    norm_query = media_processor(query)
    norm_api = media_processor(api_title)
    if not norm_query or not norm_api:
        # Empty after processing — cannot judge; don't reject
        return False
    # Directional: only reject when query is shorter than api_title
    if len(norm_query) >= len(norm_api):
        return False
    ratio = len(norm_query) / len(norm_api)
    return ratio < min_ratio


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
      of its alias/translation titles (DEV #2). Best-of only RAISES a candidate's
      score (never lowers it), and the per-alias superstring penalty still
      applies, so an alias cannot make a wrong candidate outrank an exact-title
      match of the same year; for TV the season-veto is the additional guard when
      the folder has parseable seasons. (Note: ``match_tvshow_tvdb`` has no
      runner-up "ambiguity" warning — that exists only on the movie path.)
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
        # Directional length-ratio guard: skip this candidate title when the
        # query is much shorter than api_title (e.g. "S03" vs "Glina. Nowy
        # rozdział", ratio 0.150).  The guard is NOT applied when the local
        # title is longer — that direction is legit (subtitle expansions).
        if _length_ratio_guard(local_title, api_title):
            continue
        scored = score_match(local_title, local_year, api_title, result.year) + _superstring_penalty(
            local_title, api_title
        )
        best = max(best, scored)
    return max(0.0, best)


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


def _results_to_candidates(
    results: list[SearchResult],
    local_title: str,
    local_year: int | None,
    *,
    limit: int = 5,
) -> list[DecisionCandidate]:
    """Score search results and return top-N candidates sorted by score desc.

    Deduplicates by ``provider_id`` (first occurrence wins), scores each
    result via :func:`_score_result`, and returns the top ``limit``
    candidates sorted by score descending.  Used by the detailed match
    variants to build the candidate list for the scrape-arbiter decision
    queue without additional API calls.

    Args:
        results: Search results from the provider.
        local_title: Title extracted from the local folder.
        local_year: Year extracted from the local folder (None if absent).
        limit: Maximum number of candidates to return (default 5).

    Returns:
        Top-N candidates sorted by score descending.
    """
    scored: list[tuple[float, DecisionCandidate]] = []
    seen_ids: set[int] = set()

    for r in results:
        pid = int(r.provider_id) if r.provider_id.isdigit() else 0
        if pid in seen_ids or pid == 0:
            continue
        seen_ids.add(pid)

        score = _score_result(local_title, local_year, r)
        candidate = DecisionCandidate(
            provider=r.provider,  # type: ignore[arg-type]  # "tmdb"|"tvdb" in practice
            provider_id=pid,
            title=r.title,
            year=r.year,
            score=score,
            poster_url=r.poster_url or None,
            overview=r.overview or None,
        )
        scored.append((score, candidate))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]


def _result_to_match(result: SearchResult, score: float, source: str) -> MatchResult:
    """Build a :class:`MatchResult` from a scored :class:`SearchResult`.

    Collapses the per-candidate field extraction (``api_id``/``api_title``/
    ``api_year``) + ``MatchResult`` construction that the four best-of ranking
    loops (movie search, TVDB search, TMDB-TV single, TMDB-TV fallback) each
    repeated verbatim. The ``provider_id`` → ``api_id`` coercion mirrors the
    historical ``int(...) if ...isdigit() else 0`` guard for non-numeric ids.

    Args:
        result: Candidate API search result to wrap.
        score: Confidence score already computed for ``result``.
        source: Provider label recorded on the match ("tmdb" or "tvdb").

    Returns:
        A :class:`MatchResult` carrying ``result``'s identity and ``score``.
    """
    api_id = int(result.provider_id) if result.provider_id.isdigit() else 0
    return MatchResult(
        api_id=api_id,
        api_title=result.title,
        api_year=result.year,
        confidence=score,
        source=source,
    )


def _best_scored_match(
    pairs: Iterable[tuple[str, SearchResult]],
    year: int | None,
    source: str,
) -> MatchResult | None:
    """Return the highest-scoring :class:`MatchResult` over query/result pairs.

    Collapses the best-of ranking loop that appeared in the movie search
    (fixed query title) and — verbatim, twice — in the TMDB-for-TV path
    (``match_tvshow_single`` TMDB branch and ``_match_tvshow_tmdb_detailed``,
    which iterate the per-variant ``(query_title, result)`` pairs from
    :func:`personalscraper.scraper._match_tv._tv_tmdb_candidates`). Each
    candidate is scored with its own ``query_title`` so a subject-only
    documentary variant scores against the query that produced it.

    Args:
        pairs: ``(query_title, result)`` candidates to rank. For a
            single-query search, pass ``((title, r) for r in results)``.
        year: Local year forwarded to :func:`_score_result` (None if absent).
        source: Provider label recorded on the winning match.

    Returns:
        The best-scoring :class:`MatchResult`, or ``None`` when ``pairs`` is
        empty.
    """
    best_match: MatchResult | None = None
    best_score = -1.0
    for query_title, result in pairs:
        score = _score_result(query_title, year, result)
        if score > best_score:
            best_score = score
            best_match = _result_to_match(result, score, source)
    return best_match
