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

from rapidfuzz import fuzz, process

from personalscraper.text_utils import media_processor

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
    """Find the best matching existing directory via rapidfuzz WRatio.

    Uses media_processor for accent-insensitive French title matching.
    WRatio auto-selects the best scoring strategy based on string length
    ratio (exact ratio for similar lengths, partial for very different).

    Args:
        name: The cleaned media name to match (e.g. "The Matrix").
        candidates: List of existing directory paths to match against.
        respect_year: If True and both names contain a year, years must
            match. Prevents "The Matrix (1999)" matching "The Matrix
            Reloaded (2003)".
        threshold: Minimum WRatio score (0-100) to accept a match.

    Returns:
        The Path of the best matching directory, or None if no match
        exceeds the threshold.
    """
    if not candidates:
        return None

    name_year = _extract_year(name) if respect_year else None

    # Build candidate list, filtering by year when applicable
    valid_candidates: list[Path] = []
    for cand in candidates:
        if respect_year and name_year is not None:
            cand_year = _extract_year(cand.name)
            # If candidate also has a year, it must match
            if cand_year is not None and cand_year != name_year:
                continue
        valid_candidates.append(cand)

    if not valid_candidates:
        return None

    # rapidfuzz process.extractOne returns (match_string, score, index)
    candidate_names = [c.name for c in valid_candidates]
    result = process.extractOne(
        name,
        candidate_names,
        scorer=fuzz.WRatio,
        processor=media_processor,
        score_cutoff=threshold,
    )

    if result is None:
        return None

    _, _, idx = result
    return valid_candidates[idx]
