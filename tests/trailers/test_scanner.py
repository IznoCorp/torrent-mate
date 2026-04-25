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


# ---------------------------------------------------------------------------
# Edge-case and library-scan coverage
# ---------------------------------------------------------------------------


class TestScanStagingEdgeCases:
    """Edge-case tests for Scanner.scan_staging() to cover missing-dir and hidden dirs."""

    def test_missing_staging_dir_returns_empty_list(self, tmp_path: "Path") -> None:
        """scan_staging returns [] and logs a warning when staging_dir does not exist."""
        missing = tmp_path / "does_not_exist"
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(missing)
        assert items == []

    def test_hidden_category_dir_is_skipped(self, tmp_path: "Path") -> None:
        """Directories starting with "." inside staging are silently skipped."""
        hidden = tmp_path / ".hidden_category"
        hidden.mkdir()
        movie_dir = hidden / "Some Movie (2020)"
        movie_dir.mkdir()
        (movie_dir / "Some Movie.nfo").write_text(
            '<movie><title>Some Movie</title><uniqueid type="tmdb">9999</uniqueid></movie>',
            encoding="utf-8",
        )
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_hidden_media_dir_is_skipped(self, tmp_path: "Path") -> None:
        """Media directories starting with "." are silently skipped."""
        cat = tmp_path / "001-MOVIES"
        cat.mkdir()
        hidden_media = cat / ".hidden_movie"
        hidden_media.mkdir()
        (hidden_media / "title.nfo").write_text(
            '<movie><title>Title</title></movie>', encoding="utf-8"
        )
        scanner = Scanner(min_file_size_bytes=102400)
        items = scanner.scan_staging(tmp_path)
        assert items == []

    def test_season_with_existing_trailer_is_skipped(self, tmp_path: "Path") -> None:
        """scan_staging skips season whose trailer file already exists and is large enough."""
        tvshows_dir = tmp_path / "002-TVSHOWS"
        tvshows_dir.mkdir()
        show_dir = _make_tvshow_dir(tvshows_dir, "Breaking Bad (2008)", with_trailer=False)
        saison_dir = show_dir / "Saison 01"
        saison_dir.mkdir()
        trailer_file = show_dir / "Saison 01" / "Breaking Bad (2008) - Saison 01-trailer.mp4"
        trailer_file.write_bytes(b"x" * 200000)

        scanner = Scanner(min_file_size_bytes=102400, seasons_enabled=True)
        items = scanner.scan_staging(tmp_path)
        season_items = [i for i in items if i.season_number is not None]
        assert season_items == [], f"Expected no season items but got {season_items}"


