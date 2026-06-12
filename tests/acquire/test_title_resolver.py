"""Tests for acquire/title_resolver.py — fail-soft title resolution."""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api._contracts import ApiError, CircuitOpenError
from personalscraper.api.metadata._contracts import TvDetailsProvider
from personalscraper.core.identity import MediaRef


def _mock_registry(tv_provider):
    """Build a mock ProviderRegistry whose chain(TvDetailsProvider) returns [tv_provider]."""
    registry = MagicMock()
    registry.chain.return_value = [tv_provider]
    return registry


def _empty_registry():
    """Build a mock ProviderRegistry with no TvDetailsProvider in chain."""
    registry = MagicMock()
    registry.chain.return_value = []
    return registry


# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


def test_resolve_returns_provider_title_on_success() -> None:
    """LOAD-BEARING: successful provider call returns the canonical title."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    mock_details = MagicMock()
    mock_details.title = "Breaking Bad"
    mock_provider = MagicMock(spec=TvDetailsProvider)
    mock_provider.get_tv.return_value = mock_details

    registry = _mock_registry(mock_provider)
    ref = MediaRef(tvdb_id=81189)

    result = resolve_series_title(ref, registry)

    assert result == "Breaking Bad"
    mock_provider.get_tv.assert_called_once_with(81189)


# ---------------------------------------------------------------------------
# Failure modes — all must fall back, never raise (LOAD-BEARING)
# ---------------------------------------------------------------------------


def test_resolve_falls_back_to_supplied_title_on_api_error() -> None:
    """LOAD-BEARING: ApiError → falls back to user-supplied title."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    mock_provider = MagicMock(spec=TvDetailsProvider)
    mock_provider.get_tv.side_effect = ApiError(provider="tvdb", http_status=500, message="network timeout")

    registry = _mock_registry(mock_provider)
    ref = MediaRef(tvdb_id=81189)

    result = resolve_series_title(ref, registry, fallback_title="My Show")

    assert result == "My Show", f"Expected 'My Show', got {result!r}"


def test_resolve_falls_back_to_placeholder_on_api_error_no_title() -> None:
    """LOAD-BEARING: ApiError with no fallback_title → 'tvdb:<id>' placeholder."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    mock_provider = MagicMock(spec=TvDetailsProvider)
    mock_provider.get_tv.side_effect = ApiError(provider="tvdb", http_status=403, message="403 forbidden")

    registry = _mock_registry(mock_provider)
    ref = MediaRef(tvdb_id=81189)

    result = resolve_series_title(ref, registry)

    assert result == "tvdb:81189", f"Expected 'tvdb:81189', got {result!r}"


def test_resolve_falls_back_on_circuit_open() -> None:
    """LOAD-BEARING: CircuitOpenError → falls back to placeholder."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    mock_provider = MagicMock(spec=TvDetailsProvider)
    mock_provider.get_tv.side_effect = CircuitOpenError(provider="tvdb", remaining_seconds=30.0)

    registry = _mock_registry(mock_provider)
    ref = MediaRef(tvdb_id=12345)

    result = resolve_series_title(ref, registry)

    assert result == "tvdb:12345"


def test_resolve_falls_back_on_empty_chain() -> None:
    """LOAD-BEARING: no TvDetailsProvider in chain → falls back without crashing."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    ref = MediaRef(tvdb_id=99999)
    result = resolve_series_title(ref, _empty_registry(), fallback_title="Fallback")

    assert result == "Fallback"


def test_resolve_falls_back_on_generic_exception() -> None:
    """LOAD-BEARING: unexpected exception → falls back, does not propagate."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    mock_provider = MagicMock(spec=TvDetailsProvider)
    mock_provider.get_tv.side_effect = RuntimeError("unexpected bug")

    registry = _mock_registry(mock_provider)
    ref = MediaRef(tvdb_id=11111)

    # Must not raise — any exception is swallowed and falls back.
    result = resolve_series_title(ref, registry)

    assert result == "tvdb:11111"


def test_resolve_uses_tmdb_id_placeholder_when_no_tvdb() -> None:
    """LOAD-BEARING: placeholder uses tmdb_id when tvdb_id is absent — no lookup attempted."""
    from personalscraper.acquire.title_resolver import resolve_series_title

    mock_provider = MagicMock(spec=TvDetailsProvider)

    registry = _mock_registry(mock_provider)
    ref = MediaRef(tmdb_id=5678)

    result = resolve_series_title(ref, registry)

    assert result == "tmdb:5678"
    mock_provider.get_tv.assert_not_called()
