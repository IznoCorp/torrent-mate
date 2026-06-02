"""Tests for TorrentSource and TorrentLimits (DESIGN §5.1, D1/D2/D6)."""

from __future__ import annotations

import hashlib

import pytest

from personalscraper.api.torrent._base import TorrentLimits, TorrentSource


def test_from_magnet() -> None:
    """TorrentSource.from_magnet sets magnet and leaves file_bytes None."""
    s = TorrentSource.from_magnet("magnet:?xt=urn:btih:aabb&dn=x")
    assert s.magnet
    assert s.file_bytes is None


def test_from_file() -> None:
    """TorrentSource.from_file sets file_bytes and leaves magnet None."""
    s = TorrentSource.from_file(b"\x00")
    assert s.file_bytes
    assert s.magnet is None


def test_neither_raises() -> None:
    """TorrentSource with both fields None raises ValueError."""
    with pytest.raises(ValueError, match="exactly one"):
        TorrentSource(magnet=None, file_bytes=None)


def test_both_raises() -> None:
    """TorrentSource with both fields set raises ValueError."""
    with pytest.raises(ValueError, match="exactly one"):
        TorrentSource(magnet="magnet:?xt=urn:btih:aabb", file_bytes=b"\x00")


def test_info_hash_magnet() -> None:
    """info_hash parses btih from magnet URI and lowercases it."""
    uri = "magnet:?xt=urn:btih:AABBCC112233DDEEFF00112233445566778899AA&dn=x"
    result = TorrentSource.from_magnet(uri).info_hash
    assert result == "aabbcc112233ddeeff00112233445566778899aa"


def test_info_hash_bytes() -> None:
    """info_hash computes SHA-1 of the bencoded info dict from .torrent bytes."""
    info = b"d6:lengthi0e4:name1:x12:piece lengthi16384e6:pieces20:" + b"\x00" * 20 + b"e"
    result = TorrentSource.from_file(b"d4:info" + info + b"e").info_hash
    assert result == hashlib.sha1(info).hexdigest()


def test_source_frozen() -> None:
    """TorrentSource is frozen — mutation raises AttributeError or TypeError."""
    s = TorrentSource.from_magnet("magnet:?xt=urn:btih:aabb")
    with pytest.raises((AttributeError, TypeError)):
        s.magnet = "x"  # type: ignore[misc]


def test_limits_all_none() -> None:
    """TorrentLimits() default-constructs with all fields None."""
    lim = TorrentLimits()
    assert lim.ratio is None
    assert lim.up_bytes_per_s is None


def test_limits_partial() -> None:
    """TorrentLimits allows partial construction with only some fields set."""
    lim = TorrentLimits(ratio=2.0)
    assert lim.ratio == 2.0
    assert lim.seed_time_minutes is None


def test_limits_frozen() -> None:
    """TorrentLimits is frozen — mutation raises AttributeError or TypeError."""
    with pytest.raises((AttributeError, TypeError)):
        TorrentLimits(ratio=1.0).ratio = 2.0  # type: ignore[misc]
