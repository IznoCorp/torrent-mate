"""Tests for personalscraper.library.scanner — lightweight disk scanner."""

from pathlib import Path

import pytest

from personalscraper.conf import ids as CID
from personalscraper.conf.models import CategoryConfig, Config, DiskConfig, PathConfig
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
from tests.fixtures.config import CANONICAL_STAGING_DIRS

# ---------------------------------------------------------------------------
# Minimal Config fixture for scanner tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def scanner_config(tmp_path: Path) -> Config:
    """Minimal Config for scanner unit tests.

    Two disks: drive_a (movies, tv_shows, audiobooks) and drive_b (tv_shows_animation).
    Folder names follow the default_label pattern: "movies", "tv shows", etc.
    """
    return Config(
        paths=PathConfig(
            torrent_complete_dir=tmp_path / "torrents",
            staging_dir=tmp_path / "staging",
            data_dir=tmp_path / ".data",
        ),
        disks=[
            DiskConfig(
                id="drive_a",
                path=tmp_path / "drive_a",
                categories=[CID.MOVIES, CID.TV_SHOWS, CID.AUDIOBOOKS],
            ),
            DiskConfig(
                id="drive_b",
                path=tmp_path / "drive_b",
                categories=[CID.TV_SHOWS_ANIMATION],
            ),
        ],
        categories={
            CID.MOVIES: CategoryConfig(folder_name="films"),
            CID.TV_SHOWS: CategoryConfig(folder_name="series"),
            CID.AUDIOBOOKS: CategoryConfig(folder_name="livres audios"),
            CID.TV_SHOWS_ANIMATION: CategoryConfig(folder_name="series animations"),
        },
        staging_dirs=CANONICAL_STAGING_DIRS,
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

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.title == "The Matrix"
        assert item.year == 1999
        assert item.nfo.present is True
        assert item.nfo.valid is True
        assert item.nfo.tmdb_id == "603"
        assert item.artwork.poster is True
        assert item.artwork.landscape is True
        assert item.issues == []
        assert item.seasons is None
        assert item.category == CID.MOVIES

    def test_movie_with_actors_dir(self, tmp_path: Path) -> None:
        """Movie with .actors/ should flag ISSUE_ACTORS_DIR."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Movie.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')
        (movie / ".actors").mkdir()
        (movie / ".actors" / "Actor.jpg").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.actors_dir is True
        assert ISSUE_ACTORS_DIR in item.issues

    def test_movie_missing_nfo(self, tmp_path: Path) -> None:
        """Movie without NFO should report nfo.present=False."""
        movie = tmp_path / "NoNfo (2024)"
        movie.mkdir()
        (movie / "NoNfo.mkv").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.nfo.present is False
        assert item.nfo.valid is False

    def test_movie_with_empty_subdir(self, tmp_path: Path) -> None:
        """Movie with empty subdirectory should flag it."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Subs").mkdir()  # empty subdir

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_EMPTY_SUBDIR in item.issues

    def test_movie_with_junk_files(self, tmp_path: Path) -> None:
        """Movie with .DS_Store should flag junk."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / ".DS_Store").write_bytes(b"\x00")

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_JUNK_FILES in item.issues

    def test_movie_bad_dir_name(self, tmp_path: Path) -> None:
        """Movie without (Year) in name should flag bad naming."""
        movie = tmp_path / "Some Movie"
        movie.mkdir()
        (movie / "movie.mkv").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert item.year is None
        assert ISSUE_BAD_DIR_NAME in item.issues

    def test_macos_resource_forks_flagged(self, tmp_path: Path) -> None:
        """MacOS resource fork files (._*) should be flagged as junk."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie / "._Movie.mkv").write_bytes(b"\x00" * 100)

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_JUNK_FILES in item.issues

    def test_audiobook_no_year_not_flagged(self, tmp_path: Path) -> None:
        """Audiobooks by author name (no year) should NOT flag bad_dir_naming."""
        book = tmp_path / "Isaac Asimov"
        book.mkdir()
        (book / "Foundation.mp3").write_bytes(b"\x00" * 1000)

        item = scan_movie_dir(book, disk_id="drive_a", category_id=CID.AUDIOBOOKS)

        assert item.year is None
        assert ISSUE_BAD_DIR_NAME not in item.issues

    def test_folder_size_calculated(self, tmp_path: Path) -> None:
        """Folder size should sum all files recursively."""
        movie = tmp_path / "Movie (2024)"
        movie.mkdir()
        (movie / "Movie.mkv").write_bytes(b"\x00" * 1024 * 1024)  # 1 MB

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

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

        item = scan_tvshow_dir(show, disk_id="drive_a", category_id=CID.TV_SHOWS)

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
        assert item.category == CID.TV_SHOWS

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

        item = scan_tvshow_dir(show, disk_id="drive_a", category_id=CID.TV_SHOWS)

        assert len(item.seasons) == 2
        assert item.seasons[0].episode_count == 3
        assert item.seasons[1].episode_count == 3


