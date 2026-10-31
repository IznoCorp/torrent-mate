"""Tests for resolve_series_tvdb — cross-provider TVDB resolution at follow time.

A series followed by TMDB/IMDB alone must have its TVDB id resolved before the
follow is stored, else episode detection (poll_known) silently skips it. This is
precision-first and fail-soft (any provider error → None, never raises).
"""

from __future__ import annotations

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
        client.get_tvdb_id.assert_not_called()
        client.find_by_imdb.assert_not_called()

    def test_tmdb_id_resolves_via_get_tvdb_id(self) -> None:
        """tmdb_id → get_tvdb_id(tmdb_id) (raw /tv/{id}/external_ids)."""
        client = _client(get_tvdb_id=121361)
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) == 121361
        client.get_tvdb_id.assert_called_once_with(1399)

    def test_imdb_id_resolves_via_find_then_get_tvdb_id(self) -> None:
        """imdb_id → find_by_imdb → tmdb id → get_tvdb_id → tvdb id."""
        client = _client(find_by_imdb=1399, get_tvdb_id=121361)
        assert resolve_series_tvdb(MediaRef(imdb_id="tt0944947"), client) == 121361
        client.find_by_imdb.assert_called_once_with("tt0944947")
        client.get_tvdb_id.assert_called_once_with(1399)

    def test_no_tvdb_cross_reference_returns_none(self) -> None:
        """A TMDB show with no TVDB cross-reference yields None (unresolved)."""
        client = _client(get_tvdb_id=None)
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) is None

    def test_imdb_not_a_show_returns_none(self) -> None:
        """find_by_imdb returning None (movie/person only) yields None."""
        client = _client(find_by_imdb=None)
        assert resolve_series_tvdb(MediaRef(imdb_id="tt0137523"), client) is None
        client.get_tvdb_id.assert_not_called()

    def test_provider_error_is_fail_soft(self) -> None:
        """Any provider exception degrades to None — never propagates."""
        client = MagicMock()
        client.get_tvdb_id.side_effect = RuntimeError("boom")
        assert resolve_series_tvdb(MediaRef(tmdb_id=1399), client) is None


class TestDeriveTvdbUnresolved:
    """_derive_tvdb_unresolved — honest inert-show state on every surface."""

    def _fs(self, ref: MediaRef, *, kind: str = "show", active: bool = True) -> object:
        from personalscraper.acquire.domain import FollowedSeries

        return FollowedSeries(media_ref=ref, title="T", added_at=0, active=active, kind=kind)

    def test_active_show_without_tvdb_is_unresolved(self) -> None:
        """An active show with no tvdb_id is inert (poll_known skips it)."""
        from personalscraper.web.acquisition.service import _derive_tvdb_unresolved

        assert _derive_tvdb_unresolved(self._fs(MediaRef(tmdb_id=1399))) is True

    def test_show_with_tvdb_is_resolved(self) -> None:
        """A show with a tvdb_id is detectable → not flagged."""
        from personalscraper.web.acquisition.service import _derive_tvdb_unresolved

        assert _derive_tvdb_unresolved(self._fs(MediaRef(tvdb_id=121361))) is False

    def test_paused_show_without_tvdb_is_not_flagged(self) -> None:
        """A paused (inactive) show is not searched, so it is not flagged."""
        from personalscraper.web.acquisition.service import _derive_tvdb_unresolved

        fs = self._fs(MediaRef(tmdb_id=1399), active=False)
        assert _derive_tvdb_unresolved(fs) is False

    def test_movie_without_tvdb_is_not_flagged(self) -> None:
        """A film uses the title lifecycle — no TVDB needed, never flagged."""
        from personalscraper.web.acquisition.service import _derive_tvdb_unresolved

        fs = self._fs(MediaRef(tmdb_id=550), kind="movie")
        assert _derive_tvdb_unresolved(fs) is False
