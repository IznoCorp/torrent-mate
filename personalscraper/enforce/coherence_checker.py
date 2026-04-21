"""Cross-step coherence checker for staging media.

Read-only checker that parses NFOs, verifies genre_mapper consistency,
and checks sort↔process coherence. Produces warnings, never modifies
the filesystem.
"""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.config import Settings

logger = logging.getLogger(__name__)


@dataclass
class CoherenceResult:
    """Result of coherence check for one media item.

    Attributes:
        path: Absolute path to the media directory.
        checks: List of check names that were performed.
        warnings: Human-readable non-fatal issues found.
    """

    path: Path
    checks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def check_coherence(settings: Settings, dry_run: bool = False) -> list[CoherenceResult]:
    """Check cross-step coherence for all staging items.

    Iterates over every media directory in 001-MOVIES and 002-TVSHOWS,
    verifying sort/process coherence and NFO metadata consistency.
    This function is read-only — it never modifies the filesystem.

    Args:
        settings: Pipeline configuration.
        dry_run: No effect (coherence check is always read-only).

    Returns:
        List of CoherenceResult, one per media directory found.
    """
    results: list[CoherenceResult] = []
    staging = settings.staging_dir

    movies_dir = staging / settings.movies_dir_name
    if movies_dir.exists():
        for folder in sorted(movies_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_check_movie(folder))

    tvshows_dir = staging / settings.tvshows_dir_name
    if tvshows_dir.exists():
        for folder in sorted(tvshows_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_check_tvshow(folder))

    return results


def _check_movie(movie_dir: Path) -> CoherenceResult:
    """Check coherence for a single movie directory.

    Detects TV show NFOs misplaced in the MOVIES category, and validates
    that at least one NFO contains a recognised external ID.

    Args:
        movie_dir: Path to the movie folder.

    Returns:
        CoherenceResult with any warnings found.
    """
    result = CoherenceResult(path=movie_dir)

    # A tvshow.nfo in MOVIES indicates a mis-sorted TV show
    if (movie_dir / "tvshow.nfo").exists():
        result.warnings.append(f"Wrong category: {movie_dir.name} has tvshow.nfo but is in MOVIES")
    result.checks.append("sort_process_coherence")

    nfos = list(movie_dir.glob("*.nfo"))
    if nfos:
        _check_nfo_ids(nfos[0], result)

    return result


def _check_tvshow(show_dir: Path) -> CoherenceResult:
    """Check coherence for a single TV show directory.

    Detects movie NFOs misplaced in TVSHOWS, validates external IDs in the
    show-level NFO, and checks whether the genre suggests a different category.

    Args:
        show_dir: Path to the TV show folder.

    Returns:
        CoherenceResult with any warnings found.
    """
    result = CoherenceResult(path=show_dir)

    nfo_path = show_dir / "tvshow.nfo"
    if not nfo_path.exists():
        # A movie-style NFO in TVSHOWS indicates a mis-sorted movie
        movie_nfos = [f for f in show_dir.glob("*.nfo") if f.name != "tvshow.nfo"]
        if movie_nfos:
            result.warnings.append(f"Wrong category: {show_dir.name} has movie NFO but is in TVSHOWS")
    else:
        _check_nfo_ids(nfo_path, result)
        _check_genre_coherence(nfo_path, result)

    result.checks.append("sort_process_coherence")
    return result


def _check_nfo_ids(nfo_path: Path, result: CoherenceResult) -> None:
    """Check that an NFO file contains at least one valid external ID.

    A valid NFO should have at least one <uniqueid> element with type
    "tmdb" or "imdb" and non-empty text. Missing both is a warning.

    Args:
        nfo_path: Path to the NFO XML file.
        result: CoherenceResult to append warnings and checks to (mutated).
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
    except (ET.ParseError, OSError):
        result.warnings.append(f"Cannot parse NFO: {nfo_path.name}")
        result.checks.append("nfo_ids")
        return

    has_tmdb = False
    has_imdb = False
    for uid in root.findall("uniqueid"):
        uid_type = uid.get("type", "")
        if uid_type == "tmdb" and uid.text and uid.text.strip():
            has_tmdb = True
        elif uid_type == "imdb" and uid.text and uid.text.strip():
            has_imdb = True

    if not has_tmdb and not has_imdb:
        result.warnings.append(f"Missing IDs: no TMDB or IMDB in {nfo_path.name}")

    result.checks.append("nfo_ids")


def _check_genre_coherence(nfo_path: Path, result: CoherenceResult) -> None:
    """Check whether the NFO genre suggests a different target category.

    Uses GenreMapper.categorize_from_nfo() to determine the implied category.
    If the genre implies a TV_PROGRAMS category (V14: "emissions") but the item
    is in the default TVSHOWS bucket, a warning is emitted so the operator can
    review and re-categorise manually.

    Args:
        nfo_path: Path to the tvshow NFO file.
        result: CoherenceResult to append warnings and checks to (mutated).
    """
    # V14 label returned by genre_mapper; mapped to CID.TV_PROGRAMS in V15.
    _V14_TV_PROGRAMS_LABEL = "emissions"

    try:
        from personalscraper.genre_mapper import GenreMapper

        mapper = GenreMapper()
        category = mapper.categorize_from_nfo(nfo_path, media_type="tvshow")
        if category and category == _V14_TV_PROGRAMS_LABEL:
            result.warnings.append(f"Genre suggests TV program (emissions) not series for {result.path.name}")
    except (ET.ParseError, OSError, ValueError, ImportError) as exc:
        logger.warning("Genre check failed for %s: %s", nfo_path.name, exc)
        result.warnings.append(f"Genre check failed: {exc}")

    result.checks.append("genre_coherence")
