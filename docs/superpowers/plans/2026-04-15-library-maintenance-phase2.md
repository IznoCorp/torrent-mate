# Phase 2: Scanner — library-scan command

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `personalscraper library-scan` — lightweight inventory of all media on storage disks (structure, NFO, artwork, issues). No ffprobe.

**Architecture:** `scanner.py` iterates disks via `DiskConfig`, collects metadata per item using existing utilities (`is_nfo_complete`, `PATTERNS`, `SEASON_DIR_RE`), writes `library_scan.json`.

**Tech Stack:** Python, Typer, dataclasses, pytest

---

## Task 1: Implement core scanner logic

**Files:**

- Create: `personalscraper/library/scanner.py`
- Create: `tests/library/test_scanner.py`

- [ ] **Step 1: Write failing tests for single-item scanning**

```python
# tests/library/test_scanner.py
"""Tests for personalscraper.library.scanner — lightweight disk scanner."""

from pathlib import Path

from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
)
from personalscraper.library.scanner import scan_movie_dir, scan_tvshow_dir


class TestScanMovieDir:
    """Tests for scan_movie_dir — single movie directory scanning."""

    def test_complete_movie(self, tmp_path: Path) -> None:
        """Movie with NFO, poster, landscape should have no issues."""
        movie = tmp_path / "The Matrix (1999)"
        movie.mkdir()
        (movie / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
        (movie / "The Matrix.nfo").write_text(
            '<movie><uniqueid type="tmdb">603</uniqueid></movie>'
        )
        (movie / "The Matrix-poster.jpg").write_bytes(b"\x00")
        (movie / "The Matrix-landscape.jpg").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert item.title == "The Matrix"
        assert item.year == 1999
        assert item.nfo.present is True
        assert item.nfo.valid is True
        assert item.nfo.tmdb_id == "603"
        assert item.artwork.poster is True
        assert item.artwork.landscape is True
        assert item.issues == []
        assert item.seasons is None

    def test_movie_with_actors_dir(self, tmp_path: Path) -> None:
        """Movie with .actors/ should flag ISSUE_ACTORS_DIR."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid></movie>'
        )
        (movie / ".actors").mkdir()
        (movie / ".actors" / "Actor.jpg").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert item.actors_dir is True
        assert ISSUE_ACTORS_DIR in item.issues

    def test_movie_missing_nfo(self, tmp_path: Path) -> None:
        """Movie without NFO should report nfo.present=False."""
        movie = tmp_path / "NoNfo (2024)"
        movie.mkdir()
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert item.nfo.present is False
        assert item.nfo.valid is False

    def test_movie_with_empty_subdir(self, tmp_path: Path) -> None:
        """Movie with empty subdirectory should flag it."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Subs").mkdir()  # empty subdir

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert ISSUE_EMPTY_SUBDIR in item.issues

    def test_movie_with_junk_files(self, tmp_path: Path) -> None:
        """Movie with .DS_Store should flag junk."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / ".DS_Store").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert ISSUE_JUNK_FILES in item.issues

    def test_movie_bad_dir_name(self, tmp_path: Path) -> None:
        """Movie without (Year) in name should flag bad naming."""
        movie = tmp_path / "Some Movie"
        movie.mkdir()
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert item.year is None
        assert ISSUE_BAD_DIR_NAME in item.issues

    def test_folder_size_calculated(self, tmp_path: Path) -> None:
        """Folder size should sum all files recursively."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1024 * 1024)  # 1 MB

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        # ~1 MB = ~0.001 GB, should be > 0
        assert item.folder_size_gb > 0


class TestScanTvshowDir:
    """Tests for scan_tvshow_dir — single TV show directory scanning."""

    def test_complete_show(self, tmp_path: Path) -> None:
        """Show with NFO, poster, seasons, episodes."""
        show = tmp_path / "Fallout (2024)"
        show.mkdir()
        (show / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">106379</uniqueid></tvshow>'
        )
        (show / "poster.jpg").write_bytes(b"\x00")
        (show / "landscape.jpg").write_bytes(b"\x00")

        s01 = show / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - The Beginning.mkv").write_bytes(b"\x00" * 1000)
        (s01 / "S01E01 - The Beginning.nfo").write_text("<episodedetails/>")
        (show / "season01-poster.jpg").write_bytes(b"\x00")

        item = scan_tvshow_dir(show, disk="Disk1", category="series")

        assert item.title == "Fallout"
        assert item.year == 2024
        assert item.media_type == "tvshow"
        assert item.nfo.valid is True
        assert item.artwork.poster is True
        assert len(item.seasons) == 1
        assert item.seasons[0].number == 1
        assert item.seasons[0].episode_count == 1
        assert item.seasons[0].has_poster is True
        assert item.seasons[0].episodes_with_nfo == 1

    def test_show_multiple_seasons(self, tmp_path: Path) -> None:
        """Show with 2 seasons."""
        show = tmp_path / "Show (2020)"
        show.mkdir()
        (show / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>'
        )
        (show / "poster.jpg").write_bytes(b"\x00")

        for sn in (1, 2):
            s = show / f"Saison 0{sn}"
            s.mkdir()
            for ep in range(1, 4):
                (s / f"S0{sn}E0{ep} - Ep.mkv").write_bytes(b"\x00" * 100)

        item = scan_tvshow_dir(show, disk="Disk2", category="series")

        assert len(item.seasons) == 2
        assert item.seasons[0].episode_count == 3
        assert item.seasons[1].episode_count == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_scanner.py -v`
