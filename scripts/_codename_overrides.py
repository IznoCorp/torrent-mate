"""Codename override table for design-doc → feature-codename resolution.

Present-version documents under ``docs/production/`` (e.g. ``docs/production/scraping.md``) do not follow the
``docs/features/<codename>/`` convention. The override table maps each known
reference doc to its canonical codename so the two-direction audit works.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

CODENAME_OVERRIDES: Final[dict[str, str]] = {
    "docs/production/scraping.md": "scraper",
    "docs/production/storage.md": "dispatch",
    "docs/production/pipeline-internals.md": "pipeline",
    "docs/production/trailers.md": "trailers",
    "docs/production/indexer.md": "indexer",
    # ``indexer-json-shapes.md`` documents Pydantic models for individual
    # JSON columns; it gets its own codename so contracts pinning JSON
    # shapes do not collide with behavioral indexer contracts (one map
    # file per design doc — DESIGN §3.3.1 collision policy).
    "docs/production/indexer-json-shapes.md": "indexer-json-shapes",
    "docs/production/architecture.md": "architecture",
    # The archived api-unify design is the one archived file tests contract against; it
    # moved to production with them, under a name that says what it is.
    "docs/production/api-unify-design.md": "api-unify",
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
