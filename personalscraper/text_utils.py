"""Shared text processing utilities for media title matching.

Provides media_processor() — a custom rapidfuzz processor that normalizes
media titles for accent-insensitive French matching. Used by V2 (matcher.py),
V3 (confidence.py), and V5 (media_index.py).

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
