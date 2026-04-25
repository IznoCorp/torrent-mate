"""Unit tests for trailers/scanner.py -- media-without-trailer detection.

Uses tmpdir fixtures to build fake media trees (movies and TV shows with/without
trailers). Library scanning path uses mocked library.scanner.scan_library().
"""

from pathlib import Path

from personalscraper.trailers.scanner import Scanner

# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------


def _make_movie_dir(parent: Path, name: str, with_trailer: bool = False) -> Path:
    """Create a fake movie directory with a minimal NFO.

    Args:
        parent: Parent directory to create the movie dir in.
        name: Directory name (e.g. "Fight Club (1999)").
        with_trailer: Whether to place a valid-size trailer file.

    Returns:
        Path to the created movie directory.
    """
    d = parent / name
    d.mkdir(parents=True)
    title = name.split("(")[0].strip()
    nfo = d / f"{title}.nfo"
    nfo.write_text(
        f'<movie><title>{title}</title><uniqueid type="tmdb">550</uniqueid></movie>',
        encoding="utf-8",
    )
    if with_trailer:
        (d / f"{name}-trailer.mp4").write_bytes(b"x" * 200000)
    return d


def _make_tvshow_dir(parent: Path, name: str, with_trailer: bool = False) -> Path:
    """Create a fake TV show directory with tvshow.nfo.

    Args:
        parent: Parent directory to create the show dir in.
        name: Directory name (e.g. "Breaking Bad (2008)").
        with_trailer: Whether to place a valid-size trailer file at show root.

    Returns:
        Path to the created TV show directory.
    """
    d = parent / name
    d.mkdir(parents=True)
    nfo = d / "tvshow.nfo"
    nfo.write_text(
        '<tvshow><title>Breaking Bad</title><uniqueid type="tmdb">1396</uniqueid></tvshow>',
        encoding="utf-8",
    )
    if with_trailer:
        # Flat convention: {show_name}-trailer.mp4 at show root.
        (d / f"{name}-trailer.mp4").write_bytes(b"x" * 200000)
    return d


def _make_tvshow_with_seasons(parent: Path, name: str, season_count: int) -> Path:
    """Create a fake TV show directory with N Saison XX/ subfolders.

    No trailers are placed -- every season is missing its trailer file.

    Args:
        parent: Parent directory for the show directory.
        name: Directory name (e.g. "Breaking Bad (2008)").
        season_count: Number of Saison XX/ subdirectories to create.

    Returns:
        Path to the created TV show directory.
    """
    d = _make_tvshow_dir(parent, name, with_trailer=False)
    for n in range(1, season_count + 1):
        (d / f"Saison {n:02d}").mkdir()
    return d


# ---------------------------------------------------------------------------
# scan_staging
# ---------------------------------------------------------------------------


class TestScanStaging:
    """Tests for Scanner.scan_staging()."""

    def test_finds_movie_without_trailer(self, tmp_path: Path) -> None:
        """scan_staging returns a ScanItem for a movie missing its trailer."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].title == "Fight Club"

    def test_skips_movie_with_existing_trailer(self, tmp_path: Path) -> None:
        """scan_staging skips media whose trailer already exists and is large enough."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=True)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_finds_tvshow_without_trailer(self, tmp_path: Path) -> None:
        """scan_staging returns ScanItem for TV show missing its trailer."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_dir(tvshows_dir, "Breaking Bad (2008)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].media_type == "tvshow"

    def test_scan_item_has_tmdb_id(self, tmp_path: Path) -> None:
        """ScanItem.tmdb_id is populated from the NFO."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items[0].tmdb_id == "550"

    def test_empty_staging_returns_empty_list(self, tmp_path: Path) -> None:
        """scan_staging returns [] for an empty staging directory."""
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []


# ---------------------------------------------------------------------------
# ScanItem dataclass
# ---------------------------------------------------------------------------


class TestScanItem:
    """Tests for ScanItem field population."""

    def test_scan_item_fields(self, tmp_path: Path) -> None:
        """ScanItem carries path, media_type, title, year, tmdb_id."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        _make_movie_dir(movies_dir, "Fight Club (1999)", with_trailer=False)

        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        item = items[0]
        assert item.path.is_dir()
        assert item.media_type == "movie"
        assert item.title == "Fight Club"
        assert item.year == 1999


# ---------------------------------------------------------------------------
# Season-aware scanning
# ---------------------------------------------------------------------------


class TestSeasonAwareScanning:
    """Tests for opt-in season-level ScanItem emission."""

    def test_season_scanner_emits_one_item_per_saison_folder_when_enabled(self, tmp_path: Path) -> None:
        """With seasons_enabled=True, scan emits show-level item + one item per season."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_with_seasons(tvshows_dir, "Breaking Bad (2008)", season_count=3)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=True)
        items = scanner.scan_staging(tmp_path)
        # Show-level + 3 seasons = 4 items
        assert len(items) == 4
        season_numbers = sorted(i.season_number for i in items if i.season_number is not None)
        assert season_numbers == [1, 2, 3]
        # Exactly one show-level entry (season_number is None)
        assert sum(1 for i in items if i.season_number is None) == 1

    def test_season_scanner_skips_seasons_when_disabled(self, tmp_path: Path) -> None:
        """With seasons_enabled=False (default), only the show-level ScanItem is emitted."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        _make_tvshow_with_seasons(tvshows_dir, "Breaking Bad (2008)", season_count=3)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=False)
        items = scanner.scan_staging(tmp_path)
        assert len(items) == 1
        assert items[0].season_number is None
