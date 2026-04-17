"""Lightweight library scanner — structure, NFO, artwork inventory.

Scans storage disks without ffprobe. Produces LibraryScanItem for each
media directory found. Uses existing utilities: is_nfo_complete()
and SEASON_DIR_RE.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
    ISSUE_NTFS_UNSAFE,
    ISSUE_RELEASE_ARTIFACT,
    ArtworkStatus,
    LibraryScanItem,
    LibraryScanResult,
    NfoStatus,
    SeasonInfo,
)
from personalscraper.naming_patterns import SEASON_DIR_RE
from personalscraper.nfo_utils import is_nfo_complete

logger = logging.getLogger(__name__)

# Title (Year) pattern — same as _parse_folder_name in scraper
_TITLE_YEAR_RE = re.compile(r"^(.+?)\s*\((\d{4})\)\s*$")

# NTFS-illegal characters
_NTFS_ILLEGAL = re.compile(r'[<>:"/\\|?*]')

# Junk files (same set as process/cleanup.py)
# Includes .DS_Store, Thumbs.db, desktop.ini + macOS resource fork prefix "._"
_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})

# Video extensions (same set as sorter/file_type.py)
_VIDEO_EXTENSIONS = frozenset({
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "mpg", "mpeg",
    "m4v", "webm", "ts", "m2ts", "mts", "3gp", "vob", "ogv", "rmvb",
})

# Categories that contain TV shows (matching dispatch/media_index.py convention)
_SERIES_CATEGORIES = frozenset({
    "series", "series animations", "series documentaires",
    "series animes", "emissions",
})

# Categories where "Author Name" naming (no year) is normal
_AUTHOR_CATEGORIES = frozenset({"livres audios"})


def _parse_title_year(dirname: str) -> tuple[str, int | None]:
    """Parse 'Title (Year)' from a directory name.

    Args:
        dirname: Directory name (not full path).

    Returns:
        Tuple of (title, year). Year is None if not found.
    """
    m = _TITLE_YEAR_RE.match(dirname)
    if m:
        return m.group(1).strip(), int(m.group(2))
    return dirname, None


def _dir_size_gb(path: Path) -> float:
    """Calculate total size of all files in a directory (recursive), in GB.

    Args:
        path: Directory to measure.

    Returns:
        Total size in GB.
    """
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                try:
                    total += f.stat().st_size
                except OSError:
                    continue
    except OSError:
        pass
    return total / (1024 ** 3)


def _extract_nfo_ids(nfo_path: Path) -> tuple[str | None, str | None]:
    """Extract TMDB and IMDB IDs from a valid NFO file.

    Args:
        nfo_path: Path to .nfo file (must exist and be valid XML).

    Returns:
        Tuple of (tmdb_id, imdb_id). Either can be None.
    """
    try:
        root = ET.parse(nfo_path).getroot()  # noqa: S314
        tmdb_id = None
        imdb_id = None
        for uid in root.iter("uniqueid"):
            uid_type = uid.get("type", "").lower()
            text = (uid.text or "").strip()
            if not text:
                continue
            if uid_type == "tmdb":
                tmdb_id = text
            elif uid_type == "imdb":
                imdb_id = text
        return tmdb_id, imdb_id
    except (ET.ParseError, OSError):
        return None, None


def _check_artwork_movie(movie_dir: Path, title: str) -> ArtworkStatus:
    """Check which movie artwork files exist.

    Args:
        movie_dir: Path to movie directory.
        title: Movie title (used in filename pattern).

    Returns:
        ArtworkStatus with presence flags.
    """
    return ArtworkStatus(
        poster=(movie_dir / f"{title}-poster.jpg").exists(),
        fanart=(movie_dir / f"{title}-fanart.jpg").exists(),
        landscape=(movie_dir / f"{title}-landscape.jpg").exists(),
        banner=(movie_dir / f"{title}-banner.jpg").exists(),
        clearlogo=(movie_dir / f"{title}-clearlogo.png").exists(),
        clearart=(movie_dir / f"{title}-clearart.png").exists(),
        discart=(movie_dir / f"{title}-discart.png").exists(),
    )


def _check_artwork_tvshow(show_dir: Path) -> ArtworkStatus:
    """Check which TV show artwork files exist (fixed names).

    Args:
        show_dir: Path to TV show directory.

    Returns:
        ArtworkStatus with presence flags.
    """
    return ArtworkStatus(
        poster=(show_dir / "poster.jpg").exists(),
        fanart=(show_dir / "fanart.jpg").exists(),
        landscape=(show_dir / "landscape.jpg").exists(),
        banner=(show_dir / "banner.jpg").exists(),
        clearlogo=(show_dir / "clearlogo.png").exists(),
        clearart=(show_dir / "clearart.png").exists(),
        characterart=(show_dir / "characterart.png").exists(),
    )


def _detect_issues(
    media_dir: Path,
    title: str,
    year: int | None,
    is_tvshow: bool,
    category: str = "",
) -> tuple[list[str], bool]:
    """Detect common issues in a media directory.

    Args:
        media_dir: Path to media directory.
        title: Parsed title.
        year: Parsed year (None if missing).
        is_tvshow: Whether this is a TV show.
        category: Disk category name (used to skip year check for audiobooks).

    Returns:
        Tuple of (issues list, actors_dir_present bool).
    """
    issues: list[str] = []
    actors_dir = False

    for item in media_dir.iterdir():
        name = item.name

        # .actors directory
        if name == ".actors" and item.is_dir():
            actors_dir = True
            issues.append(ISSUE_ACTORS_DIR)
            continue

        # Junk files (including macOS resource forks "._*")
        if name in _JUNK_FILES or name.startswith("._"):
            issues.append(ISSUE_JUNK_FILES)
            continue

        # Empty subdirectories
        if item.is_dir() and not any(item.iterdir()):
            if is_tvshow and not SEASON_DIR_RE.match(name):
                # Non-season empty dir in a tvshow (likely release artifact)
                issues.append(ISSUE_RELEASE_ARTIFACT)
            else:
                # Empty dir in a movie, or empty season dir in a tvshow
                issues.append(ISSUE_EMPTY_SUBDIR)

        # NTFS-unsafe names
        if _NTFS_ILLEGAL.search(name):
            issues.append(ISSUE_NTFS_UNSAFE)

    # Bad directory naming (no year) — skip for audiobook categories
    if year is None and category not in _AUTHOR_CATEGORIES:
        issues.append(ISSUE_BAD_DIR_NAME)

    # Deduplicate (e.g. multiple junk files -> one issue)
    return list(dict.fromkeys(issues)), actors_dir


def _scan_seasons(show_dir: Path) -> list[SeasonInfo]:
    """Scan TV show season directories.

    Args:
        show_dir: Path to TV show directory.

    Returns:
        List of SeasonInfo, sorted by season number.
    """
    seasons: list[SeasonInfo] = []
    for subdir in sorted(show_dir.iterdir()):
        if not subdir.is_dir() or not SEASON_DIR_RE.match(subdir.name):
            continue
        # Extract season number from "Saison XX"
        parts = subdir.name.split()
        try:
            season_num = int(parts[-1])
        except (ValueError, IndexError):
            continue

        # Count video files and NFO files
        episode_count = 0
        nfo_count = 0
        for f in subdir.iterdir():
            if f.is_file():
                ext = f.suffix.lstrip(".").lower()
                if ext in _VIDEO_EXTENSIONS:
                    episode_count += 1
                elif ext == "nfo":
                    nfo_count += 1

        # Check season poster
        poster_name = f"season{season_num:02d}-poster.jpg"
        has_poster = (show_dir / poster_name).exists()

        seasons.append(SeasonInfo(
            number=season_num,
            path=str(subdir),
            episode_count=episode_count,
            has_poster=has_poster,
            episodes_with_nfo=nfo_count,
        ))

    return seasons


def scan_movie_dir(movie_dir: Path, disk: str, category: str) -> LibraryScanItem:
    """Scan a single movie directory and collect metadata.

    Args:
        movie_dir: Path to the movie directory.
        disk: Disk name (e.g. "Disk1").
        category: Category name (e.g. "films").

    Returns:
        LibraryScanItem with all collected metadata.
    """
    title, year = _parse_title_year(movie_dir.name)

    # NFO check
    nfo_path = movie_dir / f"{title}.nfo"
    nfo_valid = is_nfo_complete(nfo_path)
    tmdb_id, imdb_id = (None, None)
    if nfo_valid:
        tmdb_id, imdb_id = _extract_nfo_ids(nfo_path)

    nfo = NfoStatus(
        present=nfo_path.exists(),
        valid=nfo_valid,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
    )

    artwork = _check_artwork_movie(movie_dir, title)
    issues, actors_dir = _detect_issues(movie_dir, title, year, is_tvshow=False, category=category)
    size_gb = _dir_size_gb(movie_dir)

    return LibraryScanItem(
        path=str(movie_dir),
        disk=disk,
        category=category,
        media_type="movie",
        title=title,
        year=year,
        folder_size_gb=round(size_gb, 3),
        nfo=nfo,
        artwork=artwork,
        actors_dir=actors_dir,
        issues=issues,
        seasons=None,
        scanned_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def scan_tvshow_dir(show_dir: Path, disk: str, category: str) -> LibraryScanItem:
    """Scan a single TV show directory and collect metadata.

    Args:
        show_dir: Path to the TV show directory.
        disk: Disk name (e.g. "Disk1").
        category: Category name (e.g. "series").

    Returns:
        LibraryScanItem with all collected metadata including seasons.
    """
    title, year = _parse_title_year(show_dir.name)

    # NFO check (tvshow.nfo is a fixed name)
    nfo_path = show_dir / "tvshow.nfo"
    nfo_valid = is_nfo_complete(nfo_path)
    tmdb_id, imdb_id = (None, None)
    if nfo_valid:
        tmdb_id, imdb_id = _extract_nfo_ids(nfo_path)

    nfo = NfoStatus(
        present=nfo_path.exists(),
        valid=nfo_valid,
        tmdb_id=tmdb_id,
        imdb_id=imdb_id,
    )

    artwork = _check_artwork_tvshow(show_dir)
    issues, actors_dir = _detect_issues(show_dir, title, year, is_tvshow=True, category=category)
    seasons = _scan_seasons(show_dir)
    size_gb = _dir_size_gb(show_dir)

    return LibraryScanItem(
        path=str(show_dir),
        disk=disk,
        category=category,
        media_type="tvshow",
        title=title,
        year=year,
        folder_size_gb=round(size_gb, 3),
        nfo=nfo,
        artwork=artwork,
        actors_dir=actors_dir,
        issues=issues,
        seasons=seasons,
        scanned_at=datetime.now(tz=timezone.utc).isoformat(),
    )


def scan_library(
    disk_configs: list,
    disk_filter: str | None = None,
    category_filter: str | None = None,
) -> LibraryScanResult:
    """Scan all mounted storage disks and collect library inventory.

    Iterates disk configs, filters by disk/category if specified,
    scans each media directory, and produces a LibraryScanResult.

    Args:
        disk_configs: List of DiskConfig objects from Settings.
        disk_filter: Only scan this disk (e.g. "Disk1"). None = all.
        category_filter: Only scan this category (e.g. "films"). None = all.

    Returns:
        LibraryScanResult with all scanned items.
    """
    items: list[LibraryScanItem] = []
    start = datetime.now(tz=timezone.utc).isoformat()

    for config in disk_configs:
        # Disk filter
        if disk_filter and config.name != disk_filter:
            continue

        # Skip unmounted disks
        if not config.path.exists():
            logger.warning("Disk not mounted: %s (%s)", config.name, config.path)
            continue

        # Iterate categories
        for category_dir in sorted(config.path.iterdir()):
            if not category_dir.is_dir():
                continue
            category_name = category_dir.name
            if category_name not in config.categories:
                continue
            if category_filter and category_name != category_filter:
                continue

            is_series = category_name in _SERIES_CATEGORIES

            # Iterate media directories
            for media_dir in sorted(category_dir.iterdir()):
                if not media_dir.is_dir() or media_dir.name.startswith("."):
                    continue
                try:
                    if is_series:
                        item = scan_tvshow_dir(media_dir, config.name, category_name)
                    else:
                        item = scan_movie_dir(media_dir, config.name, category_name)
                    items.append(item)
                except OSError as exc:
                    logger.warning("Error scanning %s: %s", media_dir, exc)

    return LibraryScanResult(
        scanned_at=start,
        disk_filter=disk_filter,
        category_filter=category_filter,
        item_count=len(items),
        items=items,
    )
