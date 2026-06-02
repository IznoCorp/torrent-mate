"""Tests for TransmissionClient.add() — DESIGN D1/D5/D7/D8."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import transmission_rpc

from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
from personalscraper.api.torrent.transmission import TransmissionClient, _labels

MAGNET = "magnet:?xt=urn:btih:aabbcc112233ddeeff00112233445566778899aa&dn=t"


def _c():
    """Build a TransmissionClient with a mocked inner client."""
    with patch("transmission_rpc.Client"):
        c = TransmissionClient("localhost", 9091, "u", "p")
    c._client = MagicMock()
    return c


def _mock_torrent(hash_string="aabbcc112233ddeeff00112233445566778899aa"):
    """Build a mock transmission_rpc.Torrent with a hash_string."""
    t = MagicMock()
    t.hash_string = hash_string
    return t


class TestTransmissionAdd:
    """Tests for TransmissionClient.add() behaviour."""

    def test_is_torrent_adder(self):
        """TransmissionClient satisfies TorrentAdder."""
        assert isinstance(_c(), TorrentAdder)

    def test_not_torrent_limiter(self):
        """TransmissionClient does NOT satisfy TorrentLimiter (D2)."""
        assert not isinstance(_c(), TorrentLimiter)

    def test_magnet_calls_add_torrent(self):
        """Magnet source is passed as torrent= kwarg with labels=[category, *tags]."""
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET), category="movies", tags=["action"])
        kw = c._client.add_torrent.call_args[1]
        assert kw["torrent"] == MAGNET
        assert kw["labels"] == ["movies", "action"]

    def test_file_bytes_passed_as_torrent(self):
        """File bytes source is passed as torrent= kwarg."""
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        data = b"d4:infodee"  # minimal valid bencode with empty info dict
        c.add(TorrentSource.from_file(data))
        assert c._client.add_torrent.call_args[1]["torrent"] == data

    def test_paused_forwarded(self):
        """paused=True is forwarded to add_torrent."""
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET), paused=True)
        assert c._client.add_torrent.call_args[1].get("paused") is True

    def test_returns_info_hash(self):
        """add() returns the source info_hash."""
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        src = TorrentSource.from_magnet(MAGNET)
        assert c.add(src) == src.info_hash

    def test_duplicate_idempotent(self):
        """Duplicate torrent returns info_hash without raising (D7)."""
        c = _c()
        c._client.add_torrent.side_effect = transmission_rpc.TransmissionError("torrent-duplicate")
        src = TorrentSource.from_magnet(MAGNET)
        assert c.add(src) == src.info_hash  # D7: no exception

    def test_duplicate_torrent_message_idempotent(self):
        """A daemon ``"duplicate torrent"`` error is idempotent success (D7).

        Some daemons raise a ``TransmissionError`` carrying ``"duplicate
        torrent"`` (the human-readable result string) rather than the lib's
        ``"torrent-duplicate"`` result key. The except-branch dup match now
        covers BOTH forms, so this maps to idempotent success (returns hash).
        """
        c = _c()
        c._client.add_torrent.side_effect = transmission_rpc.TransmissionError(
            'Query failed with result "duplicate torrent".'
        )
        src = TorrentSource.from_magnet(MAGNET)
        assert c.add(src) == src.info_hash  # D7: no exception

    def test_duplicate_returns_torrent_idempotent(self):
        """``add_torrent`` RETURNS a Torrent on duplicate (installed-lib path).

        transmission_rpc 7.x builds a ``Torrent`` from the
        ``torrent-duplicate`` result key and returns it WITHOUT raising. This
        is the realistic happy path — ``add()`` returns the source info_hash.
        """
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        src = TorrentSource.from_magnet(MAGNET)
        assert c.add(src) == src.info_hash  # D7: no raise, returns hash

    def test_non_duplicate_not_swallowed(self):
        """TransmissionError without 'torrent-duplicate' must propagate (Md5)."""
        c = _c()
        c._client.add_torrent.side_effect = transmission_rpc.TransmissionError("duplicate label rejected")
        src = TorrentSource.from_magnet(MAGNET)
        with pytest.raises(transmission_rpc.TransmissionError, match="duplicate label rejected"):
            c.add(src)

    def test_hash_mismatch_warns(self):
        """When echoed hash differs from source hash, a warning is emitted (D6/mn1)."""
        from personalscraper.api.torrent import transmission as tmod

        c = _c()
        t = _mock_torrent(hash_string="ffffeeeeddddccccbbbbaaaa9999888877776666")
        c._client.add_torrent.return_value = t
        src = TorrentSource.from_magnet(MAGNET)
        with patch.object(tmod.log, "warning") as mock_warn:
            result = c.add(src)
        assert result == src.info_hash  # D6: source hash is canonical
        mock_warn.assert_called_once()
        call_args = mock_warn.call_args
        assert call_args[0][0] == "transmission_add_hash_mismatch"
        assert call_args[1]["echoed_hash"] == "ffffeeeeddddccccbbbbaaaa9999888877776666"
        assert call_args[1]["source_hash"] == src.info_hash
        assert "source-derived" in call_args[1]["hint"]

    def test_limits_raises_unsupported(self):
        """Passing limits raises UnsupportedCapabilityError (D8)."""
        c = _c()
        with pytest.raises(UnsupportedCapabilityError, match="limit"):
            c.add(TorrentSource.from_magnet(MAGNET), limits=TorrentLimits(ratio=1.0))

    def test_no_category_no_tags_empty_labels(self):
        """No category and no tags produces empty labels list."""
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET))
        assert c._client.add_torrent.call_args[1]["labels"] == []


class TestLabelsHelper:
    """Tests for _labels() helper (D5)."""

    def test_category_first(self):
        """Category appears first in labels list."""
        assert _labels("movies", ["action"]) == ["movies", "action"]

    def test_no_category(self):
        """None category is excluded from labels."""
        assert _labels(None, ["action"]) == ["action"]

    def test_both_none(self):
        """None category with empty tags produces empty list."""
        assert _labels(None, []) == []

    def test_dedup_category_in_tags(self):
        """Category appearing in tags is deduplicated, keeping category first."""
        r = _labels("movies", ["movies", "action"])
        assert r.count("movies") == 1
        assert r[0] == "movies"
