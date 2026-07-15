"""Tests for Transmission _torrent_item labels→tags round-trip (D5)."""

from __future__ import annotations

from unittest.mock import MagicMock

from personalscraper.api.torrent.transmission import _torrent_item


def _mock(labels=None, *, error=0, error_string=""):
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
    t.error = error
    t.error_string = error_string
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


def test_no_error_has_no_error_reason():
    """error=0 → error_reason=None (healthy torrent)."""
    assert _torrent_item(_mock(error=0)).error_reason is None


def test_tracker_warning_is_not_surfaced_as_error():
    """error=1 (tracker warning) is transient — not surfaced as an error."""
    assert _torrent_item(_mock(error=1, error_string="tracker warning")).error_reason is None


def test_local_error_surfaces_error_string():
    """error=3 (local error, data missing) → the daemon's errorString (§8).

    Red-on-old: get_by_hashes already requested error/errorString but the
    mapper dropped them, so a broken Transmission torrent looked healthy.
    """
    item = _torrent_item(_mock(error=3, error_string="No data found!"))
    assert item.error_reason == "No data found!"


def test_error_without_string_falls_back_to_french():
    """error=3 with an empty errorString → a French fallback reason."""
    assert _torrent_item(_mock(error=3, error_string="")).error_reason == "Erreur locale (fichiers manquants ?)"
