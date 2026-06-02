"""Tests for TorrentSource and TorrentLimits (DESIGN §5.1, D1/D2/D6)."""

from __future__ import annotations

import base64
import hashlib

import pytest

from personalscraper.api.torrent._base import TorrentLimits, TorrentSource


def _bencode(obj: object) -> bytes:
    """Encode a Python value as bencode (test helper).

    Supports ``bytes``, ``int``, ``list`` and ``dict`` (with ``bytes`` keys).
    Dict keys are emitted in sorted order to match real ``.torrent`` shape
    (BEP-3 requires keys sorted as raw byte strings).

    Args:
        obj: Value to encode (bytes/int/list/dict).

    Returns:
        The bencoded byte string.

    Raises:
        TypeError: Unsupported type.
    """
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, bool):  # guard: bool is an int subclass
        raise TypeError("bool not supported in bencode")
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, list):
        return b"l" + b"".join(_bencode(x) for x in obj) + b"e"
    if isinstance(obj, dict):
        out = b"d"
        for key in sorted(obj):
            assert isinstance(key, bytes), "dict keys must be bytes"
            out += _bencode(key) + _bencode(obj[key])
        return out + b"e"
    raise TypeError(f"unsupported bencode type: {type(obj)!r}")


def _info_dict() -> dict[bytes, object]:
    """Return a representative single-file ``info`` dict (test helper).

    Returns:
        A dict with the canonical single-file torrent ``info`` keys.
    """
    return {
        b"length": 12345,
        b"name": b"some.movie.2024.mkv",
        b"piece length": 16384,
        b"pieces": b"\x00" * 20,
    }


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


# --- C1: structural bencode info_hash walk (regression for flat .find bug) ---


def test_info_hash_real_shape_golden() -> None:
    """info_hash hashes the top-level ``info`` value of a real-shaped torrent (C1, a).

    The top-level dict carries ``announce``, ``comment``, ``created by`` keys
    (sorted before ``info``) — a flat ``data.find(b"4:info")`` would anchor
    correctly here only by luck. The hash MUST equal sha1 over the bencoded
    info segment exactly.
    """
    info = _info_dict()
    torrent = {
        b"announce": b"http://tracker.example/announce",
        b"comment": b"a perfectly ordinary comment",
        b"created by": b"mktorrent 1.1",
        b"info": info,
    }
    data = _bencode(torrent)
    expected = hashlib.sha1(_bencode(info)).hexdigest()
    assert TorrentSource.from_file(data).info_hash == expected


def test_info_hash_decoy_4info_in_comment() -> None:
    """info_hash ignores a ``4:info`` substring inside a sibling value (C1, b).

    A ``comment`` value literally containing the bytes ``4:info`` MUST NOT
    derail the parse: the only ``info`` that counts is the top-level key. The
    flat ``data.find(b"4:info")`` implementation crashes or returns the wrong
    hash on this input.
    """
    info = _info_dict()
    torrent = {
        b"announce": b"http://tracker.example/announce",
        # decoy: contains the literal bytes the old flat scanner anchored on.
        b"comment": b"see 4:infohash details below 4:info",
        b"info": info,
    }
    data = _bencode(torrent)
    expected = hashlib.sha1(_bencode(info)).hexdigest()
    assert TorrentSource.from_file(data).info_hash == expected


def test_info_hash_announce_list_before_info() -> None:
    """info_hash walks past an ``announce-list`` list-of-lists value (C1, c).

    Exercises the recursive l/d walk in ``_bencode_end`` for a nested list
    sibling that precedes ``info`` alphabetically.
    """
    info = _info_dict()
    torrent = {
        b"announce": b"http://primary.example/announce",
        b"announce-list": [
            [b"http://primary.example/announce"],
            [b"http://backup.example/announce", b"udp://backup.example:80"],
        ],
        b"info": info,
    }
    data = _bencode(torrent)
    expected = hashlib.sha1(_bencode(info)).hexdigest()
    assert TorrentSource.from_file(data).info_hash == expected


def test_info_hash_not_a_dict_raises() -> None:
    """info_hash raises ValueError when bytes are not a top-level bencoded dict."""
    with pytest.raises(ValueError, match="bencoded dict"):
        TorrentSource.from_file(b"li1ee").info_hash


def test_info_hash_no_info_key_raises() -> None:
    """info_hash raises ValueError when there is no top-level ``info`` key."""
    data = _bencode({b"announce": b"http://x/announce"})
    with pytest.raises(ValueError, match="info"):
        TorrentSource.from_file(data).info_hash


# --- Md2: harden _bencode_end (bounds + recursion depth) ---


def test_info_hash_truncated_string_length_raises() -> None:
    """info_hash raises ValueError on a declared length beyond the buffer (Md2, e).

    The ``name`` string declares 999 bytes but only a few remain — an
    out-of-bounds slice must be rejected, not silently truncated.
    """
    # Hand-built dict: info value has a string with an over-long length prefix.
    data = b"d4:infod4:name999:short_valuee" + b"e"
    with pytest.raises(ValueError):
        TorrentSource.from_file(data).info_hash


def test_info_hash_deep_nesting_raises() -> None:
    """info_hash raises ValueError on adversarially deep nesting (Md2)."""
    # 500 nested lists as the info value — exceeds the recursion cap.
    deep = b"l" * 500 + b"e" * 500
    data = b"d4:info" + deep + b"e"
    with pytest.raises(ValueError):
        TorrentSource.from_file(data).info_hash


# --- Md3: base32 magnets ---


def test_info_hash_magnet_base32() -> None:
    """info_hash decodes a 32-char base32 btih to lowercase hex (Md3, d, BEP-9)."""
    raw = bytes(range(20))  # 20-byte info hash
    b32 = base64.b32encode(raw).decode().rstrip("=")
    assert len(b32) == 32
    uri = f"magnet:?xt=urn:btih:{b32}&dn=x"
    assert TorrentSource.from_magnet(uri).info_hash == raw.hex()


def test_info_hash_magnet_base32_lowercase_input() -> None:
    """info_hash accepts a lowercase base32 btih (case-insensitive, Md3)."""
    raw = bytes(range(20, 40))
    b32 = base64.b32encode(raw).decode().rstrip("=").lower()
    uri = f"magnet:?xt=urn:btih:{b32}"
    assert TorrentSource.from_magnet(uri).info_hash == raw.hex()


# --- Md4: reject empty-but-present source values ---


def test_empty_magnet_raises() -> None:
    """TorrentSource(magnet="") treats empty as not-set → ValueError (Md4, e)."""
    with pytest.raises(ValueError, match="exactly one"):
        TorrentSource(magnet="")


def test_empty_file_bytes_raises() -> None:
    """TorrentSource.from_file(b"") treats empty as not-set → ValueError (Md4, e)."""
    with pytest.raises(ValueError, match="exactly one"):
        TorrentSource.from_file(b"")
