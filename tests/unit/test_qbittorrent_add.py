"""Tests for QBitClient.add() — DESIGN D1/D6/D7/D8."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import qbittorrentapi

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder
from personalscraper.api.torrent.qbittorrent import QBitClient

MAGNET = "magnet:?xt=urn:btih:aabbcc112233ddeeff00112233445566778899aa&dn=t"


def _c() -> QBitClient:
    """Build a QBitClient with a mocked underlying client."""
    c = QBitClient("localhost", 8080, "u", "p")
    c._client = MagicMock()
    return c


def test_qbit_is_torrent_adder() -> None:
    """``QBitClient`` satisfies :class:`TorrentAdder`."""
    assert isinstance(_c(), TorrentAdder)


def test_add_magnet_calls_torrents_add() -> None:
    """``add()`` with magnet calls ``torrents_add`` with urls, category, tags."""
    c = _c()
    c._client.torrents_add.return_value = "Ok"
    c.add(TorrentSource.from_magnet(MAGNET), category="movies", tags=["action"])
    kw = c._client.torrents_add.call_args[1]
    assert kw["urls"] == MAGNET
    assert kw["category"] == "movies"
    assert kw["tags"] == ["action"]


def test_add_file_bytes_uses_torrent_files() -> None:
    """``add()`` with file bytes passes ``torrent_files`` to ``torrents_add``."""
    c = _c()
    c._client.torrents_add.return_value = "Ok"
    # Patch info_hash — b"bytes" is not a valid .torrent bencode, but the
    # test only cares about the torrents_add kwargs, not hash derivation.
    with patch.object(TorrentSource, "info_hash", return_value="abc123"):
        c.add(TorrentSource.from_file(b"bytes"))
    kw = c._client.torrents_add.call_args[1]
    assert kw.get("torrent_files") == b"bytes"
    assert not kw.get("urls")


def test_add_paused_forwarded() -> None:
    """``add()`` with paused=True sets ``is_paused`` in ``torrents_add``."""
    c = _c()
    c._client.torrents_add.return_value = "Ok"
    c.add(TorrentSource.from_magnet(MAGNET), paused=True)
    assert c._client.torrents_add.call_args[1]["is_paused"] is True


def test_add_returns_info_hash() -> None:
    """``add()`` returns the source info_hash."""
    c = _c()
    c._client.torrents_add.return_value = "Ok"
    src = TorrentSource.from_magnet(MAGNET)
    assert c.add(src) == src.info_hash


def test_add_idempotent_on_duplicate() -> None:
    """``add()`` on duplicate returns info_hash without exception (D7)."""
    c = _c()
    c._client.torrents_add.return_value = "Fails."
    src = TorrentSource.from_magnet(MAGNET)
    assert c.add(src) == src.info_hash  # no exception, returns hash (D7)


def test_add_with_limits_sets_ratio_and_upload() -> None:
    """``add()`` with limits passes ratio and upload limit to ``torrents_add``."""
    c = _c()
    c._client.torrents_add.return_value = "Ok"
    c.add(
        TorrentSource.from_magnet(MAGNET),
        limits=TorrentLimits(ratio=2.0, up_bytes_per_s=1024),
    )
    kw = c._client.torrents_add.call_args[1]
    assert kw.get("ratio_limit") == 2.0
    assert kw.get("upload_limit") == 1024


def test_add_forbidden_raises_api_error() -> None:
    """``add()`` raises ``ApiError`` with http_status 403 on ``Forbidden403Error``."""
    c = _c()
    c._client.torrents_add.side_effect = qbittorrentapi.Forbidden403Error("ban")
    with pytest.raises(ApiError) as ei:
        c.add(TorrentSource.from_magnet(MAGNET))
    assert ei.value.http_status == 403
