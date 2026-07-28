"""Tests for resolve_series_tvdb — cross-provider TVDB resolution at follow time.

A series followed by TMDB/IMDB alone must have its TVDB id resolved before the
follow is stored, else episode detection (poll_known) silently skips it. This is
precision-first and fail-soft (any provider error → None, never raises).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from personalscraper.core.identity import MediaRef
from personalscraper.web.acquisition.service import resolve_series_tvdb


def _client(**attrs: object) -> MagicMock:
    """A MagicMock TMDB client with the given method return values."""
    c = MagicMock()
    for name, value in attrs.items():
        getattr(c, name).return_value = value
    return c


class TestResolveSeriesTvdb:
    """resolve_series_tvdb over the TMDB/IMDB → TVDB paths."""

    def test_existing_tvdb_id_short_circuits(self) -> None:
        """A media_ref that already has a tvdb_id returns it with NO provider call."""
        client = _client()
        assert resolve_series_tvdb(MediaRef(tvdb_id=255968), client) == 255968
        client.get_tv.assert_not_called()
        client.find_by_imdb.assert_not_called()

    def test_tmdb_id_resolves_via_get_tv_external_ids(self) -> None:
        """tmdb_id → get_tv(...).external_ids['tvdb'] (as int)."""
        client = _client(get_tv=SimpleNamespace(external_ids={"tvdb": "121361"}))
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) == 121361
        client.get_tv.assert_called_once_with(1399)

    def test_imdb_id_resolves_via_find_then_get_tv(self) -> None:
        """imdb_id → find_by_imdb → tmdb id → get_tv → tvdb external id."""
        client = _client(
            find_by_imdb=1399,
            get_tv=SimpleNamespace(external_ids={"tvdb": "121361"}),
        )
        assert resolve_series_tvdb(MediaRef(imdb_id="tt0944947"), client) == 121361
        client.find_by_imdb.assert_called_once_with("tt0944947")
        client.get_tv.assert_called_once_with(1399)

    def test_no_tvdb_in_external_ids_returns_none(self) -> None:
        """A TMDB show with no TVDB cross-reference yields None (unresolved)."""
        client = _client(get_tv=SimpleNamespace(external_ids={"imdb": "tt1"}))
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) is None

    def test_imdb_not_a_show_returns_none(self) -> None:
        """find_by_imdb returning None (movie/person only) yields None."""
        client = _client(find_by_imdb=None)
        assert resolve_series_tvdb(MediaRef(imdb_id="tt0137523"), client) is None
        client.get_tv.assert_not_called()

    def test_provider_error_is_fail_soft(self) -> None:
        """Any provider exception degrades to None — never propagates."""
        client = MagicMock()
        client.get_tv.side_effect = RuntimeError("boom")
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) is None

    def test_non_numeric_tvdb_returns_none(self) -> None:
        """A malformed tvdb external id (non-numeric) yields None, never raises."""
        client = _client(get_tv=SimpleNamespace(external_ids={"tvdb": "abc"}))
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) is None
