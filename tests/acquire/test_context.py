"""Unit tests for AcquireContext — acquire-lobe RP5c."""

from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock

import pytest


def test_acquire_store_protocol_importable() -> None:
    """AcquireStore Protocol is importable and has a ``close`` method."""
    from personalscraper.acquire._ports import AcquireStore

    assert hasattr(AcquireStore, "close")


def test_acquire_context_is_frozen_dataclass() -> None:
    """AcquireContext is a frozen dataclass — mutating a field must raise."""
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.tracker._ranking import RankingConfig
    from personalscraper.api.tracker._registry import TrackerRegistry

    registry = TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())
    ctx = AcquireContext(tracker_registry=registry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.tracker_registry = registry  # type: ignore[misc]


def test_acquire_context_fields() -> None:
    """AcquireContext has tracker_registry, store, delete_authority, torrent_client, grab."""
    from personalscraper.acquire.context import AcquireContext

    fields = {f.name for f in dataclasses.fields(AcquireContext)}
    assert fields == {"tracker_registry", "store", "delete_authority", "torrent_client", "grab"}


def test_acquire_context_store_and_torrent_client_default_none() -> None:
    """Store, delete_authority, torrent_client, and grab default to None."""
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.tracker._ranking import RankingConfig
    from personalscraper.api.tracker._registry import TrackerRegistry

    registry = TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())
    ctx = AcquireContext(tracker_registry=registry)
    assert ctx.store is None
    assert ctx.delete_authority is None
    assert ctx.torrent_client is None
    assert ctx.grab is None


class TestAcquireContextClose:
    """AcquireContext.close() owns tracker_registry + store; borrows torrent_client."""

    def _make_ctx(
        self,
        *,
        store: object = None,
        torrent_client: object = None,
    ):
        """Build an AcquireContext with a mock TrackerRegistry."""
        from personalscraper.acquire.context import AcquireContext

        registry = MagicMock()
        return AcquireContext(
            tracker_registry=registry,
            store=store,
            torrent_client=torrent_client,
        )

    def test_close_calls_tracker_registry_close(self) -> None:
        """close() must call tracker_registry.close() exactly once."""
        ctx = self._make_ctx()
        ctx.close()
        ctx.tracker_registry.close.assert_called_once()

    def test_close_calls_store_close_when_present(self) -> None:
        """close() must call store.close() when store is not None."""
        store = MagicMock()
        ctx = self._make_ctx(store=store)
        ctx.close()
        store.close.assert_called_once()

    def test_close_skips_store_when_none(self) -> None:
        """close() must not raise and must not call store.close() when store is None."""
        ctx = self._make_ctx(store=None)
        ctx.close()  # no error

    def test_close_does_not_call_torrent_client_close(self) -> None:
        """NON-OWNERSHIP GUARD: close() must NEVER call torrent_client.close().

        This test is mutation-proven: if ``close()`` is modified to call
        ``self.torrent_client.close()``, ``assert_not_called()`` will fail
        (RED), catching the ownership violation immediately.
        """
        torrent_client = MagicMock()
        ctx = self._make_ctx(torrent_client=torrent_client)
        ctx.close()
        torrent_client.close.assert_not_called()

    def test_close_does_not_call_torrent_client_close_even_with_store(self) -> None:
        """Non-ownership guard holds when both store and torrent_client are set."""
        store = MagicMock()
        torrent_client = MagicMock()
        ctx = self._make_ctx(store=store, torrent_client=torrent_client)
        ctx.close()
        torrent_client.close.assert_not_called()
        store.close.assert_called_once()

    def test_delete_authority_is_stateless_not_closed(self) -> None:
        """NON-OWNERSHIP GUARD: close() must NEVER touch delete_authority.

        delete_authority is stateless (has no close() method) and borrows the
        store handle.  close() must not call any method on it.
        """
        from personalscraper.acquire.delete_authority import DeleteAuthority

        store = MagicMock()
        delete_auth = DeleteAuthority(store=store)
        ctx = self._make_ctx(store=store)
        # Use object.__setattr__ to inject on frozen dataclass (test-only).
        object.__setattr__(ctx, "delete_authority", delete_auth)
        ctx.close()
        # close() must not touch delete_authority — no attribute access, no call.
        # (delete_authority has no close(), so any close() call would AttributeError.)