class TestScanLibrary:
    """Tests for Scanner.scan_library() -- uses mocked library.scanner.scan_library()."""

    def test_scan_library_returns_items_missing_trailers(self, tmp_path: "Path") -> None:
        """scan_library returns ScanItems for library entries without trailers."""
        from unittest.mock import MagicMock, patch

        from personalscraper.library.models import ArtworkStatus, LibraryScanItem, LibraryScanResult, NfoStatus

        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()

        fake_item = LibraryScanItem(
            path=str(movie_dir),
            disk="disk_1",
            category="movies",
            media_type="movie",
            title="Fight Club",
            year=1999,
            folder_size_gb=4.2,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="550", imdb_id="tt0137523"),
            artwork=ArtworkStatus(
                poster=True, fanart=True, landscape=False, banner=False,
                clearlogo=False, clearart=False, discart=False,
            ),
            actors_dir=False,
        )
        fake_result = LibraryScanResult(
            scanned_at="2026-01-01T00:00:00Z", disk_filter=None, category_filter=None,
            item_count=1, items=[fake_item],
        )

        config = MagicMock()
        config.disks = []
        config.trailers.library_scan_max_age_hours = 24

        with patch("personalscraper.trailers.scanner._lib_scan", return_value=fake_result):
            scanner = Scanner(min_file_size_bytes=102400)
            items = scanner.scan_library(config)

        assert len(items) == 1
        assert items[0].title == "Fight Club"
        assert items[0].tmdb_id == "550"

    def test_scan_library_skips_item_with_existing_trailer(self, tmp_path: "Path") -> None:
        """scan_library skips library items whose trailer file already exists."""
        from unittest.mock import MagicMock, patch

        from personalscraper.library.models import ArtworkStatus, LibraryScanItem, LibraryScanResult, NfoStatus

        movie_dir = tmp_path / "Fight Club (1999)"
        movie_dir.mkdir()
        (movie_dir / "Fight Club (1999)-trailer.mp4").write_bytes(b"x" * 200000)

        fake_item = LibraryScanItem(
            path=str(movie_dir), disk="disk_1", category="movies", media_type="movie",
            title="Fight Club", year=1999, folder_size_gb=4.2,
            nfo=NfoStatus(present=True, valid=True, tmdb_id="550", imdb_id=None),
            artwork=ArtworkStatus(
                poster=True, fanart=True, landscape=False, banner=False,
                clearlogo=False, clearart=False, discart=False,
            ),
            actors_dir=False,
        )
        fake_result = LibraryScanResult(
            scanned_at="2026-01-01T00:00:00Z", disk_filter=None, category_filter=None,
            item_count=1, items=[fake_item],
        )

        config = MagicMock()
        config.disks = []
        config.trailers.library_scan_max_age_hours = 24

        with patch("personalscraper.trailers.scanner._lib_scan", return_value=fake_result):
            scanner = Scanner(min_file_size_bytes=102400)
            items = scanner.scan_library(config)

        assert items == []

    def test_scan_library_fresh_cache_returns_empty(self, tmp_path: "Path") -> None:
        """scan_library returns [] without calling _lib_scan when cache is still fresh."""
        from datetime import datetime, timezone
        from unittest.mock import MagicMock, patch

        config = MagicMock()
        config.disks = []
        config.trailers.library_scan_max_age_hours = 24

        scanner = Scanner(min_file_size_bytes=102400)
        scanner._last_scan_time = datetime.now(tz=timezone.utc)

        with patch("personalscraper.trailers.scanner._lib_scan") as mock_lib:
            items = scanner.scan_library(config)
            mock_lib.assert_not_called()

        assert items == []

    def test_scan_library_force_refresh_bypasses_cache(self, tmp_path: "Path") -> None:
        """force_refresh=True bypasses freshness check and always rescans."""
        from datetime import datetime, timezone
        from unittest.mock import MagicMock, patch

        from personalscraper.library.models import LibraryScanResult

        config = MagicMock()
        config.disks = []
        config.trailers.library_scan_max_age_hours = 24

        empty_result = LibraryScanResult(
            scanned_at="2026-01-01T00:00:00Z", disk_filter=None, category_filter=None,
            item_count=0, items=[],
        )

        scanner = Scanner(min_file_size_bytes=102400)
        scanner._last_scan_time = datetime.now(tz=timezone.utc)

        with patch("personalscraper.trailers.scanner._lib_scan", return_value=empty_result) as mock_lib:
            items = scanner.scan_library(config, force_refresh=True)
            mock_lib.assert_called_once()

        assert items == []

    def test_scan_library_missing_trailers_config_uses_default(self, tmp_path: "Path") -> None:
        """AttributeError on config.trailers falls back to default max_age_hours=24."""
        from unittest.mock import MagicMock, patch

        from personalscraper.library.models import LibraryScanResult

        config = MagicMock(spec=["disks"])
        config.disks = []

        empty_result = LibraryScanResult(
            scanned_at="2026-01-01T00:00:00Z", disk_filter=None, category_filter=None,
            item_count=0, items=[],
        )

        with patch("personalscraper.trailers.scanner._lib_scan", return_value=empty_result):
            scanner = Scanner(min_file_size_bytes=102400)
            items = scanner.scan_library(config)

        assert items == []
