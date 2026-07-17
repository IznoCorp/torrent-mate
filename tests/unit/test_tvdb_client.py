"""Unit tests for TVDBClient method bodies (search, get_*, helpers).

The bootstrap login (POST /login) is **deferred** since Phase 14 of
``feat/registry``: construction is network-free and the JWT exchange
fires on the first real HTTP call. For per-method unit tests we still
bypass it by constructing the client via ``__new__`` and injecting a
MagicMock transport (the lazy ``_transport`` property has a setter that
preserves this pattern).

The bootstrap path itself is exercised below via a full ``TVDBClient(...)``
construction followed by a first method call — that's what now triggers
the ``POST /login``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.metadata._base import (
    ArtworkItem,
    MediaDetails,
    SearchResult,
    SeasonDetails,
    Video,
)
from personalscraper.api.metadata.tvdb import TVDBClient
from personalscraper.core.event_bus import EventBus

SAMPLES = Path("docs/reference/_samples/tvdb")


def _load(name: str) -> Any:
    """Load a golden TVDB sample JSON from docs/reference/_samples/tvdb."""
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def _make_client(transport: MagicMock) -> TVDBClient:
    """Construct a TVDBClient bypassing the bootstrap login.

    Args:
        transport: Mock HttpTransport injected as the main transport.

    Returns:
        A fully wired TVDBClient with the supplied transport.
    """
    client = TVDBClient.__new__(TVDBClient)
    client._api_key = "fake"  # type: ignore[attr-defined]
    client._tvdb_lang = "fra"  # type: ignore[attr-defined]
    client._language = "fr-FR"  # type: ignore[attr-defined]
    client._transport = transport  # type: ignore[attr-defined]
    return client


@pytest.fixture()
def transport() -> MagicMock:
    """A MagicMock standing in for HttpTransport."""
    return MagicMock()


@pytest.fixture()
def client(transport: MagicMock) -> TVDBClient:
    """TVDBClient instance with a mocked transport (no bootstrap)."""
    return _make_client(transport)


# ── bootstrap login (full __init__) ───────────────────────────────────


class TestBootstrapLogin:
    """Cover the deferred bootstrap path: POST /login, JWT extraction, type guard.

    Since Phase 14, ``TVDBClient(...)`` is pure-Python — no HTTP fires.
    The bootstrap exchange happens on first real HTTP call. These tests
    construct the client, then exercise a method to trigger ``/login``.
    """

    def test_init_does_not_fire_http(self) -> None:
        """Construction itself MUST NOT call HttpTransport (deferred bootstrap)."""
        with patch("personalscraper.api.metadata.tvdb.HttpTransport") as MockTransport:
            TVDBClient("fake-api-key", event_bus=EventBus())
            # Zero HTTP transport instantiations at construction time.
            MockTransport.assert_not_called()

    def test_first_call_logs_in_and_stores_jwt(self) -> None:
        """A successful /login response yields a fully wired client on first call."""
        login_resp = {"status": "success", "data": {"token": "jwt-token"}}
        with patch("personalscraper.api.metadata.tvdb.HttpTransport") as MockTransport:
            bootstrap = MagicMock()
            bootstrap.__enter__.return_value = bootstrap
            bootstrap.__exit__.return_value = None
            bootstrap.post.return_value = login_resp
            main = MagicMock()
            # First call (bootstrap) returns context-managed bootstrap; second is main transport
            MockTransport.side_effect = [bootstrap, main]

            c = TVDBClient("fake-api-key", event_bus=EventBus())
            # No HTTP yet.
            MockTransport.assert_not_called()
            # Touching the lazy transport triggers bootstrap.
            assert c._transport is main

        bootstrap.post.assert_called_once_with("/login", data={"apikey": "fake-api-key"})

    def test_first_call_non_dict_login_response_raises(self) -> None:
        """A non-dict /login response raises TypeError on first method call."""
        with patch("personalscraper.api.metadata.tvdb.HttpTransport") as MockTransport:
            bootstrap = MagicMock()
            bootstrap.__enter__.return_value = bootstrap
            bootstrap.__exit__.return_value = None
            bootstrap.post.return_value = ["unexpected"]
            MockTransport.return_value = bootstrap

            # Construction MUST succeed even with a malformed /login response —
            # the bogus payload is only inspected on first transport access.
            c = TVDBClient("fake-api-key", event_bus=EventBus())
            with pytest.raises(TypeError, match="Expected dict"):
                _ = c._transport

    def test_bootstrap_is_idempotent(self) -> None:
        """Second access to _transport reuses the cached main transport."""
        login_resp = {"status": "success", "data": {"token": "jwt-token"}}
        with patch("personalscraper.api.metadata.tvdb.HttpTransport") as MockTransport:
            bootstrap = MagicMock()
            bootstrap.__enter__.return_value = bootstrap
            bootstrap.__exit__.return_value = None
            bootstrap.post.return_value = login_resp
            main = MagicMock()
            MockTransport.side_effect = [bootstrap, main]

            c = TVDBClient("fake-api-key", event_bus=EventBus())
            first = c._transport
            second = c._transport
            assert first is second is main
            # Only the bootstrap + main pair were ever built (two calls total).
            assert MockTransport.call_count == 2


# ── policy + circuit property ─────────────────────────────────────────


class TestPolicyAndCircuit:
    """Cover the classmethod policy() and the circuit property."""

    def test_policy_returns_transport_policy(self) -> None:
        """policy() builds a TransportPolicy using TVDB defaults."""
        p = TVDBClient.policy("jwt-token")
        assert p.base_url == "https://api4.thetvdb.com/v4"
        assert p.timeout_seconds == 15.0

    def test_policy_accepts_custom_circuit(self) -> None:
        """A custom CircuitPolicy override is honoured."""
        from personalscraper.api.transport._policy import CircuitPolicy

        custom = CircuitPolicy(failure_threshold=99, cooldown_seconds=1.0)
        p = TVDBClient.policy("jwt", circuit=custom)
        assert p.circuit is custom

    def test_circuit_property(self, client: TVDBClient, transport: MagicMock) -> None:
        """Circuit property exposes the underlying transport's circuit breaker."""
        assert client.circuit is transport._circuit


