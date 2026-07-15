"""Unit tests for the web layer's shared torrent-client session cache.

Guards the anti-login-storm contract (prod IP-ban incident 2026-07-15): one
client build (= one qBittorrent login) per web process, invalidation on any
error raised while the client is borrowed, TTL-bounded staleness, and the
``None`` (unconfigured client) case never being cached.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.web import torrent_session
from personalscraper.web.torrent_session import (
    invalidate_torrent_session,
    shared_torrent_client,
)

_FACTORY = "personalscraper.web.torrent_session.build_active_torrent_client"


def test_second_borrow_reuses_cached_client() -> None:
    """Two consecutive borrows build (login) exactly once."""
    client = MagicMock()
    with patch(_FACTORY, return_value=client) as factory:
        with shared_torrent_client(MagicMock()) as first:
            assert first is client
        with shared_torrent_client(MagicMock()) as second:
            assert second is client
    assert factory.call_count == 1


def test_error_while_borrowed_invalidates_then_rebuilds() -> None:
    """An exception inside the borrow drops the session; next borrow re-logs-in."""
    with patch(_FACTORY, side_effect=[MagicMock(), MagicMock()]) as factory:
        with pytest.raises(RuntimeError), shared_torrent_client(MagicMock()):
            raise RuntimeError("qbit session died mid-request")
        with shared_torrent_client(MagicMock()) as rebuilt:
            assert rebuilt is not None
    assert factory.call_count == 2


def test_ttl_expiry_rebuilds_client() -> None:
    """A borrow past the TTL rebuilds the client (config changes picked up)."""
    with patch(_FACTORY, side_effect=[MagicMock(), MagicMock()]) as factory:
        with shared_torrent_client(MagicMock()):
            pass
        # Age the cached session past the TTL (monotonic() is always > 0).
        torrent_session._built_at = -torrent_session._TTL_SECONDS
        with shared_torrent_client(MagicMock()):
            pass
    assert factory.call_count == 2


def test_unconfigured_client_yields_none_and_is_not_cached() -> None:
    """A ``None`` factory result is yielded but never cached.

    A client enabled later is picked up on the very next borrow.
    """
    real_client = MagicMock()
    with patch(_FACTORY, side_effect=[None, real_client]) as factory:
        with shared_torrent_client(MagicMock()) as first:
            assert first is None
        with shared_torrent_client(MagicMock()) as second:
            assert second is real_client
    assert factory.call_count == 2


def test_invalidate_forces_rebuild() -> None:
    """The explicit invalidation hook drops the cached session."""
    with patch(_FACTORY, side_effect=[MagicMock(), MagicMock()]) as factory:
        with shared_torrent_client(MagicMock()):
            pass
        invalidate_torrent_session()
        with shared_torrent_client(MagicMock()):
            pass
    assert factory.call_count == 2
