"""Shared fixtures for the ProviderRegistry unit-test suite (DESIGN §8.2).

Provides:

- Fake provider classes implementing capability Protocols (Searchable,
  MovieDetailsProvider, TvDetailsProvider, EpisodeFetcher, RatingProvider,
  ArtworkProvider, KeywordProvider, VideoProvider, RecommendationProvider,
  IDValidator).
- MockEventBus that records emitted events without performing real emission.
- build_registry() fixture factory that constructs a ``ProviderRegistry``
  with fake providers, bypassing real-provider instantiation and credential
  validation. The factory monkeypatches ``build_providers`` + the credential
  check so that tests can focus on registry semantics rather than provider
  wiring.
- Sample ``ProvidersConfig`` builders for the five ``ConfigIssue`` families.

The fixtures are intentionally minimal — only enough to drive the ~40
tests enumerated in plan Appendix A. They do not attempt to stand in for
real provider behavior.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from personalscraper.api._contracts import MediaType
from personalscraper.api.metadata._base import (
    ArtworkItem,
    EpisodeInfo,
    MediaDetails,
    Notations,
    Recommendation,
    SearchResult,
    Video,
)
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState

# ---------------------------------------------------------------------------
# Mock EventBus
# ---------------------------------------------------------------------------


class MockEventBus:
    """In-memory EventBus that records emitted events.

    Attributes:
        emitted: List of every event passed to ``emit()``.
    """

    def __init__(self) -> None:
        """Initialize an empty emitted-events list."""
        self.emitted: list[object] = []

    def emit(self, event: object) -> None:
        """Append ``event`` to ``self.emitted`` without further dispatch.

        Args:
            event: The event payload to record.
        """
        self.emitted.append(event)


class FailingEventBus:
    """EventBus that raises on every ``emit()`` call.

    Used to verify the registry's ``_event_bus_safe_emit`` swallows
    failures without propagating.
    """

    def emit(self, event: object) -> None:
        """Raise to simulate a bus implementation that has failed.

        Args:
            event: Ignored — this bus never accepts events.

        Raises:
            RuntimeError: Always.
        """
        raise RuntimeError("event bus is broken")


# ---------------------------------------------------------------------------
# Fake provider classes (implement capability Protocols structurally)
# ---------------------------------------------------------------------------


def _make_circuit(state: CircuitState = CircuitState.CLOSED) -> SimpleNamespace:
    """Build a fake circuit object with controllable ``state`` and ``can_proceed``.

    Args:
        state: Initial circuit state (CircuitState.CLOSED, CircuitState.OPEN,
            CircuitState.HALF_OPEN).

    Returns:
        A ``SimpleNamespace`` exposing ``state`` and ``can_proceed()``.
    """
    return SimpleNamespace(
        state=state,
        can_proceed=lambda: state is not CircuitState.OPEN,
    )


class FakeSearchable:
    """Fake provider implementing Searchable.

    Attributes:
        provider_name: Stable provider name used in config keys and events.
        circuit: Controllable circuit-breaker surface.
        closed: Flag set by ``close()`` for cleanup-test assertions.
    """

    provider_name: ClassVar[str] = "fake_searchable"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        results: list[SearchResult] | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
    ) -> None:
        """Build a FakeSearchable with optional canned results and circuit state."""
        if provider_name is not None:
            self.provider_name = provider_name
        self._results = results or []
        self.circuit = _make_circuit(circuit_state)
        self.closed = False

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Return canned ``SearchResult`` list.

        Args:
            title: Ignored.
            year: Ignored.
            media_type: Ignored.

        Returns:
            The canned results provided at construction.
        """
        return list(self._results)

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


class FakeMovieDetails:
    """Fake provider implementing Searchable + MovieDetailsProvider."""

    provider_name: ClassVar[str] = "fake_movie_details"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
        movie: MediaDetails | None = None,
    ) -> None:
        """Build the fake with optional canned details and circuit state."""
        if provider_name is not None:
            self.provider_name = provider_name
        self.circuit = _make_circuit(circuit_state)
        self._movie = movie
        self.closed = False

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Return an empty search result list (search not exercised here)."""
        return []

    def get_movie(self, provider_id: str) -> MediaDetails:
        """Return canned movie details — raises if not configured."""
        if self._movie is None:
            raise RuntimeError("no movie configured on fake")
        return self._movie

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


class FakeTvDetails:
    """Fake provider implementing Searchable + TvDetailsProvider + EpisodeFetcher."""

    provider_name: ClassVar[str] = "fake_tv_details"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
    ) -> None:
        """Build the fake with controllable circuit state."""
        if provider_name is not None:
            self.provider_name = provider_name
        self.circuit = _make_circuit(circuit_state)
        self.closed = False

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Return an empty list (search behavior not exercised here)."""
        return []

    def get_tv(self, provider_id: str) -> MediaDetails:
        """Return a minimal MediaDetails — raises by default."""
        raise RuntimeError("not configured")

    def get_episodes(self, series_id: str, season: int) -> list[EpisodeInfo]:
        """Return an empty episode list."""
        return []

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