# ── _get / _get_dict envelope helpers ─────────────────────────────────


class TestGetHelpers:
    """Direct exercise of the _get / _get_dict envelope helpers."""

    def test_get_unwraps_envelope(self, client: TVDBClient, transport: MagicMock) -> None:
        """_get unwraps {status: success, data: ...}."""
        transport.get.return_value = {"status": "success", "data": {"foo": "bar"}}
        assert client._get("/anything") == {"foo": "bar"}

    def test_get_non_dict_raises(self, client: TVDBClient, transport: MagicMock) -> None:
        """A non-dict raw response from the transport raises TypeError."""
        transport.get.return_value = ["bad", "shape"]
        with pytest.raises(TypeError, match="Expected dict"):
            client._get("/x")

    def test_get_dict_rejects_list_payload(self, client: TVDBClient, transport: MagicMock) -> None:
        """_get_dict raises when the unwrapped payload is a list."""
        transport.get.return_value = {"status": "success", "data": ["a", "b"]}
        with pytest.raises(TypeError, match="Expected dict from"):
            client._get_dict("/some/list-endpoint")

    def test_get_dict_returns_dict(self, client: TVDBClient, transport: MagicMock) -> None:
        """_get_dict returns the unwrapped dict on the happy path."""
        transport.get.return_value = {"status": "success", "data": {"k": 1}}
        assert client._get_dict("/x") == {"k": 1}


# ── map_language ──────────────────────────────────────────────────────


class TestMapLanguageMethod:
    """The instance ``map_language`` method delegates to the parser helper."""

    def test_two_char_to_three(self, client: TVDBClient) -> None:
        """``fr`` → ``fra``."""
        assert client.map_language("fr") == "fra"

    def test_unknown_falls_back_to_eng(self, client: TVDBClient) -> None:
        """Unknown 2-char codes fall back to ``eng``."""
        assert client.map_language("xx") == "eng"


# ── search dispatcher (Protocol) ──────────────────────────────────────


class TestSearchDispatch:
    """search() routes by media_type — series for tv, movie otherwise."""

    def test_search_series_routes(self, client: TVDBClient, transport: MagicMock) -> None:
        """media_type='tv' goes through search_series."""
        transport.get.return_value = _load("search_series.json")
        results = client.search("Breaking Bad", year=2008, media_type="tv")
        assert all(isinstance(r, SearchResult) for r in results)
        # Endpoint is /search regardless; verify the params type=series
        call = transport.get.call_args
        assert call.args[0] == "/search"
        assert call.kwargs["params"]["type"] == "series"
        assert call.kwargs["params"]["year"] == "2008"

    def test_search_movie_routes(self, client: TVDBClient, transport: MagicMock) -> None:
        """media_type='movie' (default) goes through search_movie."""
        transport.get.return_value = _load("search_movie.json")
        client.search("Inception", media_type="movie")
        call = transport.get.call_args
        assert call.args[0] == "/search"
        assert call.kwargs["params"]["type"] == "movie"


