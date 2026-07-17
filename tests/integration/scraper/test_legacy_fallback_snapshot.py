"""Characterization tests: lock in current orchestrator.py behavior.

Lines 150 (movies TMDB-only) and 223 (TV TVDB+TMDB) BEFORE Phase 1 migration.

These tests must remain green throughout Phase 1 and Phase 2.
If any breaks, registry semantics diverge from current behavior.

The 6 scenarios match DESIGN §8.4 verbatim, adapted to the actual orchestrator API:
- process_movies(movies_dir) → list[ScrapeResult]
- process_tvshows(tvshows_dir) → list[ScrapeResult]

Each test uses the real Scraper class with a mocked :class:`ProviderRegistry`
and asserts on ScrapeResult.action and ScrapeResult.error as they were before
the registry migration. The mocks moved from ``self._tmdb``/``self._tvdb``
direct attributes to ``self._registry.chain(...)`` / ``self._registry.get(...)``,
but the behavioral assertions are identical (ACC-13 equivalence proof).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api._contracts import CircuitOpenError
from personalscraper.api.metadata._contracts import MovieDetailsProvider, TvDetailsProvider
from personalscraper.api.metadata.registry import ProviderRegistry
from personalscraper.core.event_bus import EventBus
from personalscraper.naming_patterns import NamingPatterns
from personalscraper.scraper._shared import ScrapeResult
from personalscraper.scraper.orchestrator import Scraper


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
    def mock_tmdb(self) -> MagicMock:
        """Build a MagicMock standing in for the TMDB client.

        Used as the value returned by ``registry.get("tmdb")`` and as the
        sole entry in ``registry.chain(MovieDetailsProvider)`` /
        ``registry.chain(TvDetailsProvider)`` for tests that mirror the
        pre-registry single-provider scenarios.
        """
        return MagicMock(name="MockTMDBClient")

    @pytest.fixture
    def mock_tvdb(self) -> MagicMock:
        """Build a MagicMock standing in for the TVDB client."""
        return MagicMock(name="MockTVDBClient")

    @pytest.fixture
    def mock_registry(self, mock_tmdb: MagicMock, mock_tvdb: MagicMock) -> MagicMock:
        """Build a mock :class:`ProviderRegistry`.

        Defaults to both TMDB and TVDB being eligible for any chain
        capability — tests override ``chain.side_effect`` to model
        per-capability emptiness when simulating circuit-open scenarios.
        """
        reg = MagicMock(spec=ProviderRegistry)
        reg.get.side_effect = lambda name: {"tmdb": mock_tmdb, "tvdb": mock_tvdb}[name]

        # Default chain behaviour: both providers eligible for any capability.
        # Tests that need an empty chain (== legacy "circuit OPEN") override
        # this with ``chain.side_effect``.
        def _default_chain(capability):
            if capability is MovieDetailsProvider:
                return [mock_tmdb]
            if capability is TvDetailsProvider:
                return [mock_tvdb, mock_tmdb]
            return []

        reg.chain.side_effect = _default_chain
        return reg

    @pytest.fixture
    def scraper(self, mock_settings, mock_registry):
        """Create a Scraper wired to the mock registry."""
        return Scraper(mock_settings, NamingPatterns(), event_bus=EventBus(), registry=mock_registry)

    # ------------------------------------------------------------------
    # Test 1 — DESIGN §8.4 scenario 1
    # ------------------------------------------------------------------

    def test_movies_tmdb_circuit_open_produces_error(self, scraper, movies_dir, mock_registry):
        """No eligible MovieDetailsProvider → process_movies skips with error.

        Verifies the registry-driven gate in :meth:`Scraper.process_movies`
        — when ``registry.chain(MovieDetailsProvider)`` returns an empty
        list (all circuits OPEN), the item is skipped immediately.
        Preserves the legacy "TMDB circuit breaker OPEN" error wording.
        """

        def _empty_movies(capability):
            if capability is MovieDetailsProvider:
                return []
            return [MagicMock()]

        mock_registry.chain.side_effect = _empty_movies

        results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "TMDB circuit breaker OPEN" in results[0].error

    # ------------------------------------------------------------------
    # Test 2 — DESIGN §8.4 scenario 2
    # ------------------------------------------------------------------

    def test_movies_tmdb_circuit_open_mid_item_produces_error(self, scraper, movies_dir):
        """CircuitOpenError raised during scrape_movie → caught and recorded.

        Verifies the ``except CircuitOpenError`` arm in
        :meth:`Scraper.process_movies` produces ``action="error"`` with the
        exception message in ``.error``.
        """
        scraper.scrape_movie = MagicMock(side_effect=CircuitOpenError("tmdb", 60.0))

        results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "tmdb" in results[0].error.lower()

    # ------------------------------------------------------------------
    # Test 3 — DESIGN §8.4 scenario 3
    # ------------------------------------------------------------------

    def test_tvshows_tvdb_open_tmdb_available_uses_tmdb(self, scraper, tvshows_dir, mock_registry, mock_tmdb):
        """One eligible TvDetailsProvider remains → orchestrator proceeds.

        Mirrors the legacy "TVDB circuit OPEN but TMDB CLOSED" scenario:
        the chain shrinks but is non-empty, so the gate at
        :meth:`Scraper.process_tvshows` does NOT skip the item.
        ``scrape_tvshow`` is mocked to confirm the gate let the item
        through.
        """

        def _tmdb_only(capability):
            if capability is TvDetailsProvider:
                return [mock_tmdb]
            return [mock_tmdb]

        mock_registry.chain.side_effect = _tmdb_only

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

    def test_tvshows_both_circuits_open_produces_error(self, scraper, tvshows_dir, mock_registry):
        """No eligible TvDetailsProvider → skip with error.

        Verifies the registry-driven gate at
        :meth:`Scraper.process_tvshows` — an empty chain is the registry
        equivalent of "both TVDB and TMDB circuits OPEN". The legacy
        error wording is preserved verbatim.
        """

        def _empty_tv(capability):
            if capability is TvDetailsProvider:
                return []
            return [MagicMock()]

        mock_registry.chain.side_effect = _empty_tv

        results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "Both TVDB and TMDB" in results[0].error

    # ------------------------------------------------------------------
    # Test 5 — DESIGN §8.4 scenario 5
    # ------------------------------------------------------------------

    def test_movies_network_error_during_scrape_produces_error(self, scraper, movies_dir):
        """Network error during scrape_movie → caught by generic except.

        Verifies the generic ``except Exception`` arm in
        :meth:`Scraper.process_movies` catches non-circuit errors
        (network, transport, etc.) and produces ``action="error"``.
        """
        scraper.scrape_movie = MagicMock(side_effect=ConnectionError("Network unreachable"))

        results = scraper.process_movies(movies_dir)

        assert len(results) == 1
        assert results[0].action == "error"
        assert "Network unreachable" in results[0].error

    # ------------------------------------------------------------------
    # Test 6 — DESIGN §8.4 scenario 6
    # ------------------------------------------------------------------

    def test_tvshows_all_providers_empty_search_skips(self, scraper, tvshows_dir):
        """Every chain provider returns an empty match → "skipped_low_confidence".

        Post-P4.3, ``_lookup_series`` iterates ``registry.chain(TvDetailsProvider)``
        via ``run_chain`` and consults TMDB when TVDB is empty (SCRAPER-02). When
        *every* provider returns an empty match, ``run_chain`` returns ``None`` and
        the below-threshold path sets ``result.action = "skipped_low_confidence"``
        — the legacy fail-soft outcome for a show no provider can identify.
        """
        with patch(
            "personalscraper.scraper.tv_service_episodes.match_tvshow_single_detailed",
            return_value=(None, []),
        ):
            results = scraper.process_tvshows(tvshows_dir)

        assert len(results) == 1
        assert results[0].action == "skipped_low_confidence"
