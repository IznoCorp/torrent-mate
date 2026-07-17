"""Unit tests for TMDBClient method bodies (search, get_*, helpers).

HTTP transport is mocked. We exercise every method body to ensure the
URL/params shape, response parsing path, and edge-case branches (non-dict
responses, empty pages, pagination termination) are covered.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from personalscraper.api.metadata._base import (
    ArtworkItem,
    MediaDetails,
    SearchResult,
    SeasonDetails,
)
from personalscraper.api.metadata.tmdb import TMDBClient

SAMPLES = Path("docs/reference/_samples/tmdb")


def _load(name: str) -> Any:
    """Load a golden TMDB sample JSON from docs/reference/_samples/tmdb."""
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def transport() -> MagicMock:
    """A MagicMock standing in for HttpTransport."""
    return MagicMock()


@pytest.fixture()
def client(transport: MagicMock) -> TMDBClient:
    """TMDBClient bound to a mocked transport (no real HTTP)."""
    return TMDBClient(transport=transport, language="fr-FR")


# ── policy + circuit property ──────────────────────────────────────────


class TestPolicyAndCircuit:
    """Cover the classmethod policy() and the circuit property."""

    def test_policy_returns_transport_policy(self) -> None:
        """policy() builds a TransportPolicy with TMDB defaults."""
        policy = TMDBClient.policy("fake-bearer-token")
        assert policy.base_url == "https://api.themoviedb.org/3"
        assert policy.timeout_seconds == 10.0

    def test_policy_accepts_custom_circuit(self) -> None:
        """A custom CircuitPolicy override is honoured."""
        from personalscraper.api.transport._policy import CircuitPolicy

        custom = CircuitPolicy(failure_threshold=99, cooldown_seconds=1.0)
        policy = TMDBClient.policy("fake", circuit=custom)
        assert policy.circuit is custom

    def test_circuit_property_exposes_breaker(self, client: TMDBClient, transport: MagicMock) -> None:
        """Circuit property returns the underlying transport's circuit breaker."""
        # MagicMock auto-creates _circuit on access; verify identity.
        assert client.circuit is transport._circuit


# ── search dispatcher (Protocol entry) ────────────────────────────────


class TestSearchDispatch:
    """The Protocol-level ``search`` dispatcher routes by media_type."""

    def test_search_movie_routes_to_search_movie(self, client: TMDBClient, transport: MagicMock) -> None:
        """``media_type='movie'`` (default) hits /search/movie."""
        transport.get.return_value = _load("search_movie.json")
        results = client.search("Fight Club", year=1999)
        assert len(results) >= 1
        # Endpoint must be /search/movie
        first_call = transport.get.call_args_list[0]
        assert first_call.args[0] == "/search/movie"

    def test_search_tv_routes_to_search_tv(self, client: TMDBClient, transport: MagicMock) -> None:
        """``media_type='tv'`` hits /search/tv."""
        transport.get.return_value = _load("search_tv.json")
        client.search("Breaking Bad", media_type="tv")
        first_call = transport.get.call_args_list[0]
        assert first_call.args[0] == "/search/tv"


# ── get_details dispatcher ────────────────────────────────────────────


class TestGetDetailsDispatch:
    """Typed detail capabilities accept the string-id Protocol path."""

    def test_get_movie_string_id(self, client: TMDBClient, transport: MagicMock) -> None:
        """get_movie(str) → /movie/{id}."""
        transport.get.return_value = _load("movie_details.json")
        md = client.get_movie("550")
        assert isinstance(md, MediaDetails)
        assert md.provider_id == "550"
        assert transport.get.call_args.args[0] == "/movie/550"

    def test_get_tv_string_id(self, client: TMDBClient, transport: MagicMock) -> None:
        """get_tv(str) → /tv/{id}."""
        transport.get.return_value = _load("tv_details.json")
        md = client.get_tv("1396")
        assert isinstance(md, MediaDetails)
        assert transport.get.call_args.args[0] == "/tv/1396"


# ── search_movie / search_tv ──────────────────────────────────────────


