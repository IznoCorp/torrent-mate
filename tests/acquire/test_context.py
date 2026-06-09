"""Unit tests for AcquireContext — acquire-lobe RP5c."""

from __future__ import annotations


def test_acquire_store_protocol_importable() -> None:
    """AcquireStore Protocol is importable and has a ``close`` method."""
    from personalscraper.acquire._ports import AcquireStore

    assert hasattr(AcquireStore, "close")