class FakeRating:
    """Fake provider implementing RatingProvider."""

    provider_name: ClassVar[str] = "fake_rating"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
        notations: list[Notations] | None = None,
    ) -> None:
        """Build the fake with optional canned notations."""
        if provider_name is not None:
            self.provider_name = provider_name
        self.circuit = _make_circuit(circuit_state)
        self._notations = notations
        self.closed = False

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        """Return canned notations (or None)."""
        return self._notations

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


class FakeArtwork:
    """Fake provider implementing ArtworkProvider."""

    provider_name: ClassVar[str] = "fake_artwork"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
    ) -> None:
        """Build the fake with controllable circuit state."""
        if provider_name is not None:
            self.provider_name = provider_name
        self.circuit = _make_circuit(circuit_state)
        self.closed = False

    def get_artwork_urls(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[ArtworkItem]:
        """Return an empty artwork list."""
        return []

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


class FakeKeyword:
    """Fake provider implementing KeywordProvider."""

    provider_name: ClassVar[str] = "fake_keyword"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
    ) -> None:
        """Build the fake with controllable circuit state."""
        if provider_name is not None:
            self.provider_name = provider_name
        self.circuit = _make_circuit(circuit_state)
        self.closed = False

    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]:
        """Return an empty keyword list."""
        return []

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


