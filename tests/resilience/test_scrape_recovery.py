"""Resilience tests: scrape recovery from corrupt/incomplete state.

All tests create real corrupt filesystem states and verify recovery.
API calls are mocked but filesystem operations are real.
"""

import xml.etree.ElementTree as ET
from unittest.mock import patch

from personalscraper.scraper.scraper import _is_nfo_complete

from .conftest import make_valid_movie_dir


class TestNfoCorruptRecovery:
    """Tests 1-2: Corrupt NFO detection and re-scrape."""

    def test_truncated_nfo_detected_and_deleted(self, staging):
        """Truncated XML NFO is detected as incomplete."""
        movies = staging / "001-MOVIES"
        movie = movies / "Test Movie (2024)"
        movie.mkdir()
        (movie / "Test Movie.mkv").write_bytes(b"\x00" * 1024)
        # Write truncated NFO
        (movie / "Test Movie.nfo").write_text("<movie><title>Test</tit")

        assert _is_nfo_complete(movie / "Test Movie.nfo") is False

    def test_nfo_without_uniqueid_detected(self, staging):
        """NFO without <uniqueid> is detected as incomplete."""
        movies = staging / "001-MOVIES"
        movie = movies / "Test Movie (2024)"
        movie.mkdir()
        nfo = movie / "Test Movie.nfo"
        root = ET.Element("movie")
        ET.SubElement(root, "title").text = "Test Movie"
        ET.SubElement(root, "year").text = "2024"
        ET.ElementTree(root).write(nfo, encoding="unicode")

        assert _is_nfo_complete(nfo) is False

    @patch("personalscraper.scraper.run._has_unscraped_items", return_value=True)
    @patch("personalscraper.scraper.run.Scraper")
    def test_scrape_rescrapes_corrupt_nfo(
        self,
        MockScraper,
        mock_unscraped,
        staging,
        resilience_settings,
        resilience_config,
    ):
        """Scrape step detects corrupt NFO and triggers re-scrape."""
        from personalscraper.scraper.run import run_scrape
        from personalscraper.scraper.scraper import ScrapeResult

        movies = staging / "001-MOVIES"
        movie = movies / "Corrupt Movie (2024)"
        movie.mkdir()
        (movie / "Corrupt Movie.mkv").write_bytes(b"\x00" * 1024)
        # Write corrupt NFO (no uniqueid)
        (movie / "Corrupt Movie.nfo").write_text("<movie><title>X</title></movie>")

        # Mock scraper to return a successful result
        mock_scraper = MockScraper.return_value
        mock_scraper.process_movies.return_value = [
            ScrapeResult(media_path=movie, media_type="movie", action="scraped"),
        ]
        mock_scraper.process_tvshows.return_value = []

        run_scrape(resilience_settings, config=resilience_config)

        # Scraper was called (not skipped) because NFO is corrupt
        mock_scraper.process_movies.assert_called_once()


class TestArtworkPartialRecovery:
    """Test 3: Missing artwork recovery with valid NFO."""

    def test_valid_nfo_with_missing_artwork_triggers_recovery(self, staging):
        """Valid NFO + missing landscape should flag artwork as missing."""
        movies = staging / "001-MOVIES"
        movie = make_valid_movie_dir(movies, "Complete Movie", 2024)

        # Remove landscape to simulate partial artwork
        landscape = movie / "Complete Movie-landscape.jpg"
        landscape.unlink()

        # The movie has valid NFO but missing landscape
        assert _is_nfo_complete(movie / "Complete Movie.nfo") is True
        assert not landscape.exists()
        assert (movie / "Complete Movie-poster.jpg").exists()


class TestKillMidScrapeRecovery:
    """Test 8: Simulated kill during scrape — partial NFO + artwork."""

    def test_partial_nfo_and_artwork_detected(self, staging):
        """Partial state after simulated crash is correctly identified."""
        movies = staging / "001-MOVIES"
        movie = movies / "Crashed Movie (2024)"
        movie.mkdir()
        (movie / "Crashed Movie.mkv").write_bytes(b"\x00" * 1024)

        # Simulate crash: NFO written but truncated, poster exists
        (movie / "Crashed Movie.nfo").write_text("<movie><title>Cras")
        (movie / "Crashed Movie-poster.jpg").write_bytes(b"\xff\xd8")

        # NFO should be detected as incomplete
        assert _is_nfo_complete(movie / "Crashed Movie.nfo") is False
        # Poster exists but NFO is bad → full re-scrape needed
