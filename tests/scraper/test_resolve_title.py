"""Tests for Scraper._resolve_title() — local FR title preference."""

from unittest.mock import MagicMock

from personalscraper.scraper.scraper import Scraper


def _make_scraper(prefer_local: bool = True) -> Scraper:
    """Create a Scraper with mocked settings for title resolution tests."""
    settings = MagicMock()
    settings.scraper_prefer_local_title = prefer_local
    settings.tmdb_api_key = "fake"
    settings.tvdb_api_key = "fake"
    settings.circuit_breaker_threshold = 5
    settings.circuit_breaker_cooldown = 300
    return Scraper(settings, MagicMock(), dry_run=True)


class TestResolveTitle:
    """Tests for _resolve_title() method."""

    def test_returns_local_title_when_preferred(self):
        """When prefer_local_title=True, returns FR title from API data."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {
            "title": "Le Procès du Siècle",
            "original_title": "Jury Duty",
        }
        result = scraper._resolve_title("Jury Duty", api_data, "movie")
        assert result == "Le Procès du Siècle"

    def test_returns_match_title_when_no_preference(self):
        """When prefer_local_title=False, returns match title."""
        scraper = _make_scraper(prefer_local=False)
        api_data = {
            "title": "Le Procès du Siècle",
            "original_title": "Jury Duty",
        }
        result = scraper._resolve_title("Jury Duty", api_data, "movie")
        assert result == "Jury Duty"

    def test_fallback_when_no_local_title(self):
        """When API data has no local title, falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {
            "title": "",
            "original_title": "Some Movie",
        }
        result = scraper._resolve_title("Some Movie", api_data, "movie")
        assert result == "Some Movie"

    def test_fallback_when_local_equals_original(self):
        """When local title = original title, falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {
            "title": "Jury Duty",  # Same as original — no translation
            "original_title": "Jury Duty",
        }
        result = scraper._resolve_title("Jury Duty", api_data, "movie")
        # local_title == original_title AND local_title == match_title → returns match_title
        assert result == "Jury Duty"

    def test_tvshow_uses_name_key(self):
        """TV shows use 'name' key instead of 'title'."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {
            "name": "Le Bureau des Légendes",
            "original_name": "The Bureau",
        }
        result = scraper._resolve_title("The Bureau", api_data, "tvshow")
        assert result == "Le Bureau des Légendes"

    def test_tvshow_fallback_no_name(self):
        """TV show without 'name' key falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {}
        result = scraper._resolve_title("Show Title", api_data, "tvshow")
        assert result == "Show Title"
