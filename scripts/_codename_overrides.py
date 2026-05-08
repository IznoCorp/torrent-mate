"""Codename override table for design-doc → feature-codename resolution.

Reference docs (e.g. ``docs/reference/scraping.md``) do not follow the
``docs/features/<codename>/`` convention. The override table maps each known
reference doc to its canonical codename so the two-direction audit works.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

CODENAME_OVERRIDES: Final[dict[str, str]] = {
    "docs/reference/scraping.md": "scraper",
    "docs/reference/storage.md": "dispatch",
    "docs/reference/pipeline-internals.md": "pipeline",
    "docs/reference/trailers.md": "trailers",
    "docs/reference/indexer.md": "indexer",
    "docs/reference/indexer-json-shapes.md": "indexer",
    "docs/reference/architecture.md": "architecture",
    # Provider docs auto-resolve via stem (tmdb-api.md → tmdb, etc.).
    # Add explicit entries here if a provider doc uses a non-stem codename.
}


def resolve_codename(design_path: str) -> str:
    """Resolve a design doc path to its canonical codename.

    Order: explicit override → ``features/<codename>/`` segment → file stem.

    Args:
        design_path: Relative path from repo root.

    Returns:
        Canonical codename (filename-safe, lowercase).
    """
    if design_path in CODENAME_OVERRIDES:
        return CODENAME_OVERRIDES[design_path]

    parts = Path(design_path).parts
    if "features" in parts:
        idx = parts.index("features")
        if idx + 1 < len(parts):
            return parts[idx + 1]

    stem = Path(design_path).stem
    # Provider doc convention: foo-api.md → foo
    if stem.endswith("-api"):
        stem = stem[: -len("-api")]
    return stem
