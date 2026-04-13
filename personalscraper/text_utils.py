"""Shared text processing utilities for media title matching.

Provides media_processor() — a custom rapidfuzz processor that normalizes
media titles for accent-insensitive French matching. Used by V2 (matcher.py),
V3 (confidence.py), and V5 (media_index.py).

Also provides fuzzy_match_score() — a guarded fuzzy matching function with
anti-false-positive protections (year constraint, length ratio, adaptive
threshold). Used by V5 (media_index.py) and V2 (matcher.py).

See docs/rapidfuzz-reference.md for rationale on custom processing.
"""

import re
import unicodedata

from rapidfuzz import utils

# Year suffix pattern for length ratio normalization
_YEAR_SUFFIX = re.compile(r"\s*\(\d{4}\)\s*$")

# Characters illegal on NTFS/Windows; colon also displays as / in macOS Finder
_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*]')
_MULTI_SPACE = re.compile(r" {2,}")


def sanitize_filename(name: str) -> str:
    """Remove characters that are illegal or problematic in filenames.

    Strips characters forbidden on NTFS/Windows (<>:"/\\|?*) and that
    display incorrectly on macOS Finder (: shows as /). Also normalizes
    non-breaking spaces (U+00A0) to regular spaces and collapses any
    resulting double spaces.

    Args:
        name: Raw filename or directory name.

    Returns:
        Sanitized name safe for cross-platform use.
    """
    # Replace non-breaking space with regular space
    name = name.replace("\u00a0", " ")
    # Remove illegal characters and collapse resulting double spaces
    name = _FILENAME_ILLEGAL.sub("", name)
    return _MULTI_SPACE.sub(" ", name).strip()


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

    # Guard 2 — Length ratio: reject if strings are too different in length.
    # Strip year suffix before comparison so "Shrinking" vs "Shrinking (2023)"
    # doesn't get rejected — the year guard already handles year checking.
    if not processed_query or not processed_candidate:
        return None
    stripped_query = media_processor(_YEAR_SUFFIX.sub("", query))
    stripped_candidate = media_processor(_YEAR_SUFFIX.sub("", candidate))
    # Use stripped versions consistently — if EITHER is empty after stripping,
    # fall back to processed versions for both to avoid asymmetric comparison
    if stripped_query and stripped_candidate:
        len_query = len(stripped_query)
        len_candidate = len(stripped_candidate)
    else:
        len_query = len(processed_query)
        len_candidate = len(processed_candidate)
    shorter = min(len_query, len_candidate)
    longer = max(len_query, len_candidate)
    if shorter / longer < 0.67:
        return None

    # Guard 3 — Adaptive threshold: short titles need higher score.
    # Use stripped length so "Shrinking" (9 chars) vs "Shrinking (2023)"
    # uses the title-only length for threshold selection.
    effective_len = len(stripped_query) if stripped_query else len(processed_query)
    threshold = 95.0 if effective_len <= 10 else 90.0

    score = fuzz.WRatio(query, candidate, processor=media_processor)
    if score >= threshold:
        return score

    # If only ONE side has a year suffix, re-score without it.
    # Handles "Shrinking" vs "Shrinking (2023)" where WRatio drops to 90.
    # Don't re-score when BOTH have years — digit differences are meaningful.
    stripped_q_raw = _YEAR_SUFFIX.sub("", query).strip()
    stripped_c_raw = _YEAR_SUFFIX.sub("", candidate).strip()
    q_had_year = stripped_q_raw != query
    c_had_year = stripped_c_raw != candidate
    if q_had_year != c_had_year:  # exactly one side has a year
        score = fuzz.WRatio(stripped_q_raw, stripped_c_raw, processor=media_processor)
        if score >= threshold:
            return score

    return None
