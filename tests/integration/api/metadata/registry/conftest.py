"""Shared HTTP-level fixtures for ProviderRegistry integration tests.

Provides helpers for building a real ProviderRegistry with HTTP mocked
via ``responses``, and for building a registry with monkeypatched
providers when needed capabilities (IDCrossRef, RatingProvider) are not
available on TMDB/TVDB.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import requests  # noqa: F401
import responses

# ruff: noqa: D102, D107  # Test helpers with obvious behavior
from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import (
    ArtworkItem,
    Notations,
)
from personalscraper.api.transport._policy import CircuitPolicy
from personalscraper.conf.models.providers import ProvidersConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TMDB_BASE = "https://api.themoviedb.org/3"
TVDB_BASE = "https://api4.thetvdb.com/v4"


# ---------------------------------------------------------------------------
# HTTP mock helpers
# ---------------------------------------------------------------------------


def add_tvdb_bootstrap() -> None:
    """Mock the TVDB bootstrap login so TVDBClient can be constructed."""
    responses.add(
        responses.POST,
        f"{TVDB_BASE}/login",
        json={"data": {"token": "fake-jwt-token"}},
        status=200,
    )


def add_tmdb_503() -> None:
    """Mock TMDB search returning 503 for all paths."""
    responses.add(
        responses.GET,
        f"{TMDB_BASE}/search/movie",
        json={"status_code": 34, "status_message": "Service Unavailable"},
        status=503,
    )
    responses.add(
        responses.GET,
        f"{TMDB_BASE}/search/tv",
        json={"status_code": 34, "status_message": "Service Unavailable"},
        status=503,
    )


def add_tmdb_search_empty() -> None:
    """Mock TMDB search returning 200 with empty results."""
    responses.add(
        responses.GET,
        f"{TMDB_BASE}/search/movie",
        json={"page": 1, "results": [], "total_pages": 0, "total_results": 0},
        status=200,
    )


def add_tmdb_search_success(results: list[dict[str, Any]] | None = None) -> None:
    """Mock TMDB search returning 200 with given results."""
    if results is None:
        results = [
            {
                "id": 12345,
                "title": "Test Movie",
                "release_date": "2020-01-01",
                "overview": "A test movie.",
                "poster_path": "/poster.jpg",
                "backdrop_path": "/backdrop.jpg",
                "vote_average": 7.5,
                "vote_count": 100,
                "genre_ids": [28, 12],
                "original_language": "en",
                "original_title": "Test Movie",
                "popularity": 50.0,
                "video": False,
                "adult": False,
            }
        ]
    responses.add(
        responses.GET,
        f"{TMDB_BASE}/search/movie",
        json={"page": 1, "results": results, "total_pages": 1, "total_results": len(results)},
        status=200,
    )


def add_tvdb_search_empty() -> None:
    """Mock TVDB search returning 200 with empty data."""
    responses.add(
        responses.GET,
        f"{TVDB_BASE}/search",
        json={"data": []},
        status=200,
    )


def add_tvdb_search_success(results: list[dict[str, Any]] | None = None) -> None:
    """Mock TVDB search returning 200 with given results."""
    if results is None:
        results = [
            {
                "id": 67890,
                "name": "Test Series",
                "first_air_time": "2020-01-01",
                "overview": "A test series.",
                "image_url": "https://artworks.thetvdb.com/posters/67890.jpg",
                "type": "series",
                "country": "usa",
                "primary_language": "eng",
                "status": "Continuing",
                "year": "2020",
            }
        ]
    responses.add(
        responses.GET,
        f"{TVDB_BASE}/search",
        json={"data": results, "status": "success"},
        status=200,
    )


def add_tvdb_503() -> None:
    """Mock TVDB search returning 503."""
    responses.add(
        responses.GET,
        f"{TVDB_BASE}/search",
        json={"message": "Internal Server Error"},
        status=503,
    )


# ---------------------------------------------------------------------------
# CircuitPolicy / Settings stubs
# ---------------------------------------------------------------------------


def make_cb_policy(
    failure_threshold: int = 2,
    cooldown_seconds: float = 0.01,
) -> CircuitPolicy:
    """Build an aggressive CircuitPolicy for fast tests."""
    return CircuitPolicy(
        failure_threshold=failure_threshold,
        cooldown_seconds=cooldown_seconds,
    )


def make_settings(**overrides: Any) -> Any:
    """Build a minimal Settings-like stub for registry construction."""
    defaults: dict[str, Any] = {
        "tmdb_api_key": "dummy_tmdb_key",
        "tvdb_api_key": "dummy_tvdb_key",
        "qbit_host": "",
        "qbit_port": 0,
        "qbit_username": "",
        "qbit_password": "",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Fake providers for tests needing capabilities TMDB/TVDB lack
# ---------------------------------------------------------------------------


def _make_fake_circuit(state: str = "CLOSED") -> SimpleNamespace:
    return SimpleNamespace(
        state=state,
        can_proceed=lambda: state != "OPEN",
    )


class FakeRating:
    """Fake provider implementing RatingProvider."""

    def __init__(self, *, name: str = "fake_rating", circuit_state: str = "CLOSED"):
        self.name = name
        self.circuit = _make_fake_circuit(circuit_state)
        self._should_fail: bool = False
        self.closed = False

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        if self._should_fail:
            from personalscraper.api._contracts import ApiError

            raise ApiError(provider=self.name, http_status=503, provider_code=0, message="fake 503")
        return [Notations(source=self.name, score=7.5, max_score=10, votes=100)]

    def close(self) -> None:
        self.closed = True


class FakeArtwork:
    """Fake provider implementing ArtworkProvider."""

    def __init__(self, *, name: str = "fake_artwork", circuit_state: str = "CLOSED"):
        self.name = name
        self.circuit = _make_fake_circuit(circuit_state)
        self.closed = False

    def get_artwork_urls(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> list[ArtworkItem]:
        return [ArtworkItem(url=f"https://art.example.com/{media_id}.jpg", type="poster")]

    def close(self) -> None:
        self.closed = True


class FakeIDCrossRefProvider:
    """Fake provider implementing IDCrossRef + other capabilities."""

    def __init__(self, *, name: str, xref_table: dict[str, dict[str, str]] | None = None):
        self.name = name
        self.circuit = _make_fake_circuit("CLOSED")
        self._xref = xref_table or {}
        self.closed = False

    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        return dict(self._xref.get(provider_id, {}))

    def get_artwork_urls(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> list[ArtworkItem]:
        return [ArtworkItem(url=f"https://art.example.com/{media_id}.jpg", type="poster")]

    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]:
        return ["test", "keywords"]

    def close(self) -> None:
        self.closed = True


class MockEventBus:
    """In-memory EventBus stub that records emitted events."""

    def __init__(self) -> None:
        self.emitted: list[object] = []

    def emit(self, event: object) -> None:
        self.emitted.append(event)


# ---------------------------------------------------------------------------
# Repeated mock helpers (for retry-heavy circuit breaker tests)
# ---------------------------------------------------------------------------


def add_tmdb_search_503_repeated(n: int = 20) -> None:
    """Add N 503 mocks for TMDB search so tenacity retries don't exhaust the mock."""
    for _ in range(n):
        responses.add(
            responses.GET,
            f"{TMDB_BASE}/search/movie",
            json={"status_code": 34, "status_message": "Service Unavailable"},
            status=503,
        )


