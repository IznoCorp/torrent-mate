# Phase 06 — `TransmissionClient.add()` + `_labels()` Helper

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Implement `TransmissionClient.add()` (TorrentAdder) and `_labels()` helper (D5). Transmission composes TorrentAdder but NOT TorrentLimiter; passing limits raises UnsupportedCapabilityError (D8). 1 commit.

**Tech Stack:** `transmission_rpc`, `unittest.mock`, pytest

---

## Gate

- `QBitClient.add()` + `apply_limits()` present and tested.
- `make check` passes.

---

## Files

- Modify: `personalscraper/api/torrent/transmission.py`
- Create: `tests/unit/test_transmission_add.py`
- Modify: `tests/unit/test_torrent_capabilities_composition.py`

---

## Steps

- [ ] **1. Write failing tests** in `tests/unit/test_transmission_add.py`:

```python
"""Tests for TransmissionClient.add() — DESIGN D1/D5/D7/D8."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest, transmission_rpc
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentLimiter
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
from personalscraper.api.torrent.transmission import TransmissionClient, _labels

MAGNET = "magnet:?xt=urn:btih:aabbcc112233ddeeff00112233445566778899aa&dn=t"

def _c():
    with patch("transmission_rpc.Client"):
        c = TransmissionClient("localhost", 9091, "u", "p")
    c._client = MagicMock()
    return c

def _mock_torrent(hash_string="aabbcc112233ddeeff00112233445566778899aa"):
    t = MagicMock(); t.hash_string = hash_string; return t

class TestTransmissionAdd:
    def test_is_torrent_adder(self): assert isinstance(_c(), TorrentAdder)
    def test_not_torrent_limiter(self): assert not isinstance(_c(), TorrentLimiter)

    def test_magnet_calls_add_torrent(self):
        c = _c(); c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET), category="movies", tags=["action"])
        kw = c._client.add_torrent.call_args[1]
        assert kw["torrent"] == MAGNET and kw["labels"] == ["movies", "action"]

    def test_file_bytes_passed_as_torrent(self):
        c = _c(); c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_file(b"bytes"))
        assert c._client.add_torrent.call_args[1]["torrent"] == b"bytes"

    def test_paused_forwarded(self):
        c = _c(); c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET), paused=True)
        assert c._client.add_torrent.call_args[1].get("paused") is True

    def test_returns_info_hash(self):
        c = _c(); c._client.add_torrent.return_value = _mock_torrent()
        src = TorrentSource.from_magnet(MAGNET)
        assert c.add(src) == src.info_hash

    def test_duplicate_idempotent(self):
        c = _c()
        c._client.add_torrent.side_effect = transmission_rpc.TransmissionError("torrent-duplicate")
        src = TorrentSource.from_magnet(MAGNET)
        assert c.add(src) == src.info_hash  # D7: no exception

    def test_limits_raises_unsupported(self):
        c = _c()
        with pytest.raises(UnsupportedCapabilityError, match="limit"):
            c.add(TorrentSource.from_magnet(MAGNET), limits=TorrentLimits(ratio=1.0))

    def test_no_category_no_tags_empty_labels(self):
        c = _c(); c._client.add_torrent.return_value = _mock_torrent()
        c.add(TorrentSource.from_magnet(MAGNET))
        assert c._client.add_torrent.call_args[1]["labels"] == []

class TestLabelsHelper:
    def test_category_first(self): assert _labels("movies", ["action"]) == ["movies", "action"]
    def test_no_category(self): assert _labels(None, ["action"]) == ["action"]
    def test_both_none(self): assert _labels(None, []) == []
    def test_dedup_category_in_tags(self):
        r = _labels("movies", ["movies", "action"])
        assert r.count("movies") == 1 and r[0] == "movies"
```

- [ ] **2. Run — confirm ImportError/AttributeError**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_transmission_add.py -q 2>&1 | tail -5
```

- [ ] **3. Add imports to `transmission.py`**

```python
from collections.abc import Sequence
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
from personalscraper.api.torrent._contracts import TorrentAdder, TorrentController, TorrentInspector, TorrentLister, TorrentStateInspector
from personalscraper.api.torrent._errors import UnsupportedCapabilityError
```

Update class declaration:

```python
class TransmissionClient(TorrentLister, TorrentInspector, TorrentStateInspector, TorrentController, TorrentAdder):
```

Update class docstring to include `TorrentAdder` in capabilities list.

- [ ] **4. Add `add()` method** in the mutations section:

```python
    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent to Transmission (D1/D5/D7/D8).

        Labels encode category + tags per D5. Duplicate adds are idempotent
        (torrent-duplicate → return info_hash, no exception). Passing limits
        raises UnsupportedCapabilityError (D8 — no silent ignore).

        Args:
            source: TorrentSource — magnet or file bytes.
            category: Category (becomes labels[0]).
            tags: Tags (appended after category in labels).
            paused: Add in paused state if True.
            limits: Must be None; raises if set (D8).

        Returns:
            info_hash of the added (or already-present) torrent.

        Raises:
            UnsupportedCapabilityError: limits is not None.
        """
        if limits is not None:
            raise UnsupportedCapabilityError(
                "TransmissionClient does not support transfer limits. "
                "Gate via isinstance(client, TorrentLimiter) before passing limits."
            )
        torrent_arg = source.magnet if source.magnet is not None else source.file_bytes
        try:
            result = self._client.add_torrent(
                torrent=torrent_arg, labels=_labels(category, list(tags)), paused=paused)
            log.debug("transmission_add_ok", echoed_hash=result.hash_string,
                      source_hash=source.info_hash)
            return source.info_hash
        except transmission_rpc.TransmissionError as exc:
            if "duplicate" in str(exc).lower():  # D7 idempotence
                log.debug("transmission_add_duplicate", info_hash=source.info_hash)
                return source.info_hash
            raise
```

- [ ] **5. Add `_labels()` helper** at the bottom of `transmission.py`:

```python
def _labels(category: str | None, tags: list[str]) -> list[str]:
    """Build Transmission labels list from category and tags (D5).

    Round-trip: write labels=[category, *tags]; read category=labels[0],
    tags=labels[1:]. Category is deduped if it also appears in tags.

    Args:
        category: Category string or None.
        tags: Tag strings.

    Returns:
        Ordered list [category, *deduped_tags].
    """
    result: list[str] = []
    if category is not None:
        result.append(category)
    for tag in tags:
        if tag not in result:
            result.append(tag)
    return result
```

- [ ] **6. Add composition assertions** to `tests/unit/test_torrent_capabilities_composition.py`:

```python
def test_transmission_client_is_torrent_adder() -> None:
    """TransmissionClient satisfies TorrentAdder."""
    assert isinstance(_transmission(), TorrentAdder)

def test_transmission_client_not_torrent_limiter() -> None:
    """TransmissionClient does NOT satisfy TorrentLimiter (D2)."""
    assert not isinstance(_transmission(), TorrentLimiter)
```

(Import `TorrentAdder, TorrentLimiter` at top of that file if not already present.)

- [ ] **7. Run all tests**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_transmission_add.py tests/unit/test_torrent_capabilities_composition.py -q 2>&1 | tail -8
```

Expected: all pass.

- [ ] **8. Full quality gate**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -10
```

Expected: exits 0.

- [ ] **9. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/api/torrent/transmission.py tests/unit/test_transmission_add.py tests/unit/test_torrent_capabilities_composition.py && git commit -m "feat(torrent-write): implement TransmissionClient.add() with D5 labels and D8 limit guard"
```
