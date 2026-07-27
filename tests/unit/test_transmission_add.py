"""Tests for TransmissionClient.add() — DESIGN D1/D5/D7/D8."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import transmission_rpc

from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
from personalscraper.api.torrent.transmission import TransmissionClient, _labels, _split_labels

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

    def test_category_none_with_tags_uses_sentinel(self):
        """category=None + non-empty tags adds via the "" sentinel (F-A, open item #8 FINAL).

        The formerly-raised ``UnsupportedCapabilityError`` is gone: add() emits
        the same ``["", *tags]`` sentinel that add_tags writes and _split_labels
        decodes. Mutation-proof: the OLD guard raised before any RPC, so this
        test (which asserts add_torrent WAS called with the sentinel labels)
        fails on the pre-fix code and passes only after the guard is removed.
        """
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        result = c.add(TorrentSource.from_magnet(MAGNET), category=None, tags=["action"])
        # Write side: the tag lands behind the "" sentinel (labels[0] == "").
        assert c._client.add_torrent.call_args[1]["labels"] == ["", "action"]
        # Return contract unchanged (D6): source info_hash.
        assert result == TorrentSource.from_magnet(MAGNET).info_hash

    def test_category_none_with_tags_round_trips_via_read_side(self):
        """add(category=None, tags=[...]) → sentinel labels → _split_labels recovers (None, tags).

        Proves the full add→read round-trip integrity the sentinel guarantees:
        the "" category is decoded back to None (never leaks as a category) and
        the tags stay readable as tags (seed-pure readable — the ingest skip's
        contract).
        """
        c = _c()
        c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET), category=None, tags=["seed-pure", "extra"])
        written_labels = c._client.add_torrent.call_args[1]["labels"]
        category, tags = _split_labels(written_labels)
        assert category is None
        assert tags == ["seed-pure", "extra"]
        assert "seed-pure" in tags  # ingest SEED_PURE skip stays satisfiable


class TestLabelsHelper:
    """Tests for _labels() helper (D5)."""

    def test_category_first(self):
        """Category appears first in labels list."""
        assert _labels("movies", ["action"]) == ["movies", "action"]

    def test_no_category(self):
        """None category with tags uses the empty-string no-category sentinel (F-A).

        Previously this returned ``["action"]`` (the tag promoted to the
        category slot — the bug fixed in F-A). The sentinel keeps the tag
        readable as a tag on category-less torrents.
        """
        assert _labels(None, ["action"]) == ["", "action"]

    def test_both_none(self):
        """None category with empty tags produces empty list."""
        assert _labels(None, []) == []

    def test_dedup_category_in_tags(self):
        """Category appearing in tags is deduplicated, keeping category first."""
        r = _labels("movies", ["movies", "action"])
        assert r.count("movies") == 1
        assert r[0] == "movies"

    @pytest.mark.parametrize(
        ("category", "tags"),
        [
            ("movies", ["hd", "fr"]),
            ("movies", []),
            (None, []),
            (None, ["hd", "fr"]),  # sentinel case — F-A, now representable (open item #8)
            (None, ["seed-pure"]),  # the exact shape the ingest skip depends on
        ],
    )
    def test_d5_round_trip_stable_for_all_inputs(self, category, tags):
        """D5/F-A round-trip is stable for EVERY category/tags combination.

        Write labels via _labels, then read them back with the PRODUCTION read
        formula — ``_split_labels`` (the exact function _torrent_item uses), NOT
        the legacy naive ``labels[0]`` peek. The category-less-with-tags case
        (the "" sentinel) now round-trips just like the others: category recovers
        as None and the tags stay tags. This replaces the pre-fix test that
        excluded the sentinel case because it read labels[0] raw (open item #8).
        """
        labels = _labels(category, tags)
        read_category, read_tags = _split_labels(labels)
        assert read_category == category
        assert read_tags == tags
