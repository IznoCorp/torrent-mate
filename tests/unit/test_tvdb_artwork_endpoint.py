"""Regression tests for TVDB artwork endpoint construction.

Bug detected during pipeline-monitor run 2026-05-07:
``get_artwork_urls`` built the path as ``f"/{media_type}s/{media_id}/extended"``,
which produced ``/tvs/{id}/extended`` for TV shows. The correct TVDB v4 endpoint
is ``/series/{id}/extended`` — the wrong URL returns HTTP 400 and the artwork
fetch silently fails (best-effort warning), leaving NFOs without poster/landscape.

These tests assert the constructed endpoint to prevent regression.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from personalscraper.api.metadata.tvdb import TVDBClient


def _make_client() -> TVDBClient:
    """Build a TVDBClient instance bypassing the bootstrap login.

    Returns:
        A TVDBClient whose ``_get_dict`` is mockable for endpoint introspection.
    """
    client = TVDBClient.__new__(TVDBClient)
    client._api_key = "fake"  # type: ignore[attr-defined]
    client._tvdb_lang = "eng"  # type: ignore[attr-defined]
    client._language = "fr-FR"  # type: ignore[attr-defined]
    client._fallback_language = "en-US"  # type: ignore[attr-defined]
    return client


class TestGetArtworkUrlsEndpoint:
    """Endpoint mapping for ``TVDBClient.get_artwork_urls``."""

    def test_tv_uses_series_endpoint(self) -> None:
        """``media_type='tv'`` must request ``/series/{id}/extended``, not ``/tvs/...``."""
        client = _make_client()
        captured: dict[str, Any] = {}

        def fake_get_dict(path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
            captured["path"] = path
            return {"artworks": []}

        client._get_dict = MagicMock(side_effect=fake_get_dict)  # type: ignore[method-assign]

        client.get_artwork_urls("355567", media_type="tv")

        assert captured["path"] == "/series/355567/extended", (
            f"TV artwork must use /series/ endpoint; got {captured.get('path')!r}"
        )
        assert "/tvs/" not in captured["path"], "Regression: /tvs/ is not a valid TVDB v4 endpoint and returns 400."

    def test_movie_uses_movies_endpoint(self) -> None:
        """``media_type='movie'`` must request ``/movies/{id}/extended``."""
        client = _make_client()
        captured: dict[str, Any] = {}

        def fake_get_dict(path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
            captured["path"] = path
            return {"artworks": []}

        client._get_dict = MagicMock(side_effect=fake_get_dict)  # type: ignore[method-assign]

        client.get_artwork_urls("12345", media_type="movie")

        assert captured["path"] == "/movies/12345/extended", (
            f"Movie artwork must use /movies/ endpoint; got {captured.get('path')!r}"
        )

    def test_default_media_type_is_movie(self) -> None:
        """Default ``media_type`` (omitted) routes to the movies endpoint."""
        client = _make_client()
        captured: dict[str, Any] = {}

        def fake_get_dict(path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
            captured["path"] = path
            return {"artworks": []}

        client._get_dict = MagicMock(side_effect=fake_get_dict)  # type: ignore[method-assign]

        client.get_artwork_urls("999")

        assert captured["path"] == "/movies/999/extended"


class TestGetVideosEndpoint:
    """Endpoint mapping for ``TVDBClient.get_videos``.

    Mirrors the ``get_artwork_urls`` regression: naive ``f"/{media_type}s/..."``
    pluralization produced ``/tvs/...`` for TV shows. TVDB v4 requires
    ``/series/{id}/extended`` and returns HTTP 400 otherwise.
    """

    def test_tv_uses_series_endpoint(self) -> None:
        """``media_type='tv'`` must request ``/series/{id}/extended``, not ``/tvs/...``."""
        client = _make_client()
        captured: dict[str, Any] = {}

        def fake_get_dict(path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
            captured["path"] = path
            return {"trailers": []}

        client._get_dict = MagicMock(side_effect=fake_get_dict)  # type: ignore[method-assign]

        client.get_videos("355567", media_type="tv", language="eng")

        assert captured["path"] == "/series/355567/extended", (
            f"TV videos must use /series/ endpoint; got {captured.get('path')!r}"
        )
        assert "/tvs/" not in captured["path"], "Regression: /tvs/ is not a valid TVDB v4 endpoint and returns 400."

    def test_movie_uses_movies_endpoint(self) -> None:
        """``media_type='movie'`` must request ``/movies/{id}/extended``."""
        client = _make_client()
        captured: dict[str, Any] = {}

        def fake_get_dict(path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
            captured["path"] = path
            return {"trailers": []}

        client._get_dict = MagicMock(side_effect=fake_get_dict)  # type: ignore[method-assign]

        client.get_videos("12345", media_type="movie", language="eng")

        assert captured["path"] == "/movies/12345/extended"
