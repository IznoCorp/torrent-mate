"""Tests for personalscraper.library.scanner — lightweight disk scanner."""

from pathlib import Path
from unittest.mock import MagicMock

from personalscraper.library.models import (
    ISSUE_ACTORS_DIR,
    ISSUE_BAD_DIR_NAME,
    ISSUE_EMPTY_SUBDIR,
    ISSUE_JUNK_FILES,
    LibraryScanResult,
)
from personalscraper.library.scanner import (
    scan_library,
    scan_movie_dir,
    scan_tvshow_dir,
)


class TestScanMovieDir:
    """Tests for scan_movie_dir — single movie directory scanning."""

    def test_complete_movie(self, tmp_path: Path) -> None:
        """Movie with NFO, poster, landscape should have no issues."""
        movie = tmp_path / "The Matrix (1999)"
        movie.mkdir()
        (movie / "The Matrix.mkv").write_bytes(b"\x00" * 1000)
        (movie / "The Matrix.nfo").write_text('<movie><uniqueid type="tmdb">603</uniqueid></movie>')
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
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
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

    def test_macos_resource_forks_flagged(self, tmp_path: Path) -> None:
        """MacOS resource fork files (._*) should be flagged as junk."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert ISSUE_JUNK_FILES in item.issues

    def test_audiobook_no_year_not_flagged(self, tmp_path: Path) -> None:
        """Audiobooks by author name (no year) should NOT flag bad_dir_naming."""
        book = tmp_path / "Isaac Asimov"
        book.mkdir()
        (book / "Foundation.mp3").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(book, disk="Disk1", category="livres audios")

        assert item.year is None
        assert ISSUE_BAD_DIR_NAME not in item.issues

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
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">106379</uniqueid></tvshow>')
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
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
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
        (movie / "Test.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')

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
            tmp_path / "nonexistent",
            "Disk3",
            ["films"],
        )
        result = scan_library([config])

        assert result.item_count == 0

    def test_series_categories_scanned_as_tvshow(self, tmp_path: Path) -> None:
        """Items in series categories should be scanned as tvshows."""
        disk = tmp_path / "medias"
        show = disk / "series" / "Show (2024)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        s01 = show / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - Ep.mkv").write_bytes(b"\x00" * 100)

        config = self._make_disk_config(disk, "Disk1", ["series"])
        result = scan_library([config])

        assert result.items[0].media_type == "tvshow"
        assert result.items[0].seasons is not None


class TestParseTitleYear:
    """Direct tests for parse_title_year public API."""

    def test_title_with_year(self) -> None:
        """Standard 'Title (2024)' format."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("The Matrix (1999)")
        assert title == "The Matrix"
        assert year == 1999

    def test_title_without_year(self) -> None:
        """No year in parentheses returns None."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("Some Movie")
        assert title == "Some Movie"
        assert year is None

    def test_title_with_spaces(self) -> None:
        """Extra spaces around year should be handled."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("Movie  (2024) ")
        assert title == "Movie"
        assert year == 2024

    def test_title_with_non_year_parens(self) -> None:
        """Non-4-digit parens should not match."""
        from personalscraper.library.scanner import parse_title_year

        title, year = parse_title_year("Movie (Extended)")
        assert year is None


class TestExtractNfoIds:
    """Direct tests for extract_nfo_ids public API."""

    def test_both_ids(self, tmp_path: Path) -> None:
        """NFO with both TMDB and IMDB IDs."""
        from personalscraper.library.scanner import extract_nfo_ids

        nfo = tmp_path / "test.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb">603</uniqueid><uniqueid type="imdb">tt0133093</uniqueid></movie>')
        tmdb, imdb = extract_nfo_ids(nfo)
        assert tmdb == "603"
        assert imdb == "tt0133093"

    def test_empty_uniqueid_text(self, tmp_path: Path) -> None:
        """NFO with empty uniqueid text should return None."""
        from personalscraper.library.scanner import extract_nfo_ids

        nfo = tmp_path / "test.nfo"
        nfo.write_text('<movie><uniqueid type="tmdb"></uniqueid></movie>')
        tmdb, imdb = extract_nfo_ids(nfo)
        assert tmdb is None
        assert imdb is None

    def test_corrupt_xml(self, tmp_path: Path) -> None:
        """Corrupt XML should return (None, None)."""
        from personalscraper.library.scanner import extract_nfo_ids

        nfo = tmp_path / "test.nfo"
        nfo.write_text("<movie><broken")
        tmdb, imdb = extract_nfo_ids(nfo)
        assert tmdb is None
        assert imdb is None

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Missing file should return (None, None)."""
        from personalscraper.library.scanner import extract_nfo_ids

        tmdb, imdb = extract_nfo_ids(tmp_path / "missing.nfo")
        assert tmdb is None
        assert imdb is None


class TestNtfsUnsafeDetection:
    """Tests for NTFS-unsafe name detection in scanner."""

    def test_ntfs_unsafe_filename_flagged(self, tmp_path: Path) -> None:
        """File with NTFS-illegal ':' should flag ISSUE_NTFS_UNSAFE."""
        from personalscraper.library.models import ISSUE_NTFS_UNSAFE

        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        # Create file with colon (common in TMDB French titles)
        (movie / "Spirale : L'Héritage.txt").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk="Disk1", category="films")

        assert ISSUE_NTFS_UNSAFE in item.issues
