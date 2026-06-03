"""Tests for QBitClient.add() — DESIGN D1/D6/D7/D8."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
import qbittorrentapi

from personalscraper.api._contracts import ApiError
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter
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
    with patch.object(TorrentSource, "info_hash", new_callable=PropertyMock, return_value="abc123"):
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
    """``add()`` on duplicate returns info_hash without exception (D7).

    The library raises ``Conflict409Error`` when the torrent is already
    present — this is the real duplicate signal, mapped to idempotent success.
    """
    c = _c()
    c._client.torrents_add.side_effect = qbittorrentapi.Conflict409Error("already added")
    src = TorrentSource.from_magnet(MAGNET)
    assert c.add(src) == src.info_hash  # no exception, returns hash (D7)


def test_add_fails_string_raises() -> None:
    """``add()`` raises ``ApiError`` when ``torrents_add`` returns ``"Fails."`` (D8).

    ``"Fails."`` is a generic failure (bad magnet, disk full, bad save path),
    NOT a duplicate — it must surface as an observable error, never a silent
    fake-success.
    """
    c = _c()
    c._client.torrents_add.return_value = "Fails."
    with pytest.raises(ApiError):
        c.add(TorrentSource.from_magnet(MAGNET))


def test_add_metadata_object_return_is_success() -> None:
    """``add()`` treats a non-str ``TorrentsAddedMetadata`` return as success (review #3).

    qBit Web API v2.14.0+ returns a ``TorrentsAddedMetadata`` mapping (not the
    plain-text ``"Ok."``) on a successful add. The success check must NOT
    ``str()``-compare it (the repr never equals ``"ok"``), which would
    misreport a real success as ``ApiError`` and leave the torrent added while
    the caller sees an exception. A non-str result is only ever returned on a
    2xx success (HTTP failures already raise above), so it maps to info_hash.
    """
    from qbittorrentapi.torrents import TorrentsAddedMetadata

    c = _c()
    c._client.torrents_add.return_value = TorrentsAddedMetadata({"hash": "deadbeef"})
    src = TorrentSource.from_magnet(MAGNET)
    assert c.add(src) == src.info_hash  # success, not a false ApiError


def test_add_corrupt_payload_raises() -> None:
    """``add()`` raises ``ApiError`` on a corrupt ``.torrent`` payload (D8).

    The library raises ``UnsupportedMediaType415Error`` (and the
    ``TorrentFileError`` family) for malformed torrent files — the failure
    must be observable rather than silently swallowed.
    """
    c = _c()
    c._client.torrents_add.side_effect = qbittorrentapi.UnsupportedMediaType415Error("corrupt")
    with pytest.raises(ApiError) as ei:
        c.add(TorrentSource.from_magnet(MAGNET))
    assert ei.value.http_status == 415


def test_add_torrent_file_error_raises() -> None:
    """``add()`` raises ``ApiError`` on a ``TorrentFileError`` (D8)."""
    c = _c()
    c._client.torrents_add.side_effect = qbittorrentapi.TorrentFileNotFoundError("missing")
    with pytest.raises(ApiError):
        c.add(TorrentSource.from_magnet(MAGNET))


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


def test_add_unauthorized_401_raises_api_error() -> None:
    """``add()`` raises ``ApiError`` (http_status 401) on ``Unauthorized401Error``.

    A real 401 on ``torrents_add`` is ``qbittorrentapi.Unauthorized401Error``
    (``HTTP401Error`` MRO), a DISTINCT class from ``LoginFailed`` — neither
    subclasses the other. Catching only ``LoginFailed`` let a genuine 401
    escape ``add()`` uncaught; it must now map to a uniform ``ApiError`` (D8).
    """
    c = _c()
    c._client.torrents_add.side_effect = qbittorrentapi.Unauthorized401Error("unauthorized")
    with pytest.raises(ApiError) as ei:
        c.add(TorrentSource.from_magnet(MAGNET))
    assert ei.value.http_status == 401


class TestQBitClientApplyLimits:
    """qBittorrent ``apply_limits()`` tests — DESIGN D2."""

    def test_qbit_is_torrent_limiter(self) -> None:
        """``QBitClient`` satisfies :class:`TorrentLimiter`."""
        assert isinstance(_c(), TorrentLimiter)

    def test_apply_ratio_calls_set_share_limits(self) -> None:
        """``apply_limits()`` with ratio calls ``torrents_set_share_limits``."""
        c = _c()
        c.apply_limits("abc", TorrentLimits(ratio=1.5))
        kw = c._client.torrents_set_share_limits.call_args[1]
        assert kw["torrent_hashes"] == "abc"
        assert kw["ratio_limit"] == 1.5
        assert "seeding_time_limit" not in kw

    def test_apply_upload_calls_set_upload_limit(self) -> None:
        """``apply_limits()`` with upload limit calls ``torrents_set_upload_limit``."""
        c = _c()
        c.apply_limits("abc", TorrentLimits(up_bytes_per_s=512))
        c._client.torrents_set_upload_limit.assert_called_once_with(
            torrent_hashes="abc",
            limit=512,
        )

    def test_apply_download_calls_set_download_limit(self) -> None:
        """``apply_limits()`` with download limit calls ``torrents_set_download_limit``."""
        c = _c()
        c.apply_limits("abc", TorrentLimits(down_bytes_per_s=1024))
        c._client.torrents_set_download_limit.assert_called_once_with(
            torrent_hashes="abc",
            limit=1024,
        )

    def test_all_none_is_noop(self) -> None:
        """``apply_limits()`` with all-None limits is a no-op."""
        c = _c()
        c.apply_limits("abc", TorrentLimits())
        c._client.torrents_set_share_limits.assert_not_called()
        c._client.torrents_set_upload_limit.assert_not_called()
        c._client.torrents_set_download_limit.assert_not_called()

    def test_seed_time_minutes_passed_directly(self) -> None:
        """``apply_limits()`` passes seed_time_minutes directly (qBit uses minutes)."""
        c = _c()
        c.apply_limits("abc", TorrentLimits(seed_time_minutes=30))
        kw = c._client.torrents_set_share_limits.call_args[1]
        assert kw["seeding_time_limit"] == 30
        assert kw["torrent_hashes"] == "abc"

    def test_apply_ratio_only_no_seedtime_sentinel(self) -> None:
        """``apply_limits(ratio=2.0)`` does NOT send ``seeding_time_limit=-2`` (Md1)."""
        c = _c()
        c.apply_limits("h", TorrentLimits(ratio=2.0))
        kw = c._client.torrents_set_share_limits.call_args[1]
        assert kw["ratio_limit"] == 2.0
        assert "seeding_time_limit" not in kw
