"""Torrent family base — TorrentItem dataclass, TorrentSource and TorrentLimits value objects.

Implements DESIGN §5.1.
"""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from pathlib import Path

# Maximum bencode nesting depth. A legitimate ``.torrent`` is shallow
# (top-level dict → info dict → a few lists); anything deeper is adversarial
# and could blow the Python recursion stack (Md2 hardening).
_MAX_BENCODE_DEPTH = 100


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
        tags: List of tag labels (default ``[]``).
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
    tags: list[str] = field(default_factory=list)
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

        Empty-but-present values (``magnet=""`` / ``file_bytes=b""``) are treated
        as *not set* (Md4): an empty magnet or zero-byte ``.torrent`` carries no
        usable source, so the exactly-one invariant rejects neither/both AND
        empty values.

        Raises:
            ValueError: Both or neither (incl. empty) fields are set.
        """
        # ``or None`` collapses falsy empties ("" / b"") to None for the check.
        has_magnet = (self.magnet or None) is not None
        has_bytes = (self.file_bytes or None) is not None
        if has_magnet == has_bytes:
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

    Supports both BEP-9 btih encodings:

    * 40-char hex (``urn:btih:<40 hex>``) — returned lower-cased verbatim.
    * 32-char base32 (``urn:btih:<32 base32>``) — base32-decoded to 20 raw
      bytes then hex-encoded (lower-case). Case-insensitive per RFC 4648.

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
    # Base32 btih (BEP-9): exactly 32 chars from the RFC 4648 base32 alphabet.
    m = re.search(r"urn:btih:([A-Za-z2-7]{32})(?![A-Za-z2-7])", uri)
    if m:
        return base64.b32decode(m.group(1).upper()).hex()
    raise ValueError(f"Cannot extract btih from magnet URI: {uri!r}")


def _bencode_str(data: bytes, pos: int) -> tuple[bytes, int]:
    """Read a bencoded byte-string (``<len>:<bytes>``) starting at ``pos``.

    Used to read the *keys* of the top-level dict structurally (C1) — never
    relies on scanning for a substring inside arbitrary value bytes.

    Args:
        data: Full bencode bytes.
        pos: Index of the leading length digit.

    Returns:
        A ``(value, end)`` pair: the decoded byte-string and the index one past
        it.

    Raises:
        ValueError: Not a string here, or the declared length overruns the buffer.
    """
    if pos >= len(data) or not (b"0" <= data[pos : pos + 1] <= b"9"):
        raise ValueError(f"expected a bencoded string at {pos}")
    col = data.index(b":", pos)
    length = int(data[pos:col])
    start = col + 1
    end = start + length
    if end > len(data):
        raise ValueError("bencode string truncated")
    return data[start:end], end


def _bencode_info_hash(data: bytes) -> str:
    """SHA-1 of the top-level ``info`` dict inside a .torrent file (D6, C1).

    Walks the top-level bencoded dictionary *structurally* — confirming the
    leading ``d`` token, then reading each ``key/value`` pair where the key is a
    bencoded byte-string and the value spans ``_bencode_end``. The hash is taken
    over the raw bytes of the value whose key is exactly ``b"info"`` at the top
    level. A substring ``4:info`` buried inside a sibling value (e.g. a tracker-
    or user-controlled ``comment``/``announce`` field) is therefore ignored —
    fixing the flat ``data.find(b"4:info")`` info-hash forgery/crash bug.

    Args:
        data: Raw ``.torrent`` bytes.

    Returns:
        Lowercase hex SHA-1 of the ``info`` value.

    Raises:
        ValueError: Not a bencoded dict, malformed bencode, or no top-level
            ``info`` key.
    """
    if data[:1] != b"d":
        raise ValueError("not a bencoded dict")
    pos = 1
    while pos < len(data) and data[pos : pos + 1] != b"e":
        key, pos = _bencode_str(data, pos)
        value_start = pos
        value_end = _bencode_end(data, value_start)
        if key == b"info":
            return hashlib.sha1(data[value_start:value_end]).hexdigest()
        pos = value_end
    raise ValueError("No 'info' key in .torrent bencode")


def _bencode_end(data: bytes, pos: int, depth: int = 0) -> int:
    """Return index one past end of bencoded value at pos.

    Args:
        data: Full bencode bytes.
        pos: Start position of a value.
        depth: Current nesting depth (recursion guard, Md2).

    Returns:
        First byte after the value.

    Raises:
        ValueError: Unknown token, truncated data, out-of-bounds string length,
            or nesting beyond ``_MAX_BENCODE_DEPTH``.
    """
    if depth > _MAX_BENCODE_DEPTH:
        raise ValueError("bencode nesting too deep")
    if pos >= len(data):
        raise ValueError("bencode truncated")
    tok = data[pos : pos + 1]
    if tok in (b"d", b"l"):
        pos += 1
        while True:
            if pos >= len(data):
                raise ValueError("bencode truncated")
            if data[pos : pos + 1] == b"e":
                break
            pos = _bencode_end(data, pos, depth + 1)
        return pos + 1
    if tok == b"i":
        return data.index(b"e", pos + 1) + 1
    if b"0" <= tok <= b"9":
        col = data.index(b":", pos)
        end = col + 1 + int(data[pos:col])
        if end > len(data):
            raise ValueError("bencode string truncated")
        return end
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
