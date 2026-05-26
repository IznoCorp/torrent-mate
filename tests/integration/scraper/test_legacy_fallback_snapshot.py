"""Characterization tests: lock in current orchestrator.py behavior.

Lines 150 (movies TMDB-only) and 223 (TV TVDB+TMDB) BEFORE Phase 1 migration.

These tests must remain green throughout Phase 1 and Phase 2.
If any breaks, registry semantics diverge from current behavior.

The 6 scenarios match DESIGN §8.4 verbatim, adapted to the actual orchestrator API:
- process_movies(movies_dir) → list[ScrapeResult]
- process_tvshows(tvshows_dir) → list[ScrapeResult]

Each test uses the real Scraper class with mocked TMDB/TVDB clients and
asserts on ScrapeResult.action and ScrapeResult.error as they are TODAY.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.orchestrator import Scraper


@pytest.fixture(autouse=True)
def _patch_transport():
    """Patch HttpTransport so Scraper init + TVDB bootstrap don't build real ones."""
    mock_instance = MagicMock()
    mock_instance.__enter__.return_value = mock_instance
    mock_instance.post.return_value = {"data": {"token": "mock-jwt"}}
    mock_instance.get.return_value = {}

    with (
        patch("personalscraper.api.transport._http.HttpTransport", return_value=mock_instance),
        patch("personalscraper.api.metadata.tvdb.HttpTransport", return_value=mock_instance),
    ):
        yield


@pytest.fixture
def mock_settings():
    """Create mock Settings with fake API keys."""
    settings = MagicMock()
    settings.tmdb_api_key = "fake-tmdb-key"
    settings.tvdb_api_key = "fake-tvdb-key"
    return settings


@pytest.fixture
def movies_dir(tmp_path: Path) -> Path:
    """Create a temporary movies directory with one movie subdir."""
    movies = tmp_path / "001-MOVIES"
    movies.mkdir()
    (movies / "The Matrix (1999)").mkdir()
    return movies


@pytest.fixture
def tvshows_dir(tmp_path: Path) -> Path:
    """Create a temporary TV shows directory with one show subdir."""
    shows = tmp_path / "002-TVSHOWS"
    shows.mkdir()
    (shows / "Breaking Bad (2008)").mkdir()
    return shows


