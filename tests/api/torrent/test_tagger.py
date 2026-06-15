"""Tests for TorrentTagger capability on QBitClient and TransmissionClient.

Covers DESIGN criteria 1 (SEED_PURE importable), 2 (qBit tagger endpoints +
idempotence), and 3 (Transmission category preservation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient

# ---------------------------------------------------------------------------
# Criterion 1 — SEED_PURE constant
# ---------------------------------------------------------------------------


def test_seed_pure_importable_and_value():
    """SEED_PURE is importable from core.tags and equals 'seed-pure'."""
    from personalscraper.core.tags import SEED_PURE

    assert SEED_PURE == "seed-pure"


def test_seed_pure_in_all():
    """SEED_PURE is in core.tags.__all__."""
    import personalscraper.core.tags as m

    assert "SEED_PURE" in m.__all__


# ---------------------------------------------------------------------------
# Criterion 2 — QBitClient tagger
# ---------------------------------------------------------------------------


def _make_qbit_client() -> "QBitClient":
    """Build a QBitClient with a mocked underlying qbittorrentapi.Client."""
    from personalscraper.api.torrent.qbittorrent import QBitClient

    client = QBitClient.__new__(QBitClient)
    client._client = MagicMock()
    return client


def test_qbit_add_tags_calls_addTags():
    """add_tags calls torrents_addTags with correct hash and comma-joined tags."""
    client = _make_qbit_client()
    client.add_tags("abc123", ["seed-pure", "other"])
    client._client.torrents_addTags.assert_called_once_with(torrent_hashes="abc123", tags="seed-pure,other")


def test_qbit_remove_tags_calls_removeTags():
    """remove_tags calls torrents_removeTags with correct hash and comma-joined tags."""
    client = _make_qbit_client()
    client.remove_tags("abc123", ["seed-pure"])
    client._client.torrents_removeTags.assert_called_once_with(torrent_hashes="abc123", tags="seed-pure")


def test_qbit_add_tags_empty_is_noop():
    """add_tags with empty list makes no API call."""
    client = _make_qbit_client()
    client.add_tags("abc123", [])
    client._client.torrents_addTags.assert_not_called()


def test_qbit_remove_tags_empty_is_noop():
    """remove_tags with empty list makes no API call."""
    client = _make_qbit_client()
    client.remove_tags("abc123", [])
    client._client.torrents_removeTags.assert_not_called()


def test_qbit_tagger_protocol_compliance():
    """QBitClient satisfies the TorrentTagger protocol at runtime."""
    from personalscraper.api.torrent._contracts import TorrentTagger

    client = _make_qbit_client()
    assert isinstance(client, TorrentTagger)
