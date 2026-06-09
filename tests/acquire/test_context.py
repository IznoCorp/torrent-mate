"""Unit tests for AcquireContext — acquire-lobe RP5c."""

from __future__ import annotations

import dataclasses

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
    """AcquireContext has tracker_registry, store, torrent_client fields."""
    from personalscraper.acquire.context import AcquireContext

    fields = {f.name for f in dataclasses.fields(AcquireContext)}
    assert fields == {"tracker_registry", "store", "torrent_client"}


def test_acquire_context_store_and_torrent_client_default_none() -> None:
    """Store and torrent_client default to None."""
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.tracker._ranking import RankingConfig
    from personalscraper.api.tracker._registry import TrackerRegistry

    registry = TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())
    ctx = AcquireContext(tracker_registry=registry)
    assert ctx.store is None
    assert ctx.torrent_client is None