class TestSearchMovie:
    """search_movie: params, year filter, language override."""

    def test_basic_search(self, client: TMDBClient, transport: MagicMock) -> None:
        """Basic search hits /search/movie with query+language."""
        transport.get.return_value = _load("search_movie.json")
        results = client.search_movie("Fight Club")
        assert all(isinstance(r, SearchResult) for r in results)
        call = transport.get.call_args_list[0]
        assert call.args[0] == "/search/movie"
        assert call.kwargs["params"]["query"] == "Fight Club"
        assert call.kwargs["params"]["language"] == "fr-FR"

    def test_year_filter(self, client: TMDBClient, transport: MagicMock) -> None:
        """year= adds ``year`` query param."""
        transport.get.return_value = _load("search_movie.json")
        client.search_movie("Fight Club", year=1999)
        call = transport.get.call_args_list[0]
        assert call.kwargs["params"]["year"] == 1999

    def test_language_override(self, client: TMDBClient, transport: MagicMock) -> None:
        """An explicit ``language=`` overrides the client default."""
        transport.get.return_value = {"results": [], "total_pages": 0}
        client.search_movie("X", language="en-US")
        call = transport.get.call_args_list[0]
        assert call.kwargs["params"]["language"] == "en-US"

    def test_query_is_nfc_normalized(self, client: TMDBClient, transport: MagicMock) -> None:
        """An NFD-decomposed title is NFC-normalized before hitting TMDB.

        Folder names from the macOS / NTFS-via-macFUSE filesystem arrive
        NFD-decomposed (``a`` + U+0302 combining circumflex). TMDB's search
        index cannot match the decomposed form and returns zero results, so
        accented French titles (e.g. ``L'âge de glace``) silently failed to
        match. The client must NFC-normalize the query.
        """
        import unicodedata

        transport.get.return_value = {"results": [], "total_pages": 0}
        nfd = unicodedata.normalize("NFD", "L'âge de glace")
        assert not unicodedata.is_normalized("NFC", nfd), "test setup must pass NFD"

        client.search_movie(nfd, year=2002)

        sent = transport.get.call_args_list[0].kwargs["params"]["query"]
        assert unicodedata.is_normalized("NFC", sent), "query sent to TMDB must be NFC"
        assert sent == "L'âge de glace"  # precomposed â


class TestSearchTv:
    """search_tv: params, year filter, first_air_date_year mapping."""

    def test_year_uses_first_air_date_year(self, client: TMDBClient, transport: MagicMock) -> None:
        """TV year is sent as ``first_air_date_year``, not ``year``."""
        transport.get.return_value = _load("search_tv.json")
        client.search_tv("Breaking Bad", year=2008)
        call = transport.get.call_args_list[0]
        assert call.kwargs["params"]["first_air_date_year"] == 2008
        assert "year" not in call.kwargs["params"]


# ── get_movie / get_tv ────────────────────────────────────────────────


class TestGetMovie:
    """get_movie returns MediaDetails and uses append_to_response."""

    def test_endpoint_and_params(self, client: TMDBClient, transport: MagicMock) -> None:
        """Calls /movie/{id} with append_to_response + include_image_language."""
        transport.get.return_value = _load("movie_details.json")
        md = client.get_movie(550)
        assert md.provider_id == "550"
        call = transport.get.call_args
        assert call.args[0] == "/movie/550"
        params = call.kwargs["params"]
        assert "videos" in params["append_to_response"]
        assert "external_ids" in params["append_to_response"]
        assert params["language"] == "fr-FR"

    def test_non_dict_response_raises(self, client: TMDBClient, transport: MagicMock) -> None:
        """A non-dict response from /movie/{id} raises TypeError."""
        transport.get.return_value = ["not", "a", "dict"]
        with pytest.raises(TypeError, match="Expected dict"):
            client.get_movie(550)


class TestGetTv:
    """get_tv returns MediaDetails for a TV show."""

    def test_endpoint_and_params(self, client: TMDBClient, transport: MagicMock) -> None:
        """Calls /tv/{id} with append_to_response."""
        transport.get.return_value = _load("tv_details.json")
        md = client.get_tv(1396)
        assert isinstance(md, MediaDetails)
        call = transport.get.call_args
        assert call.args[0] == "/tv/1396"
        assert "videos" in call.kwargs["params"]["append_to_response"]

    def test_non_dict_response_raises(self, client: TMDBClient, transport: MagicMock) -> None:
        """A non-dict response from /tv/{id} raises TypeError."""
        transport.get.return_value = "bad"
        with pytest.raises(TypeError, match="Expected dict"):
            client.get_tv(1)


# ── get_tv_season / get_episodes ──────────────────────────────────────


class TestGetTvSeason:
    """get_tv_season fetches /tv/{id}/season/{n} and parses the response."""

    def test_endpoint_and_parses(self, client: TMDBClient, transport: MagicMock) -> None:
        """Calls /tv/{id}/season/{n} and returns SeasonDetails with episodes."""
        transport.get.return_value = _load("season_details.json")
        sd = client.get_tv_season(1396, 1)
        assert isinstance(sd, SeasonDetails)
        assert sd.tv_id == "1396"
        assert sd.season_number == 1
        assert len(sd.episodes) > 0
        call = transport.get.call_args
        assert call.args[0] == "/tv/1396/season/1"

    def test_non_dict_response_raises(self, client: TMDBClient, transport: MagicMock) -> None:
        """Non-dict response raises TypeError."""
        transport.get.return_value = []
        with pytest.raises(TypeError, match="Expected dict"):
            client.get_tv_season(1, 1)

    def test_get_episodes_string_id(self, client: TMDBClient, transport: MagicMock) -> None:
        """The ``get_episodes`` capability accepts a string tv_id and returns the episode list."""
        transport.get.return_value = _load("season_details.json")
        episodes = client.get_episodes("1396", 1)
        assert len(episodes) > 0