# ── search_series / search_movie ──────────────────────────────────────


class TestSearchSeries:
    """search_series: params, year, non-list payload fallback."""

    def test_year_param(self, client: TVDBClient, transport: MagicMock) -> None:
        """Year is sent as a string."""
        transport.get.return_value = _load("search_series.json")
        client.search_series("Breaking Bad", year=2008)
        call = transport.get.call_args
        assert call.kwargs["params"]["year"] == "2008"

    def test_non_list_data_returns_empty(self, client: TVDBClient, transport: MagicMock) -> None:
        """Unwrapped data that isn't a list yields []."""
        transport.get.return_value = {"status": "success", "data": {"unexpected": "shape"}}
        assert client.search_series("X") == []

    def test_parses_results(self, client: TVDBClient, transport: MagicMock) -> None:
        """Happy path: each item parsed into SearchResult."""
        transport.get.return_value = _load("search_series.json")
        results = client.search_series("Breaking Bad")
        assert len(results) >= 1
        assert results[0].provider == "tvdb"


class TestSearchMovieTvdb:
    """search_movie: params, year, non-list payload fallback."""

    def test_year_param(self, client: TVDBClient, transport: MagicMock) -> None:
        """Year is sent as a string."""
        transport.get.return_value = {"status": "success", "data": []}
        client.search_movie("Inception", year=2010)
        call = transport.get.call_args
        assert call.kwargs["params"]["year"] == "2010"
        assert call.kwargs["params"]["type"] == "movie"

    def test_non_list_data_returns_empty(self, client: TVDBClient, transport: MagicMock) -> None:
        """Non-list payload yields []."""
        transport.get.return_value = {"status": "success", "data": {"foo": "bar"}}
        assert client.search_movie("X") == []

    def test_parses_results(self, client: TVDBClient, transport: MagicMock) -> None:
        """Happy path returns SearchResult objects from parser."""
        transport.get.return_value = _load("search_movie.json")
        results = client.search_movie("Inception")
        assert all(isinstance(r, SearchResult) for r in results)

    def test_query_is_nfc_normalized(self, client: TVDBClient, transport: MagicMock) -> None:
        """NFD-decomposed titles are NFC-normalized before hitting TVDB.

        Same root cause as the TMDB client: NFD folder names from the macOS /
        NTFS-via-macFUSE filesystem fail to match the provider's NFC-indexed
        titles, returning zero results for accented titles.
        """
        import unicodedata

        transport.get.return_value = {"status": "success", "data": []}
        nfd = unicodedata.normalize("NFD", "Astérix")
        assert not unicodedata.is_normalized("NFC", nfd), "test setup must pass NFD"

        client.search_movie(nfd, year=2014)

        sent = transport.get.call_args.kwargs["params"]["query"]
        assert unicodedata.is_normalized("NFC", sent), "query sent to TVDB must be NFC"
        assert sent == "Astérix"


# ── get_details dispatcher ────────────────────────────────────────────


class TestGetDetailsDispatchTvdb:
    """get_details delegates to get_series / get_movie based on media_type."""

    def test_tv_details(self, client: TVDBClient, transport: MagicMock) -> None:
        """media_type='tv' calls /series/{id}/extended."""
        transport.get.return_value = _load("series_extended.json")
        md = client.get_details("81189", media_type="tv")
        assert isinstance(md, MediaDetails)
        assert transport.get.call_args_list[0].args[0] == "/series/81189/extended"

    def test_movie_details(self, client: TVDBClient, transport: MagicMock) -> None:
        """media_type='movie' calls /movies/{id}/extended."""
        transport.get.return_value = _load("movie_extended.json")
        md = client.get_details("12345", media_type="movie")
        assert isinstance(md, MediaDetails)
        assert transport.get.call_args_list[0].args[0] == "/movies/12345/extended"


# ── get_series / get_movie ────────────────────────────────────────────