Expected: FAIL — `scan_movie_dir` not defined

- [ ] **Step 3: Implement scan_movie_dir and scan_tvshow_dir**

```python
# personalscraper/library/scanner.py
"""Lightweight library scanner — structure, NFO, artwork inventory.

Scans storage disks without ffprobe. Produces LibraryScanItem for each
media directory found. Uses existing utilities: is_nfo_complete(),
PATTERNS, SEASON_DIR_RE, _parse_folder_name().
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

from personalscraper.library.models import (
    ArtworkStatus,
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
    ISSUE_NTFS_UNSAFE,
    ISSUE_RELEASE_ARTIFACT,
    LibraryScanItem,
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
_JUNK_FILES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})

# Video extensions (same set as sorter/file_type.py)
_VIDEO_EXTENSIONS = frozenset({
    "mp4", "mkv", "avi", "mov", "wmv", "flv", "mpg", "mpeg",
    "m4v", "webm", "ts", "m2ts", "mts", "3gp", "vob", "ogv", "rmvb",
})


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
) -> tuple[list[str], bool]:
    """Detect common issues in a media directory.

    Args:
        media_dir: Path to media directory.
        title: Parsed title.
        year: Parsed year (None if missing).
        is_tvshow: Whether this is a TV show.

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

        # Junk files
        if name in _JUNK_FILES:
            issues.append(ISSUE_JUNK_FILES)
            continue

        # Empty subdirectories (skip season dirs for tvshows)
        if item.is_dir() and not any(item.iterdir()):
            if is_tvshow and SEASON_DIR_RE.match(name):
                issues.append(ISSUE_EMPTY_SUBDIR)
            elif not is_tvshow:
                issues.append(ISSUE_EMPTY_SUBDIR)
            elif is_tvshow and not SEASON_DIR_RE.match(name):
                # Non-season empty dir in a tvshow (release artifact)
                issues.append(ISSUE_RELEASE_ARTIFACT)

        # NTFS-unsafe names
        if _NTFS_ILLEGAL.search(name):
            issues.append(ISSUE_NTFS_UNSAFE)

    # Bad directory naming (no year)
    if year is None:
        issues.append(ISSUE_BAD_DIR_NAME)

    # Deduplicate (e.g. multiple junk files → one issue)
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
    issues, actors_dir = _detect_issues(movie_dir, title, year, is_tvshow=False)
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
    issues, actors_dir = _detect_issues(show_dir, title, year, is_tvshow=True)
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_scanner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add personalscraper/library/scanner.py tests/library/test_scanner.py
git commit -m "v14.2.1: Implement scan_movie_dir and scan_tvshow_dir"
```

