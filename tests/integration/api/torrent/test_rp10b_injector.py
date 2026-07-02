"""Integration tests for RP10b TorrentInjector protocol — inject, list_files, properties.

Covers sub-phase 2.5 of the watch-seed feature (RP10b): integration tests against
a mocked QBitClient verifying TorrentInjector protocol conformance (ACC-3),
TorrentItem mapper extension (save_path/completion_on), and inject/list_files/
properties behaviour with the qbittorrentapi library interface.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import qbittorrentapi

from personalscraper.api.torrent._base import _bencode_info_hash
from personalscraper.api.torrent._contracts import TorrentInjector
from personalscraper.api.torrent.qbittorrent import QBitClient, _torrent_item

# ---- Minimal valid bencode for a single-file .torrent -----------------------
# The info dict encodes: length=1234, name="test", piece length=262144,
# pieces=<20 bytes of 'a'> (one fake SHA-1 piece hash).  The SHA-1 of
# these info bytes is the torrent's v1 info-hash.

_INFO_BYTES = b"d6:lengthi1234e4:name4:test12:piece lengthi262144e6:pieces20:aaaaaaaaaaaaaaaaaaaae"
_TORRENT_BYTES = b"d4:info" + _INFO_BYTES + b"8:announce0:e"
_EXPECTED_INFO_HASH = _bencode_info_hash(_TORRENT_BYTES)


class TestInject:
    """inject() integration tests — save_path, recheck, Conflict409."""

    @staticmethod
    def _client() -> QBitClient:
        """Build a QBitClient with a mocked underlying qbittorrentapi.Client."""
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        return c

    def test_inject_posts_with_correct_savepath(self) -> None:
        """torrents_add receives save_path, is_skip_checking=False, is_paused=True."""
        client = self._client()
        client.inject(_TORRENT_BYTES, save_path="/data/movies", recheck=True, paused=True)
        client._client.torrents_add.assert_called_once_with(  # type: ignore[attr-defined]
            torrent_files=_TORRENT_BYTES,
            save_path="/data/movies",
            is_skip_checking=False,
            is_paused=True,
        )

    def test_inject_recheck_called(self) -> None:
        """torrents_recheck called with the computed v1 info-hash."""
        client = self._client()
        client.inject(_TORRENT_BYTES, save_path="/data/movies", recheck=True)
        client._client.torrents_recheck.assert_called_once_with(  # type: ignore[attr-defined]
            torrent_hashes=_EXPECTED_INFO_HASH,
        )

    def test_inject_conflict409_idempotent(self) -> None:
        """Conflict409Error → returns info_hash AND still issues recheck."""
        client = self._client()
        client._client.torrents_add.side_effect = qbittorrentapi.Conflict409Error(  # type: ignore[attr-defined]
            "duplicate"
        )
        result = client.inject(_TORRENT_BYTES, save_path="/data/movies", recheck=True)
        assert result == _EXPECTED_INFO_HASH
        client._client.torrents_recheck.assert_called_once_with(  # type: ignore[attr-defined]
            torrent_hashes=_EXPECTED_INFO_HASH,
        )


class TestListFiles:
    """list_files() integration tests — name/size pairs."""

    @staticmethod
    def _client() -> QBitClient:
        """Build a QBitClient with a mocked underlying qbittorrentapi.Client."""
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        return c

    def test_list_files_returns_name_size_pairs(self) -> None:
        """Mocked torrents_files response → ordered list[tuple[str, int]]."""
        client = self._client()
        f1 = MagicMock()
        f1.name = "video.mkv"
        f1.size = 5000000000
        f2 = MagicMock()
        f2.name = "subtitle.srt"
        f2.size = 45000
        client._client.torrents_files.return_value = [f1, f2]  # type: ignore[attr-defined]

        result = client.list_files("abc123")
        assert result == [("video.mkv", 5000000000), ("subtitle.srt", 45000)]


class TestProperties:
    """properties() integration tests — piece_size key."""

    @staticmethod
    def _client() -> QBitClient:
        """Build a QBitClient with a mocked underlying qbittorrentapi.Client."""
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        return c

    def test_properties_includes_piece_size(self) -> None:
        """Returned dict contains piece_size key from the API response."""
        client = self._client()
        client._client.torrents_properties.return_value = {  # type: ignore[attr-defined]
            "piece_size": 262144,
            "comment": "test torrent",
        }
        result = client.properties("abc123")
        assert "piece_size" in result
        assert result["piece_size"] == 262144


class TestTorrentInjectorProtocol:
    """TorrentInjector isinstance checks (ACC-3)."""

    def test_torrent_injector_isinstance_qbit(self) -> None:
        """isinstance(QBitClient, TorrentInjector) is True."""
        c = QBitClient("localhost", 8081, "admin", "pass")
        c._client = MagicMock()
        assert isinstance(c, TorrentInjector)

    @patch("personalscraper.api.torrent.transmission.transmission_rpc.Client")
    def test_torrent_injector_not_transmission(self, mock_client_cls: MagicMock) -> None:
        """isinstance(TransmissionClient, TorrentInjector) is False (ACC-3)."""
        from personalscraper.api.torrent.transmission import TransmissionClient  # noqa: PLC0415

        t = TransmissionClient("localhost", 9091, "admin", "pass")
        assert not isinstance(t, TorrentInjector)


class TestTorrentItemMapper:
    """_torrent_item save_path and completion_on population."""

    @staticmethod
    def _make_torrent_dict(**overrides: object) -> MagicMock:
        """Build a MagicMock resembling a qbittorrentapi TorrentDictionary.

        All fields carry realistic int/str values (not MagicMock defaults)
        so the mapper's isinstance guards behave as they would against a
        real API response.  Override any field via kwargs.

        Returns:
            A configured MagicMock with TorrentDictionary-like attributes.
        """
        t = MagicMock()
        t.hash = "abc123def456"
        t.name = "Test Torrent"
        t.total_size = 5000000000
        t.progress = 1.0
        t.state = "uploading"
        t.ratio = 2.0
        t.content_path = "/data/test"
        t.category = "movies"
        t.tags = "tag1,tag2"
        t.added_on = 1712345678
        t.save_path = "/downloads"
        t.completion_on = 1712345678
        for k, v in overrides.items():
            setattr(t, k, v)
        return t

    def test_torrent_item_save_path_and_completion_on(self) -> None:
        """Mapper populates save_path and completion_on from a TorrentDictionary-like object.

        completion_on=-1 → None, completion_on=0 → None, completion_on>0 → value.
        save_path is read as-is when it is a str.
        """
        # completion_on > 0 → preserved
        mock = self._make_torrent_dict(save_path="/data/movies/completed", completion_on=1712345678)
        item = _torrent_item(mock)
        assert item.save_path == "/data/movies/completed"
        assert item.completion_on == 1712345678

        # completion_on == -1 → None (never completed)
        mock_never = self._make_torrent_dict(completion_on=-1)
        item_never = _torrent_item(mock_never)
        assert item_never.completion_on is None

        # completion_on == 0 → None (qBit default for never-completed)
        mock_zero = self._make_torrent_dict(completion_on=0)
        item_zero = _torrent_item(mock_zero)
        assert item_zero.completion_on is None

        # save_path still populated when completion_on is None
        mock_partial = self._make_torrent_dict(save_path="/other/path", completion_on=-1)
        item_partial = _torrent_item(mock_partial)
        assert item_partial.save_path == "/other/path"
        assert item_partial.completion_on is None
