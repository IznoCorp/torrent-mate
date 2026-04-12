"""Shared text processing utilities for media title matching.

Provides media_processor() — a custom rapidfuzz processor that normalizes
media titles for accent-insensitive French matching. Used by V2 (matcher.py),
V3 (confidence.py), and V5 (media_index.py).

Also provides fuzzy_match_score() — a guarded fuzzy matching function with
anti-false-positive protections (year constraint, length ratio, adaptive
threshold). Used by V5 (media_index.py) and V2 (matcher.py).

See docs/rapidfuzz-reference.md for rationale on custom processing.
"""

import unicodedata

from rapidfuzz import utils


def media_processor(s: str) -> str:
    """Normalize a media title for fuzzy matching.

    Pipeline: rapidfuzz default_process (lowercase + strip non-alphanum)
    then NFD decomposition to strip accents/diacritical marks.

    This is needed because rapidfuzz's default_process does NOT strip
    accents — "Amélie" vs "Amelie" would score poorly without this.

    Args:
        s: Raw media title string.

    Returns:
        Normalized string (lowercase, no punctuation, no accents).
    """
    s = utils.default_process(s)
    # NFD decomposition splits accented chars (é → e + combining accent)
    # then we strip the combining marks (category 'Mn')
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def fuzzy_match_score(
    query: str,
    candidate: str,
    query_year: int | None = None,
    candidate_year: int | None = None,
) -> float | None:
    """Score a fuzzy match with anti-false-positive guards.

    Applies three guards before returning a score:
    1. Year: if both years are present, abs(diff) must be <= 1
    2. Length ratio: len(shorter)/len(longer) must be >= 0.67
    3. Adaptive threshold: processed len <= 10 requires 95%, else 90%

    Uses WRatio with media_processor for accent-insensitive matching.

    Args:
        query: Search term (raw — processed internally).
        candidate: Candidate to compare (raw — processed internally).
        query_year: Year extracted from query (optional).
        candidate_year: Year extracted from candidate (optional).

    Returns:
        WRatio score (0-100) if all guards pass, None if rejected.
    """
    from rapidfuzz import fuzz

    # Guard 1 — Year constraint: ±1 year tolerance
    if query_year is not None and candidate_year is not None:
        if abs(query_year - candidate_year) > 1:
            return None

    # Process both strings for length and score comparison
    processed_query = media_processor(query)
    processed_candidate = media_processor(candidate)

    # Guard 2 — Length ratio: reject if strings are too different in length
    if not processed_query or not processed_candidate:
        return None
    shorter = min(len(processed_query), len(processed_candidate))
    longer = max(len(processed_query), len(processed_candidate))
    if shorter / longer < 0.67:
        return None

    # Guard 3 — Adaptive threshold: short titles need higher score
    threshold = 95.0 if len(processed_query) <= 10 else 90.0

    score = fuzz.WRatio(query, candidate, processor=media_processor)
    if score >= threshold:
        return score
    return None
