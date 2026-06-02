"""Torrent family base — TorrentItem dataclass, TorrentSource and TorrentLimits value objects.

Implements DESIGN §5.1.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from pathlib import Path


@dataclass
class TorrentItem:
    """A torrent tracked by a torrent client.

    Attributes:
        hash: Torrent info hash.
        name: Torrent display name.
        size_bytes: Total size in bytes.
        progress: Download progress (0.0 to 1.0).
        state: Current torrent state (e.g. "uploading", "pausedUP").
        content_path: Filesystem path to torrent content.
        category: Torrent category label, if any.
        added_on: Timestamp when the torrent was added.
        ratio: Seed ratio (uploaded / downloaded). 0.0 if never seeded.
            Used by ``ingest`` to enforce ``config.ingest.min_ratio``.
    """

    hash: str
    name: str
    size_bytes: int
    progress: float
    state: str
    content_path: Path | None = None
    category: str | None = None
    added_on: datetime | None = None
    ratio: float = 0.0


@dataclass(frozen=True)
class TorrentSource:
    """Discriminated torrent source (D1/§5.1).

    Attributes:
        magnet: Magnet URI string.
        file_bytes: Raw ``.torrent`` file bytes.
    """

    magnet: str | None = None
    file_bytes: bytes | None = None

    def __post_init__(self) -> None:
        """Validate exactly one field is set.

        Raises:
            ValueError: Both or neither fields are set.
        """
        if (self.magnet is not None) == (self.file_bytes is not None):
            raise ValueError("TorrentSource requires exactly one of magnet or file_bytes")

    @classmethod
    def from_magnet(cls, uri: str) -> "TorrentSource":
        """Build from magnet URI.

        Args:
            uri: Magnet URI string.

        Returns:
            TorrentSource with magnet set.
        """
        return cls(magnet=uri)

    @classmethod
    def from_file(cls, data: bytes) -> "TorrentSource":
        """Build from raw .torrent bytes.

        Args:
            data: Raw ``.torrent`` file bytes.

        Returns:
            TorrentSource with file_bytes set.
        """
        return cls(file_bytes=data)

    @cached_property
    def info_hash(self) -> str:
        """Derive info_hash from source (D6).

        Returns:
            Lowercase hex SHA-1 info_hash.

        Raises:
            ValueError: Cannot extract hash.
        """
        if self.magnet is not None:
            return _parse_magnet_hash(self.magnet)
        assert self.file_bytes is not None
        return _bencode_info_hash(self.file_bytes)


@dataclass(frozen=True)
class TorrentLimits:
    """Transfer limits for a newly added torrent (D2/§5.1).

    All fields optional; all-None = no-op. Passing a non-None instance to a
    client without TorrentLimiter raises UnsupportedCapabilityError (D8).

    Attributes:
        ratio: Stop seeding at this upload/download ratio.
        seed_time_minutes: Stop seeding after N minutes.
        up_bytes_per_s: Upload cap in bytes/s.
        down_bytes_per_s: Download cap in bytes/s.
    """

    ratio: float | None = None
    seed_time_minutes: int | None = None
    up_bytes_per_s: int | None = None
    down_bytes_per_s: int | None = None


def _parse_magnet_hash(uri: str) -> str:
    """Extract lowercase hex btih from a magnet URI.

    Args:
        uri: Magnet URI string.

    Returns:
        Lowercase hex info_hash.

    Raises:
        ValueError: No btih parameter found.
    """
    m = re.search(r"urn:btih:([0-9a-fA-F]{40})", uri)
    if m:
        return m.group(1).lower()
    raise ValueError(f"Cannot extract btih from magnet URI: {uri!r}")


def _bencode_info_hash(data: bytes) -> str:
    """SHA-1 of the bencoded info dict inside a .torrent file (D6).

    Args:
        data: Raw ``.torrent`` bytes.

    Returns:
        Lowercase hex SHA-1.

    Raises:
        ValueError: No info key or malformed bencode.
    """
    key = b"4:info"
    idx = data.find(key)
    if idx == -1:
        raise ValueError("No 'info' key in .torrent bencode")
    start = idx + len(key)
    end = _bencode_end(data, start)
    return hashlib.sha1(data[start:end]).hexdigest()


def _bencode_end(data: bytes, pos: int) -> int:
    """Return index one past end of bencoded value at pos.

    Args:
        data: Full bencode bytes.
        pos: Start position of a value.

    Returns:
        First byte after the value.

    Raises:
        ValueError: Unknown token or truncated data.
    """
    if pos >= len(data):
        raise ValueError("bencode truncated")
    tok = data[pos : pos + 1]
    if tok in (b"d", b"l"):
        pos += 1
        while data[pos : pos + 1] != b"e":
            pos = _bencode_end(data, pos)
        return pos + 1
    if tok == b"i":
        return data.index(b"e", pos + 1) + 1
    if b"0" <= tok <= b"9":
        col = data.index(b":", pos)
        return col + 1 + int(data[pos:col])
    raise ValueError(f"Unknown bencode token {tok!r} at {pos}")


# NOTE — provider-ids feature, sub-phase 13.1 :
# The historical monolithic ``TorrentClient(Protocol)`` defined here
# was dropped in favour of the 5 atomic capability protocols hosted in
# ``personalscraper.api.torrent._contracts``. The factory returns
# ``QBitClient | TransmissionClient`` directly ; callers type their
# dependency via the atomic protocol they actually consume, and those
# that need authentication assert ``AuthenticatedClient`` via isinstance
# (DESIGN §4 — Composition par client). The former composite
# ``TorrentClientFull`` was also dropped in 0.16.0 (MUST-14, CF-B).
