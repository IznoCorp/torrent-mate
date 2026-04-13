"""Tests for the media directory checker.

Tests movie and TV show quality checks including video presence,
naming conventions, NFO validation, artwork, and categorization.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from personalscraper.genre_mapper import GenreMapper
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.verify.checker import MediaChecker, Severity


@pytest.fixture
def checker() -> MediaChecker:
    """Create a MediaChecker with default patterns and mapper."""
    return MediaChecker(NamingPatterns(), GenreMapper())


def _make_movie_dir(tmp_path: Path, title: str = "Fight Club", year: int = 1999) -> Path:
    """Create a valid movie directory with NFO and video."""
    name = f"{title} ({year})"
    d = tmp_path / name
    d.mkdir()
    # Video file
    video = d / f"{title}.mkv"
    video.write_bytes(b"\x00" * (200 * 1024 * 1024))  # 200 MB
    # NFO
    root = ET.Element("movie")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid_tmdb = ET.SubElement(root, "uniqueid")
    uid_tmdb.set("type", "tmdb")
    uid_tmdb.text = "550"
    uid_imdb = ET.SubElement(root, "uniqueid")
    uid_imdb.set("type", "imdb")
    uid_imdb.text = "tt0137523"
    ET.SubElement(root, "genre").text = "Drame"
    fileinfo = ET.SubElement(root, "fileinfo")
    ET.SubElement(ET.SubElement(fileinfo, "streamdetails"), "video")
    ET.ElementTree(root).write(d / f"{title}.nfo", encoding="unicode")
    # Artwork
    (d / f"{title}-poster.jpg").write_bytes(b"\xff")
    (d / f"{title}-landscape.jpg").write_bytes(b"\xff")
    return d


def _make_tvshow_dir(tmp_path: Path, title: str = "Fallout", year: int = 2024) -> Path:
    """Create a valid TV show directory with NFO, season, and episodes."""
    name = f"{title} ({year})"
    d = tmp_path / name
    d.mkdir()
    # tvshow.nfo
    root = ET.Element("tvshow")
    ET.SubElement(root, "title").text = title
    ET.SubElement(root, "year").text = str(year)
    uid_tmdb = ET.SubElement(root, "uniqueid")
    uid_tmdb.set("type", "tmdb")
    uid_tmdb.text = "106379"
    uid_tvdb = ET.SubElement(root, "uniqueid")
    uid_tvdb.set("type", "tvdb")
    uid_tvdb.text = "416744"
    ET.SubElement(root, "genre").text = "Action & Adventure"
    ET.ElementTree(root).write(d / "tvshow.nfo", encoding="unicode")
    # Artwork
    (d / "poster.jpg").write_bytes(b"\xff")
    (d / "landscape.jpg").write_bytes(b"\xff")
    (d / "season01-poster.jpg").write_bytes(b"\xff")
    # Season dir with episode
    season = d / "Saison 01"
    season.mkdir()
    (season / "S01E01 - La Fin.mkv").write_bytes(b"\x00" * 1024)
    # Episode NFO
    ep_root = ET.Element("episodedetails")
    ET.SubElement(ep_root, "title").text = "La Fin"
    ET.ElementTree(ep_root).write(season / "S01E01 - La Fin.nfo", encoding="unicode")
    return d


# ---------------------------------------------------------------------------
# Movie checks
# ---------------------------------------------------------------------------

class TestCheckMovieBase:
    """Tests for basic movie checks."""

    def test_valid_movie_all_pass(self, checker: MediaChecker, tmp_path: Path) -> None:
        """A valid movie should pass all checks."""
        d = _make_movie_dir(tmp_path)
        results = checker.check_movie(d)
        errors = [r for r in results if not r.passed and r.severity == Severity.ERROR]
        assert errors == [], f"Unexpected errors: {[r.message for r in errors]}"

    def test_no_video_file(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Should fail video_present check."""
        d = tmp_path / "Movie (2024)"
        d.mkdir()
        results = checker.check_movie(d)
        video_check = next(r for r in results if r.name == "video_present")
        assert not video_check.passed
        assert video_check.severity == Severity.ERROR

    def test_bad_dir_naming(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Should fail dir_naming for 'Movie' without year."""
        d = tmp_path / "Movie"
        d.mkdir()
        (d / "Movie.mkv").write_bytes(b"\x00" * 1024)
        results = checker.check_movie(d)
        naming = next(r for r in results if r.name == "dir_naming")
        assert not naming.passed
        assert naming.fixable

    def test_sample_warning(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Small video should trigger not_sample WARNING."""
        d = tmp_path / "Movie (2024)"
        d.mkdir()
        (d / "Movie.mkv").write_bytes(b"\x00" * 1024)  # 1 KB
        results = checker.check_movie(d)
        sample_check = next(r for r in results if r.name == "not_sample")
        assert not sample_check.passed
        assert sample_check.severity == Severity.WARNING


class TestCheckMovieNFO:
    """Tests for NFO-related movie checks."""

    def test_missing_nfo(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Should fail nfo_present if no NFO file."""
        d = tmp_path / "Movie (2024)"
        d.mkdir()
        (d / "Movie.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        results = checker.check_movie(d)
        nfo_check = next(r for r in results if r.name == "nfo_present")
        assert not nfo_check.passed

    def test_invalid_nfo_xml(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Should fail nfo_valid for malformed XML."""
        d = tmp_path / "Movie (2024)"
        d.mkdir()
        (d / "Movie.mkv").write_bytes(b"\x00" * (200 * 1024 * 1024))
        (d / "Movie.nfo").write_text("not xml <><<>")
        results = checker.check_movie(d)
        valid_check = next(r for r in results if r.name == "nfo_valid")
        assert not valid_check.passed


# ---------------------------------------------------------------------------
# TV show checks
# ---------------------------------------------------------------------------

class TestCheckTvshow:
    """Tests for TV show checks."""

    def test_valid_tvshow_no_errors(self, checker: MediaChecker, tmp_path: Path) -> None:
        """A valid TV show should have no ERROR-level failures."""
        d = _make_tvshow_dir(tmp_path)
        results = checker.check_tvshow(d)
        errors = [r for r in results if not r.passed and r.severity == Severity.ERROR]
        assert errors == [], f"Unexpected errors: {[r.message for r in errors]}"

    def test_missing_tvshow_nfo(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Should fail nfo_present if tvshow.nfo missing."""
        d = tmp_path / "Show (2024)"
        d.mkdir()
        season = d / "Saison 01"
        season.mkdir()
        (season / "S01E01 - Pilot.mkv").write_bytes(b"\x00" * 1024)
        results = checker.check_tvshow(d)
        nfo_check = next(r for r in results if r.name == "nfo_present")
        assert not nfo_check.passed

    def test_no_season_structure(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Should fail season_structure if no Saison XX/ dirs."""
        d = _make_tvshow_dir(tmp_path)
        # Remove the season dir contents
        import shutil
        shutil.rmtree(d / "Saison 01")
        results = checker.check_tvshow(d)
        season_check = next(r for r in results if r.name == "season_structure")
        assert not season_check.passed

    def test_missing_season_poster_warning(self, checker: MediaChecker, tmp_path: Path) -> None:
        """Missing season poster should be a WARNING."""
        d = _make_tvshow_dir(tmp_path)
        (d / "season01-poster.jpg").unlink()
        results = checker.check_tvshow(d)
        poster_checks = [r for r in results if r.name == "season_posters"]
        failed = [r for r in poster_checks if not r.passed]
        assert len(failed) >= 1
        assert failed[0].severity == Severity.WARNING


# ---------------------------------------------------------------------------
# NTFS-safe filename checks
# ---------------------------------------------------------------------------

class TestNtfsSafeNames:
    """Tests for NTFS-illegal character detection in verify checker."""

    def test_colon_in_artwork_fails_check(self, tmp_path: Path) -> None:
        """Artwork file with ':' should fail ntfs_safe_names check."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie.nfo").write_text("<movie><title>Movie</title></movie>")
        (movie_dir / "Movie-poster.jpg").write_bytes(b"poster")
        # This file has illegal ':' character
        (movie_dir / "Movie : Special-landscape.jpg").write_bytes(b"bad")

        from personalscraper.verify.checker import MediaChecker
        checker = MediaChecker(NamingPatterns(), GenreMapper())
        results = checker.check_movie(movie_dir)

        ntfs_check = next((r for r in results if r.name == "ntfs_safe_names"), None)
        assert ntfs_check is not None, "ntfs_safe_names check should exist"
        assert ntfs_check.passed is False
        assert ":" in ntfs_check.message

    def test_clean_names_pass_check(self, tmp_path: Path) -> None:
        """Files with NTFS-safe names should pass the check."""
        movie_dir = tmp_path / "Movie (2025)"
        movie_dir.mkdir()
        (movie_dir / "Movie.mkv").write_bytes(b"\x00" * 1000)
        (movie_dir / "Movie.nfo").write_text("<movie><title>Movie</title></movie>")
        (movie_dir / "Movie-poster.jpg").write_bytes(b"poster")

        from personalscraper.verify.checker import MediaChecker
        checker = MediaChecker(NamingPatterns(), GenreMapper())
        results = checker.check_movie(movie_dir)

        ntfs_check = next((r for r in results if r.name == "ntfs_safe_names"), None)
        assert ntfs_check is not None
        assert ntfs_check.passed is True

    def test_tvshow_with_colon_in_nfo_fails(self, tmp_path: Path) -> None:
        """TV show with ':' in a filename should also fail."""
        show_dir = tmp_path / "Show (2025)"
        show_dir.mkdir()
        (show_dir / "tvshow.nfo").write_text("<tvshow><title>Show</title></tvshow>")
        (show_dir / "poster.jpg").write_bytes(b"poster")
        season_dir = show_dir / "Saison 01"
        season_dir.mkdir()
        (season_dir / "S01E01 - Title.mkv").write_bytes(b"\x00" * 1000)
        # Illegal file
        (season_dir / "S01E01 : Title.nfo").write_bytes(b"bad_nfo")

        from personalscraper.verify.checker import MediaChecker
        checker = MediaChecker(NamingPatterns(), GenreMapper())
        results = checker.check_tvshow(show_dir)

        ntfs_check = next((r for r in results if r.name == "ntfs_safe_names"), None)
        assert ntfs_check is not None
        assert ntfs_check.passed is False
