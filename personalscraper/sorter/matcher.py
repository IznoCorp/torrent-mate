"""Fuzzy directory matching for existing media folders.

Replaces FileMate's bidirectional token matcher with rapidfuzz WRatio,
which handles token reordering, partial matches, and varying string
lengths automatically. Uses media_processor for accent-insensitive
French title matching.

This module is specific to V2 sorting (matching against staging subdirs).
V3 and V5 use rapidfuzz directly for API title and disk index matching.
"""

import re
from pathlib import Path

# Year pattern: 4-digit year in parentheses or standalone
_YEAR_PATTERN: re.Pattern[str] = re.compile(r"\b((?:19|20)\d{2})\b")


def _extract_year(name: str) -> int | None:
    """Extract a year (19xx/20xx) from a directory name.

    Args:
        name: Directory name, possibly containing a year.

    Returns:
        The year as int, or None if not found.
    """
    match = _YEAR_PATTERN.search(name)
    return int(match.group(1)) if match else None


def find_matching_directory(
    name: str,
    candidates: list[Path],
    respect_year: bool = True,
    threshold: float = 85.0,
) -> Path | None:
    """Find the best matching existing directory with anti-false-positive guards.

    Uses fuzzy_match_score() for accent-insensitive French title matching
    with three guards: year constraint (±1), length ratio (≥0.67), and
    adaptive threshold (95% for short titles, 90% for long).

    The threshold parameter is kept for backward compatibility but is
    overridden by fuzzy_match_score's adaptive threshold internally.

    Args:
        name: The cleaned media name to match (e.g. "The Matrix").
        candidates: List of existing directory paths to match against.
        respect_year: If True, year guard is active in fuzzy_match_score.
            If False, years are not passed to the guard function.
        threshold: Legacy parameter — overridden by adaptive threshold.

    Returns:
        The Path of the best matching directory, or None if no match
        passes the guards.
    """
    from personalscraper.text_utils import fuzzy_match_score

    if not candidates:
        return None

    name_year = _extract_year(name) if respect_year else None

    best_score = 0.0
    best_candidate: Path | None = None

    for cand in candidates:
        cand_year = _extract_year(cand.name) if respect_year else None
        score = fuzzy_match_score(
            name, cand.name,
            query_year=name_year,
            candidate_year=cand_year,
        )
        if score is not None and score > best_score:
            best_score = score
            best_candidate = cand

    return best_candidate