def add_tmdb_search_connection_error_repeated(n: int = 20) -> None:
    """Add N ConnectionError mocks for TMDB search."""
    for _ in range(n):
        responses.add(
            responses.GET,
            f"{TMDB_BASE}/search/movie",
            body=requests.ConnectionError("connection reset"),
        )


def add_tvdb_search_503_repeated(n: int = 20) -> None:
    """Add N 503 mocks for TVDB search."""
    for _ in range(n):
        responses.add(
            responses.GET,
            f"{TVDB_BASE}/search",
            json={"message": "Internal Server Error"},
            status=503,
        )


# ---------------------------------------------------------------------------
# Registry builder with monkeypatched providers (for IDCrossRef/RatingProvider)
# ---------------------------------------------------------------------------


@pytest.fixture
def build_registry_fakes(monkeypatch: pytest.MonkeyPatch):
    """Return a factory building ProviderRegistry from fake providers.

    Monkeypatches ``_factory.build_providers`` and bypasses validation.
    """
    from personalscraper.api.metadata.registry import ProviderRegistry, _factory, _validation

    def _build(
        *,
        fakes: dict[str, object],
        providers_config: ProvidersConfig,
        event_bus: object | None = None,
    ) -> ProviderRegistry:
        if event_bus is None:
            event_bus = MockEventBus()

        def fake_build_providers(
            names: list[str],
            settings_arg: object,
            cb_policy_arg: object,
            event_bus_arg: object,
        ) -> dict[str, object]:
            return {n: fakes[n] for n in names if n in fakes}

        monkeypatch.setattr(_factory, "build_providers", fake_build_providers)
        monkeypatch.setattr(_validation, "_CRED_MAP", {})
        monkeypatch.setattr(_validation, "_check_empty_chain_sections", lambda _: [])
        monkeypatch.setattr(_validation, "_check_protocol_mismatch", lambda *a: [])

        return ProviderRegistry(
            settings=SimpleNamespace(),
            event_bus=event_bus,
            cb_policy=SimpleNamespace(),
            providers_config=providers_config,
        )

    return _build