class TestGetSeriesAndMovie:
    """get_series and get_movie hit /extended endpoints."""

    def test_get_series_endpoint(self, client: TVDBClient, transport: MagicMock) -> None:
        """get_series → /series/{id}/extended, then the fra translation overlay."""
        transport.get.return_value = _load("series_extended.json")
        md = client.get_series(81189)
        assert isinstance(md, MediaDetails)
        assert md.title == "Breaking Bad"
        called_paths = [c.args[0] for c in transport.get.call_args_list]
        assert called_paths == [
            "/series/81189/extended",
            "/series/81189/translations/fra",
        ]

    def test_get_movie_endpoint(self, client: TVDBClient, transport: MagicMock) -> None:
        """get_movie → /movies/{id}/extended, then the fra translation overlay."""
        transport.get.return_value = _load("movie_extended.json")
        md = client.get_movie(12345)
        assert isinstance(md, MediaDetails)
        called_paths = [c.args[0] for c in transport.get.call_args_list]
        assert called_paths == [
            "/movies/12345/extended",
            "/movies/12345/translations/fra",
        ]

    def test_get_series_applies_configured_language_translation(self, client: TVDBClient, transport: MagicMock) -> None:
        """A non-empty fra translation replaces the default-language title/overview.

        Regression (2026-07-17): « Disparues : Le tueur de Long Island » exists
        on TVDB (series 459609) but the NFO got the English default name — the
        client stored its configured language and never applied it.
        """
        extended = _load("series_extended.json")
        translation = {
            "status": "success",
            "data": {
                "name": "Disparues : Le tueur de Long Island",
                "overview": "Résumé en français.",
                "language": "fra",
            },
        }
        transport.get.side_effect = [extended, translation]
        md = client.get_series(459609)
        assert md.title == "Disparues : Le tueur de Long Island"
        assert md.overview == "Résumé en français."

    def test_get_series_keeps_default_when_translation_missing(self, client: TVDBClient, transport: MagicMock) -> None:
        """A 404 on /translations/{lang} keeps the default-language payload (fail-soft)."""
        from personalscraper.api._contracts import ApiError

        extended = _load("series_extended.json")
        transport.get.side_effect = [
            extended,
            ApiError(provider="tvdb", http_status=404, message="no translation"),
        ]
        md = client.get_series(81189)
        assert md.title == "Breaking Bad"

    def test_get_series_ignores_empty_translation_fields(self, client: TVDBClient, transport: MagicMock) -> None:
        """Blank/absent translated fields never overwrite the default values."""
        extended = _load("series_extended.json")
        translation = {"status": "success", "data": {"name": "   ", "language": "fra"}}
        transport.get.side_effect = [extended, translation]
        md = client.get_series(81189)
        assert md.title == "Breaking Bad"


# ── get_artwork_urls (already partly covered in test_tvdb_artwork_endpoint) ──


class TestGetArtworkUrlsTvdb:
    """Validate the parsing path for both media types."""

    def test_returns_artwork_items(self, client: TVDBClient, transport: MagicMock) -> None:
        """Artworks are parsed into ArtworkItems."""
        transport.get.return_value = {
            "status": "success",
            "data": {"artworks": [{"type": 2, "image": "https://x/p.jpg"}]},
        }
        items = client.get_artwork_urls("999", media_type="movie")
        assert len(items) == 1
        assert isinstance(items[0], ArtworkItem)


# ── get_season / get_series_episodes (pagination) ─────────────────────


class TestGetSeriesEpisodes:
    """Covers the pagination loop in get_series_episodes."""

    def test_single_page_no_next(self, client: TVDBClient, transport: MagicMock) -> None:
        """A single-page response (links.next=None) terminates the loop."""
        transport.get.return_value = _load("episodes_default.json")
        sd = client.get_series_episodes(81189, 1)
        assert isinstance(sd, SeasonDetails)
        assert sd.tv_id == "81189"
        assert sd.season_number == 1
        assert len(sd.episodes) > 0
        # Single GET call
        assert transport.get.call_count == 1

    def test_multi_page_pagination(self, client: TVDBClient, transport: MagicMock) -> None:
        """When links.next is non-empty, the loop fetches additional pages."""
        page0 = {
            "status": "success",
            "data": {
                "episodes": [{"number": 1, "name": "E1", "seasonNumber": 1}],
                "links": {"next": "https://api/.../page=1"},
            },
        }
        page1 = {
            "status": "success",
            "data": {
                "episodes": [{"number": 2, "name": "E2", "seasonNumber": 1}],
                "links": {"next": None},
            },
        }
        transport.get.side_effect = [page0, page1]
        sd = client.get_series_episodes(1, 1)
        assert len(sd.episodes) == 2
        assert transport.get.call_count == 2

    def test_get_season_delegates_to_episodes(self, client: TVDBClient, transport: MagicMock) -> None:
        """The Protocol-level get_season calls get_series_episodes via int coercion."""
        transport.get.return_value = _load("episodes_default.json")
        sd = client.get_season("81189", 1)
        assert sd.tv_id == "81189"

    def test_no_links_terminates(self, client: TVDBClient, transport: MagicMock) -> None:
        """Missing/empty links.next ends pagination after first page."""
        transport.get.return_value = {
            "status": "success",
            "data": {"episodes": [], "links": {}},
        }
        sd = client.get_series_episodes(1, 1)
        assert sd.episodes == []
        assert transport.get.call_count == 1


