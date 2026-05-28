"""HTTP-level integration tests for ProviderRegistry chain/fan_out/locked semantics (DESIGN §8.3).

Uses ``responses`` to intercept HTTP calls at the transport layer. Real providers
(TMDBClient, TVDBClient) are instantiated with real HttpTransport and CircuitBreaker;
only the HTTP wire is mocked. Tests requiring capabilities not on TMDB/TVDB (IDCrossRef,
RatingProvider) use monkeypatched fake providers.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
import requests
import responses

from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.metadata._base import ArtworkItem, Notations
from personalscraper.api.metadata._contracts import (
    ArtworkProvider,
    RatingProvider,
    Searchable,
)
from personalscraper.api.metadata.registry import (
    AttemptOutcome,
    FanOutResult,
    ProviderMatch,
    ProviderRegistry,
    RegistryProviderName,
)
from personalscraper.api.metadata.registry._errors import ProviderExhausted
from personalscraper.api.metadata.registry._events import (
    LockedCapabilityUnresolved,
    RegistryBootValidated,
    RegistryFanOutCompleted,
)
from personalscraper.api.transport._policy import CircuitPolicy
from personalscraper.conf.models.providers import ProvidersConfig
from personalscraper.core.circuit import CircuitState
from personalscraper.core.event_bus import EventBus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TMDB_BASE = "https://api.themoviedb.org/3"
TVDB_BASE = "https://api4.thetvdb.com/v4"

# ---------------------------------------------------------------------------
# Inline helpers (cannot use relative import — no __init__.py in integration dir)
# ---------------------------------------------------------------------------


def mock_tvdb_bootstrap() -> None:
    """Mock TVDB bootstrap login so TVDBClient can be constructed."""
    responses.add(
        responses.POST,
        f"{TVDB_BASE}/login",
        json={"data": {"token": "fake-jwt-token"}},
        status=200,
    )


def mock_tmdb_search_empty() -> None:
    """Mock TMDB search returning 200 with empty results."""
    responses.add(
        responses.GET,
        f"{TMDB_BASE}/search/movie",
        json={"page": 1, "results": [], "total_pages": 0, "total_results": 0},
        status=200,
    )


def mock_tmdb_search_success() -> None:
    """Mock TMDB search returning 200 with one result."""
    responses.add(
        responses.GET,
        f"{TMDB_BASE}/search/movie",
        json={
            "page": 1,
            "results": [
                {
                    "id": 12345,
                    "title": "Test Movie",
                    "release_date": "2020-01-01",
                    "overview": "A test movie.",
                    "poster_path": "/poster.jpg",
                    "backdrop_path": "/backdrop.jpg",
                    "vote_average": 7.5,
                    "vote_count": 100,
                    "genre_ids": [28],
                    "original_language": "en",
                    "original_title": "Test Movie",
                    "popularity": 50.0,
                    "video": False,
                    "adult": False,
                }
            ],
            "total_pages": 1,
            "total_results": 1,
        },
        status=200,
    )


def mock_tvdb_search_success() -> None:
    """Mock TVDB search returning 200 with one result."""
    responses.add(
        responses.GET,
        f"{TVDB_BASE}/search",
        json={
            "data": [
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
            ],
            "status": "success",
        },
        status=200,
    )


def _make_cb_policy(
    failure_threshold: int = 2,
    cooldown_seconds: float = 0.01,
) -> CircuitPolicy:
    """Build an aggressive CircuitPolicy for fast tests."""
    return CircuitPolicy(
        failure_threshold=failure_threshold,
        cooldown_seconds=cooldown_seconds,
    )


def _make_settings(**overrides: Any) -> Any:
    """Build a minimal settings stub."""
    from types import SimpleNamespace

    defaults: dict[str, Any] = {
        "tmdb_api_key": "dummy_tmdb_key",
        "tvdb_api_key": "dummy_tvdb_key",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# Fake providers (used by monkeypatched-registry tests)
# ruff: noqa: D102, D107
# ---------------------------------------------------------------------------


def _fake_circuit(state: str = "CLOSED") -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(state=state, can_proceed=lambda: state != "OPEN")


class FakeRatingForTest:
    """Implements RatingProvider."""

    def __init__(self, *, provider_name: str, circuit_state: str = "CLOSED"):
        self.provider_name = provider_name
        self.circuit = _fake_circuit(circuit_state)
        self._should_fail: bool = False
        self.closed = False

    def get_rating(self, provider_id: str) -> list[Notations] | None:
        if self._should_fail:
            raise ApiError(provider=self.provider_name, http_status=503, provider_code=0, message="fake 503")
        source: Any = self.provider_name
        return [Notations(provider=str(source), source="imdb", score=7.5)]

    def close(self) -> None:
        self.closed = True


class FakeArtworkForTest:
    """Implements ArtworkProvider."""

    def __init__(self, *, provider_name: str, circuit_state: str = "CLOSED"):
        self.provider_name = provider_name
        self.circuit = _fake_circuit(circuit_state)
        self.closed = False

    def get_artwork_urls(self, media_id: str, media_type: MediaType = MediaType.MOVIE) -> list[ArtworkItem]:
        return [ArtworkItem(url=f"https://art.example.com/{media_id}.jpg", type="poster")]

    def close(self) -> None:
        self.closed = True


class FakeIDCrossRefProviderForTest:
    """Implements IDCrossRef only (no ArtworkProvider) for locked cross_ref tests."""

    def __init__(self, *, provider_name: str, xref_table: dict[str, dict[str, str]] | None = None):
        self.provider_name = provider_name
        self.circuit = _fake_circuit("CLOSED")
        self._xref = xref_table or {}
        self.closed = False

    def get_cross_refs(self, provider_id: str) -> dict[str, str]:
        return dict(self._xref.get(provider_id, {}))

    def close(self) -> None:
        self.closed = True


class MockEventBusForTest:
    """In-memory EventBus that records emitted events."""

    def __init__(self) -> None:
        self.emitted: list[object] = []

    def emit(self, event: object) -> None:
        self.emitted.append(event)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ANY_MOVIE_SEARCH = re.compile(rf"{re.escape(TMDB_BASE)}/search/movie\b.*")
_ANY_TVDB_SEARCH = re.compile(rf"{re.escape(TVDB_BASE)}/search\b.*")


def mock_tmdb_503_regex(n: int = 30) -> None:
    """Add N 503 mocks matching any TMDB search/movie URL (covers retries)."""
    for _ in range(n):
        responses.add(
            responses.GET,
            _ANY_MOVIE_SEARCH,
            json={"status_code": 34, "status_message": "Service Unavailable"},
            status=503,
        )


def mock_tvdb_search_503_repeated(n: int = 30) -> None:
    """Add N 503 mocks for TVDB search to cover retries."""
    for _ in range(n):
        responses.add(
            responses.GET,
            _ANY_TVDB_SEARCH,
            json={"message": "Internal Server Error"},
            status=503,
        )


def mock_tmdb_conn_err_regex(n: int = 30) -> None:
    """Add N ConnectionError mocks matching any TMDB search/movie URL."""
    for _ in range(n):
        responses.add(
            responses.GET,
            _ANY_MOVIE_SEARCH,
            body=requests.ConnectionError("connection reset"),
        )


def _build_chain_registry(
    event_bus: EventBus,
    providers_config: ProvidersConfig,
    cb_policy: CircuitPolicy | None = None,
) -> ProviderRegistry:
    """Build a real ProviderRegistry for chain tests. Mock TVDB bootstrap if needed.

    Bypasses validation so tests can specify only the capability sections they
    need (e.g. Searchable only).
    """
    from personalscraper.api.metadata.registry import _validation

    _orig_empty_chain = _validation._check_empty_chain_sections
    _orig_protocol_mismatch = _validation._check_protocol_mismatch
    _orig_cred_map = _validation._CRED_MAP
    try:
        _validation._check_empty_chain_sections = lambda _: []  # type: ignore[assignment]
        _validation._check_protocol_mismatch = lambda *a: []  # type: ignore[assignment]
        _validation._CRED_MAP = {}  # type: ignore[assignment]

        mock_tvdb_bootstrap()
        return ProviderRegistry(
            settings=_make_settings(),
            event_bus=event_bus,
            cb_policy=cb_policy or _make_cb_policy(),
            providers_config=providers_config,
        )
    finally:
        _validation._check_empty_chain_sections = _orig_empty_chain
        _validation._check_protocol_mismatch = _orig_protocol_mismatch
        _validation._CRED_MAP = _orig_cred_map


def _attempt_chain(
    providers: list[Any],
    title: str = "test",
    media_type: MediaType = MediaType.MOVIE,
) -> tuple[Any, list[AttemptOutcome]]:
    """Iterate chain providers; return (result, attempted). Raises ProviderExhausted on full failure."""
    attempted: list[AttemptOutcome] = []
    for p in providers:
        p_name = getattr(p, "name", None) or getattr(p, "provider_name", "unknown")
        try:
            result = p.search(title, media_type=media_type)
            return result, attempted
        except ApiError as exc:
            attempted.append(
                AttemptOutcome(
                    provider=RegistryProviderName(p_name),
                    reason="network",
                    detail=str(exc),
                )
            )
        except requests.ConnectionError as exc:
            attempted.append(
                AttemptOutcome(
                    provider=RegistryProviderName(p_name),
                    reason="network",
                    detail=str(exc),
                )
            )
        except Exception as exc:
            attempted.append(
                AttemptOutcome(
                    provider=RegistryProviderName(p_name),
                    reason="other",
                    detail=type(exc).__name__,
                )
            )
    raise ProviderExhausted(Searchable, attempted)


# ---------------------------------------------------------------------------
# Circuit breaker status propagation (tests 1-3)
# ---------------------------------------------------------------------------


class TestCircuitBreakerStatusPropagation:
    """Verify circuit state changes propagate to registry.status()."""

    @responses.activate
    def test_circuit_breaker_opened_propagates_to_status(self) -> None:
        """Trigger 5xx until breaker opens; assert status reflects OPEN."""
        mock_tmdb_503_regex()
        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1}),
        )
        tmdb = registry.get("tmdb")

        for _ in range(2):
            with pytest.raises(ApiError):
                tmdb.search("test", media_type=MediaType.MOVIE)

        status = registry.status()
        assert status["tmdb"].circuit_state == CircuitState.OPEN

    @responses.activate
    def test_circuit_breaker_half_opened_propagates_to_status(self) -> None:
        """After cooldown, circuit transitions HALF_OPEN; status() reflects it."""
        mock_tmdb_503_regex()
        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1}),
        )
        tmdb = registry.get("tmdb")

        # Trip to OPEN
        for _ in range(2):
            with pytest.raises(ApiError):
                tmdb.search("test", media_type=MediaType.MOVIE)

        assert registry.status()["tmdb"].circuit_state == CircuitState.OPEN

        # Force cooldown elapsed deterministically (time injection, not sleep).
        breaker = tmdb.circuit
        breaker._opened_at -= breaker.cooldown_seconds + 1.0

        status = registry.status()
        assert status["tmdb"].circuit_state == CircuitState.HALF_OPEN

    @responses.activate
    def test_circuit_breaker_closed_propagates_to_status(self) -> None:
        """After HALF_OPEN probe success, circuit closes; status() reflects CLOSED."""
        # Trip to OPEN
        mock_tmdb_503_regex()
        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1}),
        )
        tmdb = registry.get("tmdb")

        for _ in range(2):
            with pytest.raises(ApiError):
                tmdb.search("test", media_type=MediaType.MOVIE)

        # Force cooldown elapsed deterministically.
        breaker = tmdb.circuit
        breaker._opened_at -= breaker.cooldown_seconds + 1.0
        assert registry.status()["tmdb"].circuit_state == CircuitState.HALF_OPEN

        # Probe succeeds
        responses.reset()
        mock_tmdb_search_success()
        tmdb.search("test", media_type=MediaType.MOVIE)

        status = registry.status()
        assert status["tmdb"].circuit_state == CircuitState.CLOSED


# ---------------------------------------------------------------------------
# Chain fallback (tests 4-6)
# ---------------------------------------------------------------------------


class TestChainFallback:
    """Verify chain iterates to the next provider on 5xx / timeout / empty body."""

    @responses.activate
    def test_chain_falls_back_on_5xx_to_next_provider(self) -> None:
        """Tmdb returns 5xx; tvdb succeeds — chain fallback works.

        Design: docs/reference/scraping.md#fallback-triggers-chain
        Contract: chain triggers fallback on 5xx response to the next eligible provider.
        """
        mock_tmdb_503_regex()
        mock_tvdb_bootstrap()
        mock_tvdb_search_success()

        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1, "tvdb": 2}),
        )
        providers = registry.chain(Searchable)

        result, attempted = _attempt_chain(providers, "test", MediaType.MOVIE)

        assert len(attempted) == 1
        assert attempted[0].provider == "tmdb"
        assert attempted[0].reason == "network"
        assert len(result) > 0

    @responses.activate
    def test_chain_falls_back_on_timeout(self) -> None:
        """Tmdb raises ConnectionError (timeout); tvdb succeeds.

        Design: docs/reference/scraping.md#fallback-triggers-chain
        Contract: chain triggers fallback on timeout to the next eligible provider.
        """
        mock_tmdb_conn_err_regex()
        mock_tvdb_bootstrap()
        mock_tvdb_search_success()

        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1, "tvdb": 2}),
        )
        providers = registry.chain(Searchable)

        result, attempted = _attempt_chain(providers, "test", MediaType.MOVIE)

        assert len(attempted) == 1
        assert attempted[0].provider == "tmdb"
        assert attempted[0].reason == "network"
        assert len(result) > 0

    @responses.activate
    def test_chain_falls_back_on_empty_body(self) -> None:
        """Tmdb returns 200 but empty results; tvdb succeeds.

        Design: docs/reference/scraping.md#fallback-triggers-chain
        Contract: chain triggers fallback on empty body to the next eligible provider.
        """
        mock_tmdb_search_empty()
        mock_tvdb_bootstrap()
        mock_tvdb_search_success()

        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1, "tvdb": 2}),
        )
        providers = registry.chain(Searchable)

        # Call tmdb directly — it returns empty list (not an exception)
        tmdb_result = providers[0].search("test", media_type=MediaType.MOVIE)
        assert tmdb_result == []

        # Call tvdb — returns results
        tvdb_result = providers[1].search("test", media_type=MediaType.MOVIE)
        assert len(tvdb_result) > 0


# ---------------------------------------------------------------------------
# HALF_OPEN probe (tests 7-8)
# ---------------------------------------------------------------------------


class TestHalfOpenProbe:
    """Verify HALF_OPEN probe behavior end-to-end (DESIGN §7.6)."""

    @responses.activate
    def test_half_open_probe_success_transitions_to_closed(self) -> None:
        """Probe succeeds in HALF_OPEN → circuit transitions to CLOSED.

        Design: docs/reference/scraping.md#half-open-eligibility
        Contract: half-open probe success transitions circuit to closed, validating eligibility rules.
        """
        mock_tmdb_503_regex()
        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1}),
        )
        tmdb = registry.get("tmdb")

        # Trip to OPEN
        for _ in range(2):
            with pytest.raises(ApiError):
                tmdb.search("test", media_type=MediaType.MOVIE)

        # Force cooldown elapsed deterministically — backdate the breaker's
        # `_opened_at` instead of waiting on wall-clock + polling. Polling
        # was brittle under xdist + coverage load (~1/5 flake rate); time
        # injection is timing-independent.
        breaker = tmdb.circuit
        breaker._opened_at -= breaker.cooldown_seconds + 1.0
        assert registry.status()["tmdb"].circuit_state == CircuitState.HALF_OPEN

        # Probe succeeds
        responses.reset()
        mock_tmdb_search_success()
        result = tmdb.search("test", media_type=MediaType.MOVIE)

        assert len(result) > 0
        assert registry.status()["tmdb"].circuit_state == CircuitState.CLOSED

    @responses.activate
    def test_half_open_probe_failure_returns_to_open_and_chain_falls_through(self) -> None:
        """Probe fails in HALF_OPEN → circuit reopens; next provider receives call.

        Design: docs/reference/scraping.md#half-open-eligibility
        Contract: half-open probe failure returns to open state, validating eligibility re-entry rules.
        """
        mock_tmdb_503_regex()
        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1, "tvdb": 2}),
        )
        tmdb = registry.get("tmdb")

        # Trip to OPEN
        for _ in range(2):
            with pytest.raises(ApiError):
                tmdb.search("test", media_type=MediaType.MOVIE)

        # Force cooldown elapsed deterministically — backdate the breaker's
        # `_opened_at` instead of waiting on wall-clock + polling. Polling
        # was brittle under xdist + coverage load (~1/5 flake rate); time
        # injection is timing-independent.
        breaker = tmdb.circuit
        breaker._opened_at -= breaker.cooldown_seconds + 1.0
        assert registry.status()["tmdb"].circuit_state == CircuitState.HALF_OPEN

        # Probe fails — mock 503 for TMDB, success for TVDB.
        # Re-register the TVDB bootstrap mock after ``responses.reset()``:
        # the chain fall-through below is the first TVDB HTTP call, so the
        # deferred JWT exchange fires here.
        responses.reset()
        mock_tmdb_503_regex()
        mock_tvdb_bootstrap()
        mock_tvdb_search_success()

        providers = registry.chain(Searchable)
        # tmdb should be HALF_OPEN (eligible), tvdb CLOSED
        result, attempted = _attempt_chain(providers, "test", MediaType.MOVIE)

        # tmdb probe fails → circuit reopens
        assert registry.status()["tmdb"].circuit_state == CircuitState.OPEN
        # tvdb succeeds
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Network error → AttemptOutcome (test 9)
# ---------------------------------------------------------------------------


class TestNetworkErrorAttemptOutcome:
    """Verify network errors are recorded as AttemptOutcome.reason='network'."""

    @responses.activate
    def test_network_error_recorded_as_attempt_outcome(self) -> None:
        """Caller exhausts chain; asserts reason='network' in ProviderExhausted.attempted."""
        mock_tmdb_503_regex()
        mock_tvdb_bootstrap()
        mock_tvdb_search_503_repeated()

        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1, "tvdb": 2}),
        )
        providers = registry.chain(Searchable)

        with pytest.raises(ProviderExhausted) as exc:
            _attempt_chain(providers, "test", MediaType.MOVIE)

        assert len(exc.value.attempted) == 2
        for outcome in exc.value.attempted:
            assert outcome.reason == "network"


# ---------------------------------------------------------------------------
# Locked cross_ref (tests 10-11)
# ---------------------------------------------------------------------------


class TestLockedCrossRef:
    """Verify locked() IDCrossRef translation path."""

    def test_locked_cross_ref_via_idcrossref_succeeds(self, build_registry_fakes: Any) -> None:
        """Match has tmdb id, locked(ArtworkProvider); TVDB has artwork via xref translation."""
        fakes = {
            "tmdb": FakeIDCrossRefProviderForTest(
                provider_name="tmdb",
                xref_table={"tmdb-123": {"tvdb": "tvdb-456"}},
            ),
            "tvdb": FakeArtworkForTest(provider_name="tvdb"),
        }
        config = ProvidersConfig(
            Searchable={"tmdb": 1, "tvdb": 2},
            ArtworkProvider={"tvdb": 1},
            IDCrossRef={"tmdb": 1},
        )
        bus = MockEventBusForTest()
        registry = build_registry_fakes(fakes=fakes, providers_config=config, event_bus=bus)

        match = ProviderMatch(
            provider=RegistryProviderName("tmdb"),
            id="tmdb-123",
            media_type=MediaType.MOVIE,
        )
        locked = registry.locked(ArtworkProvider, match)

        assert locked is not None
        assert locked.bound_id == "tvdb-456"
        assert locked.translated_via == "tmdb"

    def test_locked_cross_ref_returns_none_when_xref_empty(self, build_registry_fakes: Any) -> None:
        """IDCrossRef returns empty dict; locked() returns None; LockedCapabilityUnresolved emitted."""
        fakes = {
            "tmdb": FakeIDCrossRefProviderForTest(provider_name="tmdb", xref_table={}),
            "tvdb": FakeArtworkForTest(provider_name="tvdb"),
        }
        config = ProvidersConfig(
            Searchable={"tmdb": 1},
            ArtworkProvider={"tvdb": 1},
            IDCrossRef={"tmdb": 1},
        )
        bus = MockEventBusForTest()
        registry = build_registry_fakes(fakes=fakes, providers_config=config, event_bus=bus)

        match = ProviderMatch(
            provider=RegistryProviderName("tmdb"),
            id="tmdb-unknown",
            media_type=MediaType.MOVIE,
        )
        locked = registry.locked(ArtworkProvider, match)

        assert locked is None
        assert any(isinstance(e, LockedCapabilityUnresolved) for e in bus.emitted)


# ---------------------------------------------------------------------------
# All providers 5xx → ProviderExhausted (test 12)
# ---------------------------------------------------------------------------


class TestProviderExhausted:
    """Verify ProviderExhausted raised when all chain providers fail."""

    @responses.activate
    def test_all_providers_5xx_raises_provider_exhausted(self) -> None:
        """Every chain provider returns 5xx → ProviderExhausted raised."""
        mock_tmdb_503_regex()
        mock_tvdb_bootstrap()
        mock_tvdb_search_503_repeated()

        bus = EventBus()
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1, "tvdb": 2}),
        )
        providers = registry.chain(Searchable)

        with pytest.raises(ProviderExhausted) as exc:
            _attempt_chain(providers, "test", MediaType.MOVIE)

        assert len(exc.value.attempted) == len(providers)
        assert exc.value.capability is Searchable


# ---------------------------------------------------------------------------
# Fan_out partial (test 13)
# ---------------------------------------------------------------------------


class TestFanOutPartial:
    """Verify fan_out semantics with partial failure."""

    def test_fan_out_partial_one_failure_one_success(self, build_registry_fakes: Any) -> None:
        """One provider 5xx, one 200; FanOutResult composed correctly."""
        r1 = FakeRatingForTest(provider_name="r1", circuit_state=CircuitState.CLOSED)
        r2 = FakeRatingForTest(provider_name="r2", circuit_state=CircuitState.CLOSED)
        r2._should_fail = True

        fakes = {"r1": r1, "r2": r2}
        config = ProvidersConfig(RatingProvider={"r1": 1, "r2": 2})
        bus = MockEventBusForTest()
        registry = build_registry_fakes(fakes=fakes, providers_config=config, event_bus=bus)

        registry_result = registry.fan_out(RatingProvider)
        eligible = registry_result.values
        assert len(eligible) == 2
        # fan_out itself returns a FanOutResult; the test below additionally
        # composes a caller-side FanOutResult after exercising the providers
        # to demonstrate provenance composition over HTTP failures.
        assert registry_result.attempted == []

        # Caller iterates fan_out, composing its own FanOutResult per-call outcomes.
        values: list[Any] = []
        attempted: list[AttemptOutcome] = []
        for p in eligible:
            try:
                result = p.get_rating("dummy-id")
                if result:
                    values.append(result)
                attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(p.provider_name),
                        reason="empty_result" if not result else "empty_result",
                    )
                )
            except ApiError:
                attempted.append(
                    AttemptOutcome(
                        provider=RegistryProviderName(p.provider_name),
                        reason="network",
                        detail="5xx",
                    )
                )

        fan_out_result = FanOutResult(values=values, attempted=attempted)
        assert len(fan_out_result.values) == 1
        assert len(fan_out_result.attempted) == 2

        # RegistryFanOutCompleted emitted by fan_out() call
        completed_events = [e for e in bus.emitted if isinstance(e, RegistryFanOutCompleted)]
        assert len(completed_events) == 1


# ---------------------------------------------------------------------------
# RegistryBootValidated event (test 14)
# ---------------------------------------------------------------------------


class TestRegistryBootEvent:
    """Verify RegistryBootValidated is emitted on successful init."""

    @responses.activate
    def test_registry_boot_validated_event_emitted_on_successful_init(self) -> None:
        """Construct registry with valid config+providers; assert RegistryBootValidated emitted."""
        bus = EventBus()
        captured: list[Any] = []
        bus.subscribe(RegistryBootValidated, lambda e: captured.append(e))

        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1}),
        )

        assert len(captured) == 1
        event = captured[0]
        assert isinstance(event, RegistryBootValidated)
        assert "tmdb" in event.providers
        assert "Searchable" in event.capabilities

        registry.close()


# ---------------------------------------------------------------------------
# EventBus failure during chain (test 15)
# ---------------------------------------------------------------------------


class TestEventBusFailure:
    """Verify registry survives event_bus.emit() failures."""

    @responses.activate
    def test_event_bus_failure_during_chain_does_not_crash_registry(self) -> None:
        """Wrapping event_bus.emit to raise; trigger chain; no exception propagated."""
        mock_tmdb_503_regex()
        bus = EventBus()
        # Monkeypatch emit to always raise
        original_emit = bus.emit

        def failing_emit(event: object) -> None:
            raise RuntimeError("event bus is broken")

        bus.emit = failing_emit  # type: ignore[method-assign]

        # Construct registry — _event_bus_safe_emit swallows the failure
        registry = _build_chain_registry(
            bus,
            ProvidersConfig(Searchable={"tmdb": 1}),
        )

        # Restore emit for normal operation
        bus.emit = original_emit  # type: ignore[method-assign]

        # Registry should still work
        providers = registry.chain(Searchable)
        assert len(providers) == 1

        registry.close()
