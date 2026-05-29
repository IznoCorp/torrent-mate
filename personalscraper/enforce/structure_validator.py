"""Validate and fix directory structure for staging media items.

Checks NFO count, artwork duplicates, season structure, and torrent
residuals. Fixes what can be fixed, reports what can't.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from personalscraper.conf.models.config import Config
from personalscraper.conf.staging import find_by_file_type, folder_name
from personalscraper.config import Settings
from personalscraper.core.media_types import FileType
from personalscraper.logger import get_logger
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.text_utils import sanitize_filename

log = get_logger("enforce.structure")
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
                    log.warning("enforce_structure_nfo_delete_failed", name=nfo.name, exc_info=True, error=str(exc))
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
                    log.warning("enforce_structure_artwork_delete_failed", name=f.name, exc_info=True, error=str(exc))
                    continue
            result.fixes.append(f"Removed duplicate artwork: {f.name}")

    if result.fixes:
        result.action = "repaired"
    return result


_EPISODE_SEASON_RE = re.compile(r"S(\d{1,2})E\d+", re.IGNORECASE)
_VIDEO_SUFFIXES = {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".ts"}


def _move_orphan_episodes_to_seasons(show_dir: Path, result: StructureResult, dry_run: bool) -> None:
    """Move root-level episode video files into the matching ``Saison NN/`` subdir.

    Scans ``show_dir`` for video files that sit directly at the show root
    (i.e. not inside any ``Saison NN/`` subdirectory) and whose filename
    contains a season pattern such as ``S01E03``.  Each matching file is
    moved into ``Saison 01/`` (zero-padded two digits), which is created
    if it does not yet exist.  Files without a recognisable season number
    are left in place.

    Args:
        show_dir: Path to the TV show directory (e.g. ``Show (2025)/``).
        result: :class:`StructureResult` to append fix/warning messages to.
        dry_run: When ``True``, report planned moves without touching the
            filesystem.
    """
    for f in list(show_dir.iterdir()):
        if not f.is_file() or f.suffix.lower() not in _VIDEO_SUFFIXES:
            continue
        match = _EPISODE_SEASON_RE.search(f.name)
        if not match:
            # No season number extractable — leave the file alone, but emit
            # an info event so operators know about extras/specials at the root.
            log.info("enforce.orphan_episode_no_season", path=str(f))
            continue
        season_num = int(match.group(1))
        season_dir = show_dir / f"Saison {season_num:02d}"
        dst = season_dir / f.name
        if not dry_run:
            season_dir.mkdir(exist_ok=True)
            try:
                f.rename(dst)
            except OSError as exc:
                log.warning(
                    "enforce.orphan_episode_move_failed",
                    src=str(f),
                    dst=str(dst),
                    exc_info=True,
                    error=str(exc),
                )
                result.warnings.append(f"Failed to move orphan episode '{f.name}' into Saison folder: {exc}")
                continue
        log.info("enforce.orphan_episode_moved", src=str(f), dst=str(dst))
        result.fixes.append(f"Moved orphan episode: {f.name} → {season_dir.name}/")


def _validate_tvshow(show_dir: Path, dry_run: bool) -> StructureResult:
    """Validate a single TV show directory.

    Checks:
    - Orphan episode video files at the show root that match ``SxxEyy`` —
      moved into the corresponding ``Saison NN/`` subdirectory (created if
      missing).
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

    # Move orphan episode files at root level into their Saison NN/ subdir.
    _move_orphan_episodes_to_seasons(show_dir, result, dry_run)

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
                    log.warning("enforce_structure_torrent_dir_failed", name=subdir.name, exc_info=True, error=str(exc))
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
                    log.warning("enforce_structure_orphan_poster_failed", name=f.name, exc_info=True, error=str(exc))
                    continue
            result.fixes.append(f"Removed orphan season poster: {f.name}")

    if result.fixes:
        result.action = "repaired"
    return result
