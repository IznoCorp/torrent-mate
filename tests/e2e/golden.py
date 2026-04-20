"""Golden file loader and matcher for E2E test validation.

Loads expected results from JSON golden files in assets/torrents/expected/
and matches torrent names to their golden files using fuzzy matching.
Golden files provide exact validation (NFO invariants, artwork, structure,
dispatch) on top of the existing smoke-test assertions.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

from personalscraper.text_utils import media_processor

logger = logging.getLogger(__name__)

EXPECTED_DIR = Path(__file__).parents[2] / "assets" / "torrents" / "expected"

# Regex to strip release group tags and technical info from torrent names
_STRIP_PATTERNS = [
    r"\[.*?\]",  # [LaCale], [720p], etc.
    r"\b\d{3,4}p\b",  # 720p, 1080p
    r"\bBluRay\b",
    r"\bWEBRip\b",
    r"\bWEB-?DL\b",
    r"\bHDLight\b",
    r"\bHDRip\b",
    r"\bMULTi\b",
    r"\bVF\d*\b",  # VF, VF2
    r"\bVFI\b",
    r"\bNOST\b",
    r"\bDD5\.1\b",
    r"\bAAC\s*5\.1\b",
    r"\bx26[45]\b",
    r"\bHEVC\b",
    r"\bH\.?26[45]\b",
    r"-\w+$",  # -PopHD, -Papaya at end
]


def _normalize_torrent_name(name: str) -> str:
    """Normalize a torrent name for matching against golden file slugs.

    Strips release group tags, codec info, resolution labels, and
    other technical metadata. Converts dots/underscores to spaces.

    Args:
        name: Raw torrent filename (without extension).

    Returns:
        Cleaned, lowercased name suitable for fuzzy matching.
    """
    cleaned = name
    for pattern in _STRIP_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # Convert dots and underscores to spaces
    cleaned = cleaned.replace(".", " ").replace("_", " ")
    # Collapse whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def _slug_to_display(slug: str) -> str:
    """Convert a golden file slug to a display name for matching.

    Args:
        slug: Directory slug (e.g. "jumanji_1995").

    Returns:
        Display name (e.g. "jumanji 1995").
    """
    return slug.replace("_", " ")


@dataclass
class GoldenFile:
    """Loaded golden file data for a single torrent.

    Attributes:
        name: Torrent identifier (e.g. "jumanji_1995").
        nfo: Expected NFO data (required_nfo_tags, nfo_invariants, etc.).
        artwork: Expected artwork data (required files, min sizes).
        structure: Expected directory structure (files, dirs, forbidden).
        dispatch: Expected dispatch results (action, eligible disks).
    """

    name: str
    nfo: dict
    artwork: dict
    structure: dict
    dispatch: dict


def load_golden_file(torrent_slug: str) -> GoldenFile:
    """Load all golden files for a torrent.

    Args:
        torrent_slug: Directory name in expected/ (e.g. "jumanji_1995").

    Returns:
        GoldenFile with all expected data loaded.

    Raises:
        FileNotFoundError: If the golden file directory doesn't exist.
    """
    golden_dir = EXPECTED_DIR / torrent_slug
    if not golden_dir.is_dir():
        raise FileNotFoundError(f"Golden file directory not found: {golden_dir}")

    def _load_json(filename: str) -> dict:
        """Load a JSON file, returning empty dict if absent."""
        path = golden_dir / filename
        if not path.exists():
            return {}
        with open(path) as f:
            return json.load(f)

    return GoldenFile(
        name=torrent_slug,
        nfo=_load_json("expected_nfo.json"),
        artwork=_load_json("expected_artwork.json"),
        structure=_load_json("expected_structure.json"),
        dispatch=_load_json("expected_dispatch.json"),
    )


def match_torrent_to_golden(torrent_name: str) -> GoldenFile | None:
    """Match a torrent name to its golden file.

    Uses fuzzy matching to find the correct golden file directory
    from the torrent filename. Normalizes the torrent name by stripping
    release tags, codecs, and resolution info.

    Args:
        torrent_name: Raw torrent filename (e.g. "[LaCale]-Jumanji.1995...").

    Returns:
        GoldenFile if matched (score >= 80), None if no golden file exists.
    """
    if not EXPECTED_DIR.exists():
        return None

    slugs = [d.name for d in EXPECTED_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
    if not slugs:
        return None

    normalized = _normalize_torrent_name(torrent_name)

    best_slug: str | None = None
    best_score = 0.0

    for slug in slugs:
        display = _slug_to_display(slug)
        score = fuzz.WRatio(normalized, display, processor=media_processor)
        if score > best_score:
            best_score = score
            best_slug = slug

    if best_slug and best_score >= 80:
        logger.info(
            "Golden match: '%s' → '%s' (score=%.1f)",
            torrent_name,
            best_slug,
            best_score,
        )
        return load_golden_file(best_slug)

    logger.debug(
        "No golden match for '%s' (best: '%s' score=%.1f)",
        torrent_name,
        best_slug,
        best_score,
    )
    return None


def discover_golden_files() -> list[GoldenFile]:
    """Discover all golden files in assets/torrents/expected/.

    Returns:
        List of all available GoldenFile objects.
    """
    if not EXPECTED_DIR.exists():
        return []

    golden_files = []
    for d in sorted(EXPECTED_DIR.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            golden_files.append(load_golden_file(d.name))

    return golden_files
