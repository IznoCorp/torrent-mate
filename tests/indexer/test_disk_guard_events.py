"""Tests for the disk-guard event emits — Sub-phase 4.2b.

Covers :class:`DiskFullWarning` emission from both threshold paths:

- :func:`personalscraper.indexer.db.check_free_space` (pre-flight check)
  emits when free < required.
- :func:`personalscraper.indexer._disk_guard.handle_disk_full` (mid-scan
  reactive path) emits when an ``OperationalError`` confirms the disk is
  full.

Both paths are guarded by ``event_bus is not None``; the legacy positional
contracts remain valid (event_bus defaults to ``None``).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.core.event_bus import (
    EventBus,
    event_from_envelope,
    event_to_envelope,
)
from personalscraper.indexer._disk_guard import handle_disk_full
from personalscraper.indexer.db import IndexerDiskFullError, check_free_space
from personalscraper.indexer.events import DiskFullWarning
from tests.fixtures.event_bus import CollectingSubscriber, assert_event_round_trip
from tests.fixtures.event_samples import EVENT_SAMPLE_FACTORIES


def _statvfs_with_free(free_bytes: int) -> os.statvfs_result:
    """Build a ``statvfs_result``-shaped object reporting ``free_bytes`` available.

    ``frsize=1`` makes ``frsize * f_bavail == free_bytes`` exactly so the
    test isolates the free-space arithmetic from any block-size rounding.
    """
    return os.statvfs_result((1, 1, 0, 0, free_bytes, 0, 0, 0, 0, 255))


def test_check_free_space_emits_warning_when_below_threshold(tmp_path: Path) -> None:
    """``check_free_space`` emits exactly one ``DiskFullWarning`` and raises ``IndexerDiskFullError``."""
    bus = EventBus()
    collector: CollectingSubscriber[DiskFullWarning] = CollectingSubscriber(bus, DiskFullWarning)
    db_path = tmp_path / "library.db"

    with patch("personalscraper.indexer.db.os.statvfs", return_value=_statvfs_with_free(1_000_000_000)):
        with pytest.raises(IndexerDiskFullError):
            check_free_space(db_path, expected_growth_bytes=10_000_000_000, event_bus=bus)

    assert len(collector.received) == 1
    event = collector.received[0]
    assert event.disk_path == db_path
    assert event.free_bytes == 1_000_000_000
    assert event.threshold_bytes == 20_000_000_000


def test_check_free_space_does_not_emit_when_above_threshold(tmp_path: Path) -> None:
    """A successful free-space check emits nothing."""
    bus = EventBus()
    collector: CollectingSubscriber[DiskFullWarning] = CollectingSubscriber(bus, DiskFullWarning)
    db_path = tmp_path / "library.db"

    with patch("personalscraper.indexer.db.os.statvfs", return_value=_statvfs_with_free(100_000_000_000)):
        check_free_space(db_path, expected_growth_bytes=1_000_000_000, event_bus=bus)

    assert collector.received == []


def test_check_free_space_without_bus_does_not_raise(tmp_path: Path) -> None:
    """Calling without ``event_bus`` preserves the legacy raise-only contract."""
    db_path = tmp_path / "library.db"
    with patch("personalscraper.indexer.db.os.statvfs", return_value=_statvfs_with_free(1)):
        with pytest.raises(IndexerDiskFullError):
            check_free_space(db_path, expected_growth_bytes=1_000_000_000)


def test_handle_disk_full_emits_warning_on_disk_io_error() -> None:
    """``handle_disk_full`` emits one ``DiskFullWarning`` and raises ``IndexerDiskFullError``."""
    bus = EventBus()
    collector: CollectingSubscriber[DiskFullWarning] = CollectingSubscriber(bus, DiskFullWarning)
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(0, "main", "/tmp/library.db")]
    exc = sqlite3.OperationalError("disk I/O error")

    with pytest.raises(IndexerDiskFullError):
        handle_disk_full(mock_conn, exc, event_bus=bus)

    assert len(collector.received) == 1
    event = collector.received[0]
    assert event.disk_path == Path("/tmp/library.db")
    assert event.free_bytes == 0  # not derivable from the SQLite error
    assert event.threshold_bytes == 0


def test_handle_disk_full_does_not_emit_on_unrelated_error() -> None:
    """A non-disk-full OperationalError leaves the bus untouched."""
    bus = EventBus()
    collector: CollectingSubscriber[DiskFullWarning] = CollectingSubscriber(bus, DiskFullWarning)
    mock_conn = MagicMock()
    exc = sqlite3.OperationalError("database is locked")

    result = handle_disk_full(mock_conn, exc, event_bus=bus)
    assert result is None
    assert collector.received == []


def test_handle_disk_full_without_bus_does_not_raise() -> None:
    """``event_bus=None`` preserves the legacy contract — only the indexer error rises."""
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [(0, "main", "/tmp/library.db")]
    exc = sqlite3.OperationalError("database or disk is full")
    with pytest.raises(IndexerDiskFullError):
        handle_disk_full(mock_conn, exc)


def test_disk_full_warning_has_factory() -> None:
    """``DiskFullWarning`` is registered in ``EVENT_SAMPLE_FACTORIES``."""
    assert DiskFullWarning in EVENT_SAMPLE_FACTORIES


def test_disk_full_warning_envelope_roundtrip() -> None:
    """``DiskFullWarning`` survives envelope round-trip, including ``Path`` coercion."""
    original = EVENT_SAMPLE_FACTORIES[DiskFullWarning]()
    envelope = event_to_envelope(original)
    assert envelope["_type"] == "DiskFullWarning"
    reconstructed = event_from_envelope(envelope)
    assert type(reconstructed) is DiskFullWarning
    assert_event_round_trip(original, reconstructed)
    assert isinstance(reconstructed.disk_path, Path)  # type: ignore[attr-defined]
