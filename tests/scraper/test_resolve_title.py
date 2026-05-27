"""Tests for Scraper._resolve_title() — local FR title preference.

Phase-27 parity coverage: ``_resolve_title`` must handle both the legacy
TMDB-flavoured raw dict shape (still emitted by some test fixtures and
the TVDB→show_data converter) and the typed ``MediaDetails`` returned
directly by api-unify clients. Both paths go through the
``_coerce_to_classifier_dict`` shim and must produce identical results.
"""

from unittest.mock import MagicMock, patch

from personalscraper.api.metadata._base import MediaDetails
from personalscraper.core.event_bus import EventBus
from personalscraper.scraper.scraper import Scraper


def _make_scraper(prefer_local: bool = True) -> Scraper:
    """Create a Scraper with mocked settings for title resolution tests."""
    from personalscraper.api.metadata.registry import ProviderRegistry

    settings = MagicMock()
    settings.tmdb_api_key = "fake"
    settings.tvdb_api_key = "fake"
    settings.circuit_breaker_threshold = 5
    settings.circuit_breaker_cooldown = 300

    config = MagicMock()
    config.scraper.language = "fr-FR"
    config.scraper.fallback_language = "en-US"
    config.scraper.prefer_local_title = prefer_local
    config.scraper.artwork_language = "en"
    config.thresholds.circuit_breaker_threshold = 5
    config.thresholds.circuit_breaker_cooldown = 300

    with (
        patch("personalscraper.api.transport._http.HttpTransport"),
        patch("personalscraper.api.metadata.tvdb.HttpTransport"),
        patch("personalscraper.api.metadata.tmdb.TMDBClient"),
        patch("personalscraper.api.metadata.tvdb.TVDBClient"),
    ):
        return Scraper(
            settings,
            MagicMock(),
            dry_run=True,
            config=config,
            interactive=False,
            event_bus=EventBus(),
            registry=MagicMock(spec=ProviderRegistry),
        )


class TestResolveTitleDictShape:
    """Legacy dict-shape input — preserves backward compatibility."""

    def test_returns_local_title_when_preferred(self) -> None:
        """When prefer_local_title=True, returns FR title from API data."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {"title": "Le Procès du Siècle", "original_title": "Jury Duty"}
        assert scraper._resolve_title("Jury Duty", api_data, "movie") == "Le Procès du Siècle"

    def test_returns_match_title_when_no_preference(self) -> None:
        """When prefer_local_title=False, returns match title."""
        scraper = _make_scraper(prefer_local=False)
        api_data = {"title": "Le Procès du Siècle", "original_title": "Jury Duty"}
        assert scraper._resolve_title("Jury Duty", api_data, "movie") == "Jury Duty"

    def test_fallback_when_no_local_title(self) -> None:
        """Empty local title falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {"title": "", "original_title": "Some Movie"}
        assert scraper._resolve_title("Some Movie", api_data, "movie") == "Some Movie"

    def test_fallback_when_local_equals_original(self) -> None:
        """When local title == original title, falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {"title": "Jury Duty", "original_title": "Jury Duty"}
        assert scraper._resolve_title("Jury Duty", api_data, "movie") == "Jury Duty"

    def test_tvshow_uses_name_key(self) -> None:
        """TV shows look up the localised title under ``name``."""
        scraper = _make_scraper(prefer_local=True)
        api_data = {"name": "Le Bureau des Légendes", "original_name": "The Bureau"}
        assert scraper._resolve_title("The Bureau", api_data, "tvshow") == "Le Bureau des Légendes"

    def test_tvshow_fallback_no_name(self) -> None:
        """TV show without ``name`` key falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        assert scraper._resolve_title("Show Title", {}, "tvshow") == "Show Title"


def _md(*, title: str = "", original_title: str = "") -> MediaDetails:
    """Build a minimal MediaDetails — used by the typed-shape tests below."""
    return MediaDetails(provider="tmdb", provider_id="0", title=title, original_title=original_title)


class TestResolveTitleMediaDetailsShape:
    """Typed MediaDetails input — phase-27 path must give the same answers."""

    def test_returns_local_title_when_preferred(self) -> None:
        """MediaDetails.title is the localised title for both movies and TV."""
        scraper = _make_scraper(prefer_local=True)
        details = _md(title="Le Procès du Siècle", original_title="Jury Duty")
        assert scraper._resolve_title("Jury Duty", details, "movie") == "Le Procès du Siècle"

    def test_returns_match_title_when_no_preference(self) -> None:
        """When prefer_local_title=False, returns match title."""
        scraper = _make_scraper(prefer_local=False)
        details = _md(title="Le Procès du Siècle", original_title="Jury Duty")
        assert scraper._resolve_title("Jury Duty", details, "movie") == "Jury Duty"

    def test_fallback_when_no_local_title(self) -> None:
        """Empty MediaDetails.title falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        details = _md(title="", original_title="Some Movie")
        assert scraper._resolve_title("Some Movie", details, "movie") == "Some Movie"

    def test_fallback_when_local_equals_original(self) -> None:
        """When MediaDetails.title == original_title, falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        details = _md(title="Jury Duty", original_title="Jury Duty")
        assert scraper._resolve_title("Jury Duty", details, "movie") == "Jury Duty"

    def test_tvshow_localised_name(self) -> None:
        """TV: MediaDetails.title carries the localised name (TMDB ``name``)."""
        scraper = _make_scraper(prefer_local=True)
        details = _md(title="Le Bureau des Légendes", original_title="The Bureau")
        assert scraper._resolve_title("The Bureau", details, "tvshow") == "Le Bureau des Légendes"

    def test_tvshow_fallback_empty_details(self) -> None:
        """Empty MediaDetails falls back to match title."""
        scraper = _make_scraper(prefer_local=True)
        assert scraper._resolve_title("Show Title", _md(), "tvshow") == "Show Title"