# ── get_artwork_urls ──────────────────────────────────────────────────


class TestGetArtworkUrls:
    """get_artwork_urls: endpoint, params, fail-soft on non-dict."""

    def test_movie_artwork(self, client: TMDBClient, transport: MagicMock) -> None:
        """Calls /movie/{id}/images and parses backdrops/posters/logos."""
        transport.get.return_value = {
            "id": 550,
            "backdrops": [{"file_path": "/b.jpg", "iso_639_1": "en", "vote_average": 5.0}],
            "posters": [{"file_path": "/p.jpg", "iso_639_1": "fr", "vote_average": 6.0}],
            "logos": [],
        }
        items = client.get_artwork_urls("550", media_type="movie")
        assert all(isinstance(a, ArtworkItem) for a in items)
        assert transport.get.call_args.args[0] == "/movie/550/images"

    def test_tv_artwork(self, client: TMDBClient, transport: MagicMock) -> None:
        """media_type=tv → /tv/{id}/images."""
        transport.get.return_value = {"backdrops": [], "posters": [], "logos": []}
        client.get_artwork_urls("1396", media_type="tv")
        assert transport.get.call_args.args[0] == "/tv/1396/images"

    def test_non_dict_returns_empty(self, client: TMDBClient, transport: MagicMock) -> None:
        """Non-dict response falls back to []."""
        transport.get.return_value = None
        assert client.get_artwork_urls("550") == []


# ── get_keywords ──────────────────────────────────────────────────────


class TestGetKeywords:
    """get_keywords: endpoint, fail-soft on non-dict, movie/tv envelope."""

    def test_movie_keywords(self, client: TMDBClient, transport: MagicMock) -> None:
        """Movie keywords use the ``keywords`` envelope."""
        transport.get.return_value = {"keywords": [{"id": 1, "name": "thriller"}]}
        kws = client.get_keywords("550", media_type="movie")
        assert kws == ["thriller"]
        assert transport.get.call_args.args[0] == "/movie/550/keywords"

    def test_tv_keywords(self, client: TMDBClient, transport: MagicMock) -> None:
        """TV keywords use the ``results`` envelope."""
        transport.get.return_value = {"results": [{"id": 1, "name": "drama"}]}
        kws = client.get_keywords("1396", media_type="tv")
        assert kws == ["drama"]
        assert transport.get.call_args.args[0] == "/tv/1396/keywords"

    def test_non_dict_returns_empty(self, client: TMDBClient, transport: MagicMock) -> None:
        """Non-dict response → []."""
        transport.get.return_value = ["unexpected"]
        assert client.get_keywords("1", "movie") == []


# ── get_image_url helper ──────────────────────────────────────────────


class TestGetImageUrl:
    """The ``get_image_url`` helper delegates to _build_image_url."""

    def test_path_prepended(self, client: TMDBClient) -> None:
        """A non-empty path produces a CDN URL."""
        url = client.get_image_url("/abc.jpg", "w500")
        assert url == "https://image.tmdb.org/t/p/w500/abc.jpg"

    def test_empty_path_empty_url(self, client: TMDBClient) -> None:
        """Empty path → empty string."""
        assert client.get_image_url("", "w500") == ""


# ── _search_paginated branches ────────────────────────────────────────


class TestSearchPaginated:
    """Pagination loop: total_pages termination, empty page break, non-dict break."""

    def test_terminates_at_total_pages(self, client: TMDBClient, transport: MagicMock) -> None:
        """Loop exits when ``page >= total_pages``."""
        transport.get.return_value = {
            "results": [{"id": 1, "title": "X"}],
            "total_pages": 1,
        }
        results = client.search_movie("X", max_pages=10)
        # Only one page should have been fetched
        assert transport.get.call_count == 1
        assert len(results) == 1

    def test_breaks_on_empty_results(self, client: TMDBClient, transport: MagicMock) -> None:
        """An empty results list ends pagination immediately."""
        transport.get.return_value = {"results": [], "total_pages": 5}
        results = client.search_movie("X")
        assert results == []
        assert transport.get.call_count == 1

    def test_breaks_on_non_dict(self, client: TMDBClient, transport: MagicMock) -> None:
        """A non-dict response ends pagination."""
        transport.get.return_value = "garbage"
        results = client.search_movie("X")
        assert results == []

    def test_aggregates_multiple_pages(self, client: TMDBClient, transport: MagicMock) -> None:
        """Multi-page responses are flattened into a single list."""
        transport.get.side_effect = [
            {"results": [{"id": 1, "title": "A"}], "total_pages": 2},
            {"results": [{"id": 2, "title": "B"}], "total_pages": 2},
        ]
        results = client.search_movie("X", max_pages=5)
        assert [r.provider_id for r in results] == ["1", "2"]