# ── get_videos ────────────────────────────────────────────────────────


class TestGetVideosTvdb:
    """get_videos parses trailers from extended responses."""

    def test_extracts_trailers(self, client: TVDBClient, transport: MagicMock) -> None:
        """Trailers list is mapped through parse_videos."""
        transport.get.return_value = {
            "status": "success",
            "data": {
                "trailers": [
                    {"id": 1, "url": "https://www.youtube.com/watch?v=ABC123"},
                ],
            },
        }
        vids = client.get_videos("12345", media_type="movie", language="eng")
        assert len(vids) == 1
        assert isinstance(vids[0], Video)
        assert vids[0].key == "ABC123"


# ── get_keywords / get_notations not supported ────────────────────────


class TestUnsupportedCapabilities:
    """TVDB does not expose keywords or rating notations."""

    def test_get_keywords_raises(self, client: TVDBClient) -> None:
        """get_keywords raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="keywords"):
            client.get_keywords("1", "movie")

    def test_get_notations_raises(self, client: TVDBClient) -> None:
        """get_notations raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="notations"):
            client.get_notations("1", "movie")


class TestCircuitPropertyIsHttpFree:
    """Phase 22 / DESIGN §7.6: reading ``TVDBClient.circuit`` is HTTP-free.

    Pre-bootstrap, the breaker doesn't exist yet (it's constructed by
    :meth:`_ensure_transport` together with the main HttpTransport), so
    the property returns ``None``. Post-bootstrap, the property returns
    the same instance the transport uses — no extra HTTP, no extra
    instantiation.
    """

    def test_tvdb_circuit_property_no_bootstrap_on_first_access(self) -> None:
        """Reading ``.circuit`` on a fresh TVDBClient must not call ``_ensure_transport``."""
        bus = EventBus()
        client = TVDBClient(api_key="bogus", event_bus=bus)

        bootstrap_calls: list[None] = []
        original_ensure = TVDBClient._ensure_transport

        def spy(self_: TVDBClient) -> Any:
            bootstrap_calls.append(None)
            return original_ensure(self_)

        with patch.object(TVDBClient, "_ensure_transport", spy):
            result = client.circuit

        assert result is None, "Pre-bootstrap, circuit must be None (lazy breaker)."
        assert bootstrap_calls == [], "Reading .circuit must not invoke _ensure_transport."

    def test_tvdb_circuit_property_returns_breaker_post_bootstrap(self) -> None:
        """After ``_ensure_transport`` runs, ``.circuit`` returns the transport's breaker."""
        client = TVDBClient.__new__(TVDBClient)
        client._api_key = "fake"  # type: ignore[attr-defined]
        client._tvdb_lang = "fra"  # type: ignore[attr-defined]
        client._language = "fr-FR"  # type: ignore[attr-defined]
        client._circuit_breaker = None  # type: ignore[attr-defined]
        # Inject a transport carrying a sentinel breaker; the setter mirrors
        # it into the cache.
        sentinel_breaker = object()
        transport = MagicMock()
        transport._circuit = sentinel_breaker
        client._transport = transport  # type: ignore[attr-defined]

        assert client.circuit is sentinel_breaker

    def test_tvdb_eligibility_is_http_free(self) -> None:
        """``_eligible(TVDBClient)`` must not trigger the JWT bootstrap.

        The registry boots providers eagerly; the first
        ``registry.chain(...)`` or ``registry.status()`` call iterates
        the chain and calls :func:`_eligible` on every provider. Before
        Phase 22, that triggered the TVDB JWT exchange via the
        ``circuit`` property. The ``_registry_lazy_circuit = True``
        marker now flags TVDB as eligible pre-bootstrap without reading
        the live breaker.
        """
        from personalscraper.api.metadata.registry._factory import _eligible

        bus = EventBus()
        client = TVDBClient(api_key="bogus", event_bus=bus)

        bootstrap_calls: list[None] = []
        original_ensure = TVDBClient._ensure_transport

        def spy(self_: TVDBClient) -> Any:
            bootstrap_calls.append(None)
            return original_ensure(self_)

        with patch.object(TVDBClient, "_ensure_transport", spy):
            result = _eligible(client)

        assert result is True
        assert bootstrap_calls == [], "Eligibility check triggered TVDB bootstrap."