---

## Task 2: Implement full disk scanning with filters

**Files:**

- Modify: `personalscraper/library/scanner.py`
- Modify: `tests/library/test_scanner.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/library/test_scanner.py`:

```python
from unittest.mock import MagicMock

from personalscraper.library.models import LibraryScanResult
from personalscraper.library.scanner import scan_library


class TestScanLibrary:
    """Tests for scan_library — full disk scanning."""

    def _make_disk_config(self, path: Path, name: str, categories: list[str]):
        """Create a mock DiskConfig."""
        config = MagicMock()
        config.path = path
        config.name = name
        config.categories = categories
        return config

    def test_scan_single_disk(self, tmp_path: Path) -> None:
        """Scan a single disk with one movie."""
        disk = tmp_path / "medias"
        films = disk / "films"
        films.mkdir(parents=True)
        movie = films / "Test (2024)"
        movie.mkdir()
        (movie / "Test.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Test.nfo").write_text(
            '<movie><uniqueid type="tmdb">1</uniqueid></movie>'
        )

        config = self._make_disk_config(disk, "Disk1", ["films"])
        result = scan_library([config])

        assert isinstance(result, LibraryScanResult)
        assert result.item_count == 1
        assert result.items[0].title == "Test"
        assert result.items[0].disk == "Disk1"

    def test_disk_filter(self, tmp_path: Path) -> None:
        """--disk filter should only scan the specified disk."""
        disk1 = tmp_path / "disk1" / "medias"
        disk2 = tmp_path / "disk2" / "medias"
        (disk1 / "films" / "A (2024)").mkdir(parents=True)
        (disk2 / "films" / "B (2024)").mkdir(parents=True)
        (disk1 / "films" / "A (2024)" / "a.mkv").write_bytes(b"\x00")
        (disk2 / "films" / "B (2024)" / "b.mkv").write_bytes(b"\x00")

        configs = [
            self._make_disk_config(disk1, "Disk1", ["films"]),
            self._make_disk_config(disk2, "Disk2", ["films"]),
        ]
        result = scan_library(configs, disk_filter="Disk1")

        assert result.item_count == 1
        assert result.items[0].disk == "Disk1"
        assert result.disk_filter == "Disk1"

    def test_category_filter(self, tmp_path: Path) -> None:
        """--category filter should only scan the specified category."""
        disk = tmp_path / "medias"
        (disk / "films" / "Movie (2024)").mkdir(parents=True)
        (disk / "series" / "Show (2024)").mkdir(parents=True)
        (disk / "films" / "Movie (2024)" / "m.mkv").write_bytes(b"\x00")
        (disk / "series" / "Show (2024)" / "s.mkv").write_bytes(b"\x00")

        config = self._make_disk_config(disk, "Disk1", ["films", "series"])
        result = scan_library([config], category_filter="films")

        assert result.item_count == 1
        assert result.items[0].category == "films"
        assert result.category_filter == "films"

    def test_unmounted_disk_skipped(self, tmp_path: Path) -> None:
        """Unmounted disk (path doesn't exist) should be skipped."""
        config = self._make_disk_config(
            tmp_path / "nonexistent", "Disk3", ["films"],
        )
        result = scan_library([config])

        assert result.item_count == 0

    def test_series_categories_scanned_as_tvshow(self, tmp_path: Path) -> None:
        """Items in series categories should be scanned as tvshows."""
        disk = tmp_path / "medias"
        show = disk / "series" / "Show (2024)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>'
        )
        s01 = show / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - Ep.mkv").write_bytes(b"\x00" * 100)

        config = self._make_disk_config(disk, "Disk1", ["series"])
        result = scan_library([config])

        assert result.items[0].media_type == "tvshow"
        assert result.items[0].seasons is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/library/test_scanner.py::TestScanLibrary -v`