class TestScanLibrary:
    """Tests for scan_library — full disk scanning with Config."""

    def test_scan_single_disk(self, tmp_path: Path, scanner_config: Config) -> None:
        """Scan a single disk with one movie — produces LibraryScanResult with category_id."""
        disk_a = scanner_config.disks[0].path
        films = disk_a / "films"
        films.mkdir(parents=True)
        movie = films / "Test (2024)"
        movie.mkdir()
        (movie / "Test.mkv").write_bytes(b"\x00" * 1000)
        (movie / "Test.nfo").write_text('<movie><uniqueid type="tmdb">1</uniqueid></movie>')

        result = scan_library(scanner_config.disks, config=scanner_config)

        assert isinstance(result, LibraryScanResult)
        assert result.item_count == 1
        assert result.items[0].title == "Test"
        assert result.items[0].disk == "drive_a"
        assert result.items[0].category == CID.MOVIES

    def test_disk_filter(self, tmp_path: Path, scanner_config: Config) -> None:
        """disk_filter should only scan the specified disk by disk.id."""
        disk_a = scanner_config.disks[0].path
        disk_b = scanner_config.disks[1].path
        (disk_a / "films").mkdir(parents=True)
        (disk_b / "series animations").mkdir(parents=True)
        (disk_a / "films" / "A (2024)").mkdir()
        (disk_a / "films" / "A (2024)" / "a.mkv").write_bytes(b"\x00")
        (disk_b / "series animations" / "Anime (2024)").mkdir()
        (disk_b / "series animations" / "Anime (2024)" / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>'
        )

        result = scan_library(scanner_config.disks, config=scanner_config, disk_filter="drive_a")

        assert result.item_count == 1
        assert result.items[0].disk == "drive_a"
        assert result.disk_filter == "drive_a"

    def test_category_filter(self, tmp_path: Path, scanner_config: Config) -> None:
        """category_filter should only scan the specified category_id."""
        disk_a = scanner_config.disks[0].path
        (disk_a / "films").mkdir(parents=True)
        (disk_a / "series").mkdir(parents=True)
        (disk_a / "films" / "Movie (2024)").mkdir()
        (disk_a / "films" / "Movie (2024)" / "m.mkv").write_bytes(b"\x00")
        (disk_a / "series" / "Show (2024)").mkdir()
        (disk_a / "series" / "Show (2024)" / "tvshow.nfo").write_text(
            '<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>'
        )

        result = scan_library(
            scanner_config.disks,
            config=scanner_config,
            category_filter=CID.MOVIES,
        )

        assert result.item_count == 1
        assert result.items[0].category == CID.MOVIES
        assert result.category_filter == CID.MOVIES

    def test_unmounted_disk_skipped(self, tmp_path: Path, scanner_config: Config) -> None:
        """Unmounted disk (path doesn't exist) should be skipped."""
        # drive_a and drive_b paths do not exist (not mkdir'd)
        result = scan_library(scanner_config.disks, config=scanner_config)

        assert result.item_count == 0

    def test_tv_categories_scanned_as_tvshow(self, tmp_path: Path, scanner_config: Config) -> None:
        """Items in TV category IDs should be scanned as tvshows."""
        disk_a = scanner_config.disks[0].path
        show = disk_a / "series" / "Show (2024)"
        show.mkdir(parents=True)
        (show / "tvshow.nfo").write_text('<tvshow><uniqueid type="tmdb">1</uniqueid></tvshow>')
        s01 = show / "Saison 01"
        s01.mkdir()
        (s01 / "S01E01 - Ep.mkv").write_bytes(b"\x00" * 100)

        result = scan_library(scanner_config.disks, config=scanner_config, category_filter=CID.TV_SHOWS)

        assert result.item_count == 1
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

        item = scan_movie_dir(movie, disk_id="drive_a", category_id=CID.MOVIES)

        assert ISSUE_NTFS_UNSAFE in item.issues
