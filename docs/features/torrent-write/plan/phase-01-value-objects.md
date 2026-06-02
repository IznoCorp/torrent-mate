# Phase 01 — `TorrentSource` and `TorrentLimits` Value Objects

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Add `TorrentSource` (frozen dataclass, discriminated magnet|file_bytes, stdlib `info_hash`) and `TorrentLimits` (frozen dataclass, all-optional) to `api/torrent/_base.py`. 1 commit.

**Tech Stack:** Python 3.11, `dataclasses`, `hashlib`, `re`, `functools.cached_property`, pytest

---

## Gate

_First phase — no prior gate._

---

## Files

- Modify: `personalscraper/api/torrent/_base.py`
- Create: `tests/unit/test_torrent_source.py`

---

## Steps

- [ ] **1. Write the failing tests** in `tests/unit/test_torrent_source.py`:

```python
"""Tests for TorrentSource and TorrentLimits (DESIGN §5.1, D1/D2/D6)."""
from __future__ import annotations
import hashlib, pytest
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource

def test_from_magnet(): s = TorrentSource.from_magnet("magnet:?xt=urn:btih:aabb&dn=x"); assert s.magnet and s.file_bytes is None
def test_from_file(): s = TorrentSource.from_file(b"\x00"); assert s.file_bytes and s.magnet is None
def test_neither_raises():
    with pytest.raises(ValueError, match="exactly one"): TorrentSource(magnet=None, file_bytes=None)
def test_both_raises():
    with pytest.raises(ValueError, match="exactly one"): TorrentSource(magnet="magnet:?xt=urn:btih:aabb", file_bytes=b"\x00")
def test_info_hash_magnet():
    uri = "magnet:?xt=urn:btih:AABBCC112233DDEEFF00112233445566778899AA&dn=x"
    assert TorrentSource.from_magnet(uri).info_hash == "aabbcc112233ddeeff00112233445566778899aa"
def test_info_hash_bytes():
    info = b"d6:lengthi0e4:name1:x12:piece lengthi16384e6:pieces20:" + b"\x00"*20 + b"e"
    assert TorrentSource.from_file(b"d4:info" + info + b"e").info_hash == hashlib.sha1(info).hexdigest()
def test_source_frozen():
    s = TorrentSource.from_magnet("magnet:?xt=urn:btih:aabb")
    with pytest.raises((AttributeError, TypeError)): s.magnet = "x"  # type: ignore[misc]
def test_limits_all_none(): lim = TorrentLimits(); assert lim.ratio is None and lim.up_bytes_per_s is None
def test_limits_partial(): lim = TorrentLimits(ratio=2.0); assert lim.ratio == 2.0 and lim.seed_time_minutes is None
def test_limits_frozen():
    with pytest.raises((AttributeError, TypeError)): TorrentLimits(ratio=1.0).ratio = 2.0  # type: ignore[misc]
```

- [ ] **2. Run — confirm ImportError**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_source.py -q 2>&1 | tail -5
```

- [ ] **3. Implement** — append to `_base.py` after `TorrentItem`.

Add imports at top: `import hashlib`, `import re`, `from functools import cached_property`. Replace `from dataclasses import dataclass` with `from dataclasses import dataclass, field`.

```python
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
```

- [ ] **4. Run tests — expect all pass**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_source.py -v 2>&1 | tail -15
```

- [ ] **5. Lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint 2>&1 | tail -5
```

Expected: 0 errors.

- [ ] **6. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/api/torrent/_base.py tests/unit/test_torrent_source.py && git commit -m "feat(torrent-write): add TorrentSource and TorrentLimits value objects"
```
