"""Validate and fix directory structure for staging media items.

Checks NFO count, artwork duplicates, season structure, and torrent
residuals. Fixes what can be fixed, reports what can't.
"""

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.conf.models import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.sorter.file_type import FileType
from personalscraper.text_utils import sanitize_filename

logger = logging.getLogger(__name__)
_ARTWORK_SUFFIXES = (
    "-poster",
    "-fanart",
    "-banner",
    "-landscape",
    "-clearlogo",
    "-clearart",
    "-discart",
    "-thumb",
)


@dataclass
class StructureResult:
    """Result of validating/fixing structure for one media item.

    Attributes:
        path: Absolute path to the media directory.
        media_type: Either ``"movie"`` or ``"tvshow"``.
        action: Summary outcome — ``"validated"``, ``"repaired"``, or
            ``"error"``.
        fixes: List of human-readable descriptions of changes made.
        warnings: Non-fatal issues that did not prevent validation.
    """

    path: Path
    media_type: str  # "movie" or "tvshow"
    action: str  # "validated", "repaired", "error"
    fixes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_structure(
    settings: Settings,
    config: Config,
    dry_run: bool = False,
) -> list[StructureResult]:
    """Validate and fix directory structure for all staging items.

    Iterates over every top-level directory in ``{movies_dir}/`` and
    ``{tvshows_dir}/``, running the appropriate validation logic for each.
    Fixes are applied in-place unless *dry_run* is ``True``.

    Args:
        settings: Pipeline configuration (reserved for future use).
        config: Application config used to resolve staging_dir and category folder names.
        dry_run: When ``True``, report planned fixes without modifying
            the filesystem.

    Returns:
        One :class:`StructureResult` per media directory scanned.
    """
    results: list[StructureResult] = []
    staging = config.paths.staging_dir

    movies_dir = staging / folder_name(find_by_file_type(config, FileType.MOVIE))
    if movies_dir.exists():
        for folder in sorted(movies_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_validate_movie(folder, dry_run))

    tvshows_dir = staging / folder_name(find_by_file_type(config, FileType.TVSHOW))
    if tvshows_dir.exists():
        for folder in sorted(tvshows_dir.iterdir()):
            if folder.is_dir() and not folder.name.startswith("."):
                results.append(_validate_tvshow(folder, dry_run))

    return results


def _validate_movie(movie_dir: Path, dry_run: bool) -> StructureResult:
    """Validate a single movie directory.

    Checks:
    - Extra NFO files (keeps ``{Title}.nfo``, removes residuals).
    - Duplicate artwork of the same type (keeps the canonically-named
      file, removes the rest).

    Args:
        movie_dir: Path to the movie directory (e.g. ``Film (2025)/``).
        dry_run: When ``True``, report planned fixes without touching
            the filesystem.

    Returns:
        A :class:`StructureResult` for this movie directory.
    """
    result = StructureResult(path=movie_dir, media_type="movie", action="validated")

    # Derive expected NFO name from the folder name — strip year suffix first.
    title = re.sub(r"\s*\(\d{4}\)\s*$", "", movie_dir.name).strip()
    expected_nfo = sanitize_filename(title) + ".nfo"

    # --- Extra NFO removal -----------------------------------------------
    for nfo in list(movie_dir.glob("*.nfo")):
        if nfo.name != expected_nfo:
            if not dry_run:
                try:
                    nfo.unlink()
                except OSError as exc:
                    logger.warning("Cannot delete extra NFO %s: %s", nfo.name, exc)
                    continue
            result.fixes.append(f"Removed extra NFO: {nfo.name}")

    # --- Duplicate artwork removal ----------------------------------------
    # Group files by artwork type suffix so we can detect duplicates.
    artwork_by_type: dict[str, list[Path]] = {}
    for f in movie_dir.iterdir():
        if not f.is_file():
            continue
        for suffix in _ARTWORK_SUFFIXES:
            if suffix in f.stem:
                artwork_by_type.setdefault(suffix, []).append(f)
                break

    for art_type, files in artwork_by_type.items():
        if len(files) <= 1:
            continue

        # Canonical name is ``{sanitized_title}{art_type}.{ext}`` — prefer
        # the file whose stem matches exactly; fall back to the first file.
        expected_stem = sanitize_filename(title) + art_type
        keep = next((f for f in files if f.stem == expected_stem), files[0])

        for f in files:
            if f == keep:
                continue
            if not dry_run:
                try:
                    f.unlink()
                except OSError as exc:
                    logger.warning("Cannot delete duplicate artwork %s: %s", f.name, exc)
                    continue
            result.fixes.append(f"Removed duplicate artwork: {f.name}")

    if result.fixes:
        result.action = "repaired"
    return result


def _validate_tvshow(show_dir: Path, dry_run: bool) -> StructureResult:
    """Validate a single TV show directory.

    Checks:
    - Empty non-season subdirectories (leftover torrent extraction dirs).

    Also warns when ``tvshow.nfo`` is absent, but does not mark this as
    an error — it will be addressed by the scraper step.

    Args:
        show_dir: Path to the TV show directory (e.g. ``Show (2025)/``).
        dry_run: When ``True``, report planned fixes without touching
            the filesystem.

    Returns:
        A :class:`StructureResult` for this show directory.
    """
    result = StructureResult(path=show_dir, media_type="tvshow", action="validated")

    # Remove empty non-season subdirs left behind by torrent extractors.
    # Season dirs match ``Saison \d+`` and are always preserved.
    for subdir in list(show_dir.iterdir()):
        if not subdir.is_dir() or subdir.name.startswith(".") or SEASON_DIR_RE.match(subdir.name):
            continue

        # ``rglob("*")`` yields any file or sub-directory — an empty dir
        # produces no results at all, so ``any(...)`` is False.
        has_files = any(subdir.rglob("*"))
        if not has_files:
            if not dry_run:
                try:
                    subdir.rmdir()
                except OSError as exc:
                    logger.warning("Cannot remove empty torrent dir %s: %s", subdir.name, exc)
                    continue
            result.fixes.append(f"Removed empty torrent dir: {subdir.name}")

    if not (show_dir / "tvshow.nfo").exists():
        result.warnings.append("Missing tvshow.nfo")

    # Remove season posters for non-present seasons
    present_seasons = {d.name for d in show_dir.iterdir() if d.is_dir() and SEASON_DIR_RE.match(d.name)}
    for f in list(show_dir.iterdir()):
        if not f.is_file() or not f.name.startswith("season"):
            continue
        # Extract season number from "seasonNN-poster.jpg"
        match = re.match(r"^season(\d+)-", f.name)
        if not match:
            continue
        season_num = int(match.group(1))
        season_dir_name = f"Saison {season_num:02d}"
        if season_dir_name not in present_seasons:
            if not dry_run:
                try:
                    f.unlink()
                except OSError as exc:
                    logger.warning("Cannot remove orphan season poster %s: %s", f.name, exc)
                    continue
            result.fixes.append(f"Removed orphan season poster: {f.name}")

    if result.fixes:
        result.action = "repaired"
    return result
