"""Tests for the main scraping orchestrator.

Tests movie scraping flow including folder name parsing, NFO skip logic,
match integration, and batch processing. Uses mocked API clients and
filesystem operations.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper.confidence import MatchResult
from personalscraper.scraper.scraper import (
    Scraper,
    ScrapeResult,
    _find_video_file,
    _parse_folder_name,
)

# ---------------------------------------------------------------------------
# Folder name parsing
# ---------------------------------------------------------------------------

class TestParseFolderName:
    """Tests for _parse_folder_name."""

    def test_standard_format(self) -> None:
        """Should parse 'Title (Year)' format."""
        title, year = _parse_folder_name("The Matrix (1999)")
        assert title == "The Matrix"
        assert year == 1999

    def test_french_title(self) -> None:
        """Should handle French titles with accents."""
        title, year = _parse_folder_name("La Quête d'Ewilan (2026)")
        assert title == "La Quête d'Ewilan"
        assert year == 2026

    def test_no_year(self) -> None:
        """Should return None year for titles without year."""
        title, year = _parse_folder_name("Some Movie")
        assert title == "Some Movie"
        assert year is None

    def test_year_in_title(self) -> None:
        """Should handle year at end in parentheses."""
        title, year = _parse_folder_name("2001 A Space Odyssey (1968)")
        assert title == "2001 A Space Odyssey"
        assert year == 1968


# ---------------------------------------------------------------------------
# Video file finding
# ---------------------------------------------------------------------------

class TestFindVideoFile:
    """Tests for _find_video_file."""

    def test_finds_mkv(self, tmp_path: Path) -> None:
        """Should find .mkv files."""
        (tmp_path / "movie.mkv").write_text("video")
        (tmp_path / "movie.nfo").write_text("nfo")
        result = _find_video_file(tmp_path)
        assert result is not None
        assert result.name == "movie.mkv"

    def test_no_video(self, tmp_path: Path) -> None:
        """Should return None if no video files."""
        (tmp_path / "readme.txt").write_text("text")
        result = _find_video_file(tmp_path)
        assert result is None


# ---------------------------------------------------------------------------
# Movie scraping orchestration
# ---------------------------------------------------------------------------

class TestScrapeMovie:
    """Tests for Scraper.scrape_movie."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked API clients."""
        with patch("personalscraper.scraper.scraper.TMDBClient"):
            s = Scraper(mock_settings, NamingPatterns())
        return s

    def test_skip_if_nfo_exists(
        self, scraper: Scraper, tmp_path: Path,
    ) -> None:
        """Should skip movie if .nfo already exists."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.nfo").write_text("<movie/>")

        result = scraper.scrape_movie(movie_dir)
        assert result.action == "skipped_already_done"

    def test_skip_low_confidence(
        self, scraper: Scraper, tmp_path: Path,
    ) -> None:
        """Should skip if no confident match found."""
        movie_dir = tmp_path / "Unknown Movie (2024)"
        movie_dir.mkdir()

        with patch("personalscraper.scraper.scraper.match_movie", return_value=None):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "skipped_low_confidence"

    def test_full_scrape_flow(
        self, scraper: Scraper, tmp_path: Path,
    ) -> None:
        """Should complete full scrape: match → details → NFO → artwork."""
        movie_dir = tmp_path / "The Matrix (1999)"
        movie_dir.mkdir()
        (movie_dir / "The Matrix.mkv").write_text("video")

        match = MatchResult(
            api_id=603, api_title="The Matrix",
            api_year=1999, confidence=0.95, source="tmdb",
        )
        movie_data = {
            "id": 603,
            "title": "The Matrix",
            "overview": "A computer hacker...",
            "vote_average": 8.2,
            "vote_count": 20000,
            "genres": [{"name": "Action"}],
            "release_date": "1999-03-31",
            "credits": {"cast": [], "crew": []},
            "images": {"posters": [], "backdrops": []},
            "external_ids": {"imdb_id": "tt0133093"},
            "release_dates": {"results": []},
            "production_countries": [],
            "production_companies": [],
        }

        with (
            patch("personalscraper.scraper.scraper.match_movie", return_value=match),
            patch.object(scraper._tmdb, "get_movie", return_value=movie_data),
            patch("personalscraper.scraper.scraper.extract_stream_info", return_value=None),
            patch.object(scraper._artwork, "download_movie_artwork", return_value=[]),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "scraped"
        assert result.match == match
        assert result.nfo_written is True
        # Verify NFO was written
        assert (movie_dir / "The Matrix.nfo").exists()

    def test_error_on_match_failure(
        self, scraper: Scraper, tmp_path: Path,
    ) -> None:
        """Should return error result on match exception."""
        movie_dir = tmp_path / "Bad Movie (2024)"
        movie_dir.mkdir()

        with patch(
            "personalscraper.scraper.scraper.match_movie",
            side_effect=ConnectionError("API down"),
        ):
            result = scraper.scrape_movie(movie_dir)

        assert result.action == "error"
        assert "API down" in (result.error or "")


# ---------------------------------------------------------------------------
# Batch movie processing
# ---------------------------------------------------------------------------

class TestProcessMovies:
    """Tests for Scraper.process_movies."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock Settings."""
        settings = MagicMock()
        settings.tmdb_api_key = "fake-key"
        settings.tvdb_api_key = "fake-key"
        return settings

    @pytest.fixture
    def scraper(self, mock_settings: MagicMock) -> Scraper:
        """Create a Scraper with mocked clients."""
        with patch("personalscraper.scraper.scraper.TMDBClient"):
            s = Scraper(mock_settings, NamingPatterns())
        return s

    def test_processes_all_subdirs(
        self, scraper: Scraper, tmp_path: Path,
    ) -> None:
        """Should call scrape_movie for each subdirectory."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Movie A (2024)").mkdir()
        (movies_dir / "Movie B (2024)").mkdir()
        # Hidden directories should be skipped
        (movies_dir / ".hidden").mkdir()

        with patch.object(scraper, "scrape_movie") as mock_scrape:
            mock_scrape.return_value = ScrapeResult(
                media_path=Path("."), media_type="movie", action="scraped",
            )
            results = scraper.process_movies(movies_dir)

        assert len(results) == 2
        assert mock_scrape.call_count == 2

    def test_nonexistent_dir(self, scraper: Scraper, tmp_path: Path) -> None:
        """Should return empty list for nonexistent directory."""
        results = scraper.process_movies(tmp_path / "nonexistent")
        assert results == []

    def test_handles_scrape_error(
        self, scraper: Scraper, tmp_path: Path,
    ) -> None:
        """Should catch exceptions and add error results."""
        movies_dir = tmp_path / "001-MOVIES"
        movies_dir.mkdir()
        (movies_dir / "Bad Movie (2024)").mkdir()

        with patch.object(
            scraper, "scrape_movie",
            side_effect=RuntimeError("unexpected"),
        ):
            results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