Expected: FAIL — `scan_library` not defined

- [ ] **Step 3: Implement scan_library**

Add to `personalscraper/library/scanner.py`:

```python
# Categories that contain TV shows (matching dispatch/media_index.py convention)
_SERIES_CATEGORIES = frozenset({
    "series", "series animations", "series documentaires",
    "series animes", "emissions",
})


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
    from personalscraper.library.models import LibraryScanResult

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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/library/test_scanner.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/library/scanner.py tests/library/test_scanner.py
git commit -m "v14.2.2: Implement scan_library with disk/category filters"
```

---

## Task 3: Add library-scan CLI command

**Files:**

- Modify: `personalscraper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_cli.py`:

```python
class TestLibraryScan:
    """Tests for library-scan CLI command."""

    def test_help(self, runner) -> None:
        """library-scan --help should display usage."""
        result = runner.invoke(app, ["library-scan", "--help"])
        assert result.exit_code == 0
        assert "library-scan" in result.output
        assert "--disk" in result.output
        assert "--category" in result.output

    def test_scan_produces_json(self, runner, tmp_path, monkeypatch) -> None:
        """library-scan should produce library_scan.json."""
        from unittest.mock import patch, MagicMock
        from personalscraper.library.models import LibraryScanResult

        mock_result = LibraryScanResult(
            scanned_at="2026-04-15T12:00:00",
            disk_filter=None, category_filter=None,
            item_count=0, items=[],
        )

        with (
            patch("personalscraper.cli.get_settings") as mock_settings,
            patch("personalscraper.cli.scan_library", return_value=mock_result),
            patch("personalscraper.cli.write_json") as mock_write,
        ):
            settings = MagicMock()
            settings.disk_configs = []
            settings.data_dir = tmp_path
            mock_settings.return_value = settings

            result = runner.invoke(app, ["library-scan"])

        assert result.exit_code == 0
        mock_write.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py::TestLibraryScan -v`
Expected: FAIL — command not registered

- [ ] **Step 3: Add library-scan command to cli.py**

Add to `personalscraper/cli.py`, after the existing commands:

```python
@app.command()
@handle_cli_errors
def library_scan(
    disk: str = typer.Option(None, "--disk", help="Scan only this disk (Disk1-4)"),
    category: str = typer.Option(None, "--category", help="Scan only this category (disk category name)"),
) -> None:
    """Scan library structure and metadata on storage disks.

    Lightweight scan: reads directories and NFOs, no ffprobe.
    Produces library_scan.json in .personalscraper/.

    Examples:
        personalscraper library-scan
        personalscraper library-scan --disk Disk1
        personalscraper library-scan --category films
    """
    from personalscraper.library.models import write_json
    from personalscraper.library.scanner import scan_library

    console = state["console"]
    settings = get_settings()

    console.print("[bold]Scanning library...[/bold]")
    result = scan_library(
        settings.disk_configs,
        disk_filter=disk,
        category_filter=category,
    )

    output_path = settings.data_dir / "library_scan.json"
    write_json(result, output_path)

    console.print(
        f"[green]Scan complete:[/green] {result.item_count} items → {output_path}"
    )
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/test_cli.py::TestLibraryScan -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add personalscraper/cli.py tests/test_cli.py
git commit -m "v14.2.3: Add library-scan CLI command"
```

---

## Acceptance Criteria — Phase 2

Before moving to Phase 3, verify:

- [ ] `personalscraper library-scan --help` displays usage with `--disk` and `--category` options
- [ ] `scan_movie_dir` detects NFO, artwork, .actors, empty dirs, junk, bad naming
- [ ] `scan_tvshow_dir` scans seasons with episode counts and poster detection
- [ ] `scan_library` filters by disk and category, skips unmounted disks
- [ ] `library_scan.json` is written atomically to `.personalscraper/`
- [ ] Full test suite passes: `python -m pytest tests/ -x -q`
