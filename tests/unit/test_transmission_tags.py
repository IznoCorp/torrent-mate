"""Tests for Transmission _torrent_item labels→tags round-trip (D5)."""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.torrent.transmission import _torrent_item


def _mock(labels=None):
    """Build a mock transmission_rpc.Torrent with minimal fields for tag testing."""
    t = MagicMock()
    t.hash_string = "h"
    t.name = "n"
    t.total_size = 0
    t.percent_done = 0.0
    t.status = "stopped"
    t.download_dir = None
    t.added_date = None
    t.get_files.return_value = []
    t.labels = labels
    t.ratio = 0.0
    return t


def test_labels_round_trip_category_and_tags():
    """category=labels[0], tags=labels[1:] per D5."""
    item = _torrent_item(_mock(labels=["movies", "action", "2024"]))
    assert item.category == "movies"
    assert item.tags == ["action", "2024"]


def test_labels_category_only():
    """Single label → category only, tags=[]."""
    item = _torrent_item(_mock(labels=["movies"]))
    assert item.category == "movies"
    assert item.tags == []


def test_labels_none():
    """No labels → category=None, tags=[]."""
    item = _torrent_item(_mock(labels=None))
    assert item.category is None
    assert item.tags == []