class FakeMultiCapability:
    """Fake provider implementing many capabilities at once.

    Used for tests that need a single instance under several sections
    (e.g. own-provider-path in ``locked()``).
    """

    provider_name: ClassVar[str] = "fake_multi"

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        circuit_state: CircuitState = CircuitState.CLOSED,
    ) -> None:
        """Build the fake — all method bodies are stubs that return empty data."""
        if provider_name is not None:
            self.provider_name = provider_name
        self.circuit = _make_circuit(circuit_state)
        self.closed = False

    def search(
        self,
        title: str,
        year: int | None = None,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[SearchResult]:
        """Return an empty list."""
        return []

    def get_movie(self, provider_id: str) -> MediaDetails:
        """Stub — never called in current tests."""
        raise RuntimeError("not configured")

    def get_tv(self, provider_id: str) -> MediaDetails:
        """Stub — never called in current tests."""
        raise RuntimeError("not configured")

    def get_episodes(self, series_id: str, season: int) -> list[EpisodeInfo]:
        """Return an empty episode list."""
        return []

    def get_artwork_urls(
        self,
        media_id: str,
        media_type: MediaType = MediaType.MOVIE,
    ) -> list[ArtworkItem]:
        """Return an empty artwork list."""
        return []

    def get_keywords(self, media_id: str, media_type: MediaType) -> list[str]:
        """Return an empty keyword list."""
        return []

    def get_videos(
        self,
        media_id: str,
        media_type: MediaType,
        language: str,
    ) -> list[Video]:
        """Return an empty video list."""
        return []

    def get_recommendations(
        self,
        media_id: str,
        media_type: MediaType,
    ) -> list[Recommendation]:
        """Return an empty recommendation list."""
        return []

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        """Return None — no rating configured by default."""
        return None

    def close(self) -> None:
        """Mark this fake as closed for cleanup-test assertions."""
        self.closed = True


# ---------------------------------------------------------------------------
# ProvidersConfig builders — one per ConfigIssue family + a minimal-valid case
# ---------------------------------------------------------------------------


def valid_minimal_config() -> ProvidersConfig:
    """Build a clean ProvidersConfig referencing only the ``fake_searchable`` fake."""
    return ProvidersConfig(
        Searchable={"fake_searchable": 1},
        TvDetailsProvider={"fake_searchable": 1},
    )


def config_with_unknown_provider() -> ProvidersConfig:
    """Build a config referencing a provider that has no class registered.

    The misspelled name ``"tmdbb"`` is close to a real provider name so the
    ``difflib.get_close_matches`` suggestion fires.
    """
    return ProvidersConfig(
        Searchable={"tmdbb": 1, "tmdb": 2},
    )


def config_with_empty_chain_section() -> ProvidersConfig:
    """Build a config with an explicitly empty MovieDetailsProvider section."""
    return ProvidersConfig(
        Searchable={"tmdb": 1},
        MovieDetailsProvider={},
    )


def config_with_locked_orphan() -> ProvidersConfig:
    """Build a config where TVDB is in chain but not in the artwork locked section."""
    return ProvidersConfig(
        Searchable={"tvdb": 1},
        ArtworkProvider={"tmdb": 1},
        # tvdb is a chain provider absent from ArtworkProvider — orphaned, since
        # there is no cross-provider translation path (API-TRANSPORT-03).
    )


def config_with_all_five_families() -> ProvidersConfig:
    """Build a config that triggers all five ConfigIssue families at once.

    - ``unknown_provider``: section references ``"nobody"`` (no class).
    - ``empty_chain_section``: MovieDetailsProvider is empty.
    - ``protocol_mismatch``: assumes TMDBClient lacks the EpisodeFetcher Protocol.
    - ``locked_capability_orphan``: tvdb is in chain but absent from artwork.
    - ``missing_credentials``: handled via env-stripping in the test, not via config.
    """
    return ProvidersConfig(
        Searchable={"nobody": 1, "tmdb": 2, "tvdb": 3},
        MovieDetailsProvider={},
        EpisodeFetcher={"tmdb": 1},
        TvDetailsProvider={"tvdb": 1},
        ArtworkProvider={"tmdb": 1},
    )


# ---------------------------------------------------------------------------
# Build-registry factory fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_event_bus() -> MockEventBus:
    """Return a fresh ``MockEventBus`` for each test."""
    return MockEventBus()


@pytest.fixture
def settings_stub() -> Any:
    """Return a minimal Settings-like stub with empty credentials.

    A ``SimpleNamespace`` is used because the registry's validation only
    accesses individual credential attributes via ``getattr``; the full
    pydantic-settings machinery is not needed for unit tests.
    """
    return SimpleNamespace(
        tmdb_api_key="dummy",
        tvdb_api_key="dummy",
        qbit_host="",
        qbit_port=0,
        qbit_username="",
        qbit_password="",
    )


@pytest.fixture
def cb_policy_stub() -> Any:
    """Return a minimal CircuitPolicy stub for registry construction.

    The fakes in this conftest carry their own circuit objects; the
    registry never reads through ``cb_policy`` when building fakes, so a
    plain ``SimpleNamespace`` suffices.
    """
    return SimpleNamespace(failure_threshold=3, cooldown_seconds=60.0)


@pytest.fixture
def build_registry(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Return a factory that builds a ProviderRegistry from supplied fakes.

    The factory monkeypatches ``_factory.build_providers`` so the
    registry's real constructor sees the ``fakes`` dict instead of
    importing real provider classes. It also clears the credential check
    by patching ``_validation._CRED_MAP`` so fake providers never trigger
    a ``missing_credentials`` issue.

    Returns:
        Callable ``(*, fakes, providers_config, event_bus=None, settings=None,
        cb_policy=None) -> ProviderRegistry``.
    """
    from personalscraper.api.metadata.registry import _factory, _validation

    def _factory_impl(
        *,
        fakes: dict[str, object],
        providers_config: ProvidersConfig,
        event_bus: object | None = None,
        settings: object | None = None,
        cb_policy: object | None = None,
    ) -> Any:
        # Default to MockEventBus per project architectural contract
        # (event-bus 0.14.0). Callers can pass a FailingEventBus to
        # test bus-failure behavior without propagation.
        if event_bus is None:
            event_bus = MockEventBus()
        from personalscraper.api.metadata.registry import ProviderRegistry

        # Patch build_providers to return fakes verbatim.
        def fake_build_providers(
            provider_names: list[str],
            settings_arg: object,
            cb_policy_arg: object,
            event_bus_arg: object,
        ) -> dict[str, object]:
            # Only return the fakes that were actually requested by the
            # config, mirroring real factory behaviour.
            return {name: fakes[name] for name in provider_names if name in fakes}

        monkeypatch.setattr(_factory, "build_providers", fake_build_providers)
        # Empty credentials map → no missing_credentials issues from fakes.
        monkeypatch.setattr(_validation, "_CRED_MAP", {})
        # Bypass empty-chain check — test configs only specify a subset of sections.
        monkeypatch.setattr(_validation, "_check_empty_chain_sections", lambda _: [])
        # Bypass protocol-mismatch check — test fakes don't implement all protocols.
        monkeypatch.setattr(_validation, "_check_protocol_mismatch", lambda *a: [])

        return ProviderRegistry(
            settings=settings if settings is not None else SimpleNamespace(),
            event_bus=event_bus,
            cb_policy=cb_policy if cb_policy is not None else SimpleNamespace(),
            providers_config=providers_config,
        )

    return _factory_impl