class TestLegacyFallbackSnapshot:
    """Characterization tests locking in current orchestrator circuit-check behavior."""

    @pytest.fixture
    def scraper(self, mock_settings):
        """Create a Scraper with both TMDB and TVDB clients fully mocked.

        Patches both client classes so self._tmdb / self._tvdb are MagicMock
        instances.  Their .circuit.can_proceed() returns True by default
        (MagicMock is truthy), representing CLOSED circuits.
        """
        with (
            patch("personalscraper.api.metadata.tmdb.TMDBClient"),
            patch("personalscraper.api.metadata.tvdb.TVDBClient"),
        ):
            s = Scraper(mock_settings, NamingPatterns(), event_bus=EventBus())
        s._tmdb.circuit.can_proceed.return_value = True
        s._tvdb.circuit.can_proceed.return_value = True
        return s

    # ------------------------------------------------------------------
    # Test 1 — DESIGN §8.4 scenario 1
    # ------------------------------------------------------------------

    def test_movies_tmdb_circuit_open_produces_error(self, scraper, movies_dir):
        """TMDB circuit OPEN → process_movies gate skips item with error.

        Verifies the gate at orchestrator.py:150 — when
        self._tmdb.circuit.can_proceed() returns False, the item is
        skipped immediately (no fallback for movies).
        """
        scraper._tmdb.circuit.can_proceed.return_value = False

        results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "TMDB circuit breaker OPEN" in results[0].error

    # ------------------------------------------------------------------
    # Test 2 — DESIGN §8.4 scenario 2
    # ------------------------------------------------------------------

    def test_movies_tmdb_circuit_open_mid_item_produces_error(self, scraper, movies_dir):
        """CircuitOpenError raised during scrape_movie → caught and recorded.

        Verifies the except CircuitOpenError arm at orchestrator.py:165
        produces action="error" with the exception message in .error.
        """
        scraper._tmdb.circuit.can_proceed.return_value = True
        scraper.scrape_movie = MagicMock(side_effect=CircuitOpenError("tmdb", 60.0))

        results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "tmdb" in results[0].error.lower()

    # ------------------------------------------------------------------
    # Test 3 — DESIGN §8.4 scenario 3
    # ------------------------------------------------------------------

    def test_tvshows_tvdb_open_tmdb_available_uses_tmdb(self, scraper, tvshows_dir):
        """TVDB circuit OPEN but TMDB CLOSED → orchestrator proceeds.

        Verifies the gate at orchestrator.py:223 — when TVDB is OPEN
        but TMDB is still CLOSED, the condition
        ``not self._tvdb.can_proceed() and not self._tmdb.can_proceed()``
        is False, so the item is NOT skipped.  scrape_tvshow is called
        and the internal fallback logic (match_tvshow in confidence.py)
        handles the actual provider selection.

        We mock scrape_tvshow to return success — the test covers the
        orchestrator-level gate, not the full scrape path.
        """
        scraper._tvdb.circuit.can_proceed.return_value = False
        scraper._tmdb.circuit.can_proceed.return_value = True
        scraper.scrape_tvshow = MagicMock(
            return_value=ScrapeResult(
                media_path=tvshows_dir / "Breaking Bad (2008)",
                media_type="tvshow",
                action="scraped",
            )
        )

        results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action != "error"

    # ------------------------------------------------------------------
    # Test 4 — DESIGN §8.4 scenario 4
    # ------------------------------------------------------------------

    def test_tvshows_both_circuits_open_produces_error(self, scraper, tvshows_dir):
        """Both TVDB and TMDB circuits OPEN → skip with error.

        Verifies the gate at orchestrator.py:223 — when both providers
        are unavailable the item is skipped with the "Both TVDB and TMDB
        circuit breakers OPEN" message.
        """
        scraper._tvdb.circuit.can_proceed.return_value = False
        scraper._tmdb.circuit.can_proceed.return_value = False

        results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "Both TVDB and TMDB" in results[0].error

    # ------------------------------------------------------------------
    # Test 5 — DESIGN §8.4 scenario 5
    # ------------------------------------------------------------------

    def test_movies_network_error_during_scrape_produces_error(self, scraper, movies_dir):
        """Network error during scrape_movie → caught by generic except.

        Verifies the generic except Exception arm at orchestrator.py:176
        catches non-circuit errors (network, transport, etc.) and
        produces action="error".
        """
        scraper._tmdb.circuit.can_proceed.return_value = True
        scraper.scrape_movie = MagicMock(side_effect=ConnectionError("Network unreachable"))

        results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "Network unreachable" in results[0].error

    # ------------------------------------------------------------------
    # Test 6 — DESIGN §8.4 scenario 6
    # ------------------------------------------------------------------

    def test_tvshows_tvdb_empty_search_no_fallback_currently(self, scraper, tvshows_dir):
        """TVDB returns empty search results → "skipped_low_confidence" today.

        When match_tvshow returns None (no confident match from TVDB,
        e.g. empty search results), _lookup_series in tv_service.py:478
        sets result.action = "skipped_low_confidence".  There is no
        cross-provider fallback at this level — the registry (Phase 2)
        will add chain fallback to try TMDB when TVDB comes back empty.

        NOTE: This is a characterization of CURRENT behavior, not a
        design target.  The registry will change this outcome.
        """
        scraper._tvdb.circuit.can_proceed.return_value = True
        scraper._tmdb.circuit.can_proceed.return_value = True

        with patch("personalscraper.scraper.scraper.match_tvshow", return_value=None):
            results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "skipped_low_confidence"
