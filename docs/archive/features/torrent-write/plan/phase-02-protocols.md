# Phase 02 — `TorrentAdder`, `TorrentLimiter` Protocols + `UnsupportedCapabilityError`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Add two new `@runtime_checkable` Protocols to `_contracts.py` and `UnsupportedCapabilityError` to `_errors.py`. 1 commit.

**Tech Stack:** Python 3.11, `typing.Protocol`, `runtime_checkable`, pytest

---

## Gate

- `TorrentSource`, `TorrentLimits` importable from `personalscraper.api.torrent._base`.
- `make lint` passes.

---

## Files

- Modify: `personalscraper/api/torrent/_contracts.py`
- Modify: `personalscraper/api/torrent/_errors.py`
- Create: `tests/unit/test_torrent_write_contracts.py`

---

## Steps

- [ ] **1. Write failing tests** in `tests/unit/test_torrent_write_contracts.py`:

```python
"""Tests for TorrentAdder / TorrentLimiter Protocols and UnsupportedCapabilityError."""
from __future__ import annotations
import personalscraper.api.torrent._contracts as cm
import personalscraper.api.torrent._errors as em

def test_adder_in_all(): assert "TorrentAdder" in cm.__all__
def test_limiter_in_all(): assert "TorrentLimiter" in cm.__all__
def test_adder_runtime_checkable():
    from personalscraper.api.torrent._contracts import TorrentAdder
    from typing import runtime_checkable, Protocol
    assert issubclass(TorrentAdder, Protocol)  # type: ignore[arg-type]
def test_limiter_runtime_checkable():
    from personalscraper.api.torrent._contracts import TorrentLimiter
    from typing import Protocol
    assert issubclass(TorrentLimiter, Protocol)  # type: ignore[arg-type]
def test_unsupported_error_importable():
    from personalscraper.api.torrent._errors import UnsupportedCapabilityError
    assert issubclass(UnsupportedCapabilityError, Exception)
def test_unsupported_error_in_all(): assert "UnsupportedCapabilityError" in em.__all__
def test_adder_has_add_method():
    from personalscraper.api.torrent._contracts import TorrentAdder
    import inspect
    assert "add" in {m for m in dir(TorrentAdder) if not m.startswith("_") or m == "add"}
def test_limiter_has_apply_limits_method():
    from personalscraper.api.torrent._contracts import TorrentLimiter
    assert hasattr(TorrentLimiter, "apply_limits")
```

- [ ] **2. Run — confirm ImportError**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_write_contracts.py -q 2>&1 | tail -5
```

- [ ] **3. Add Protocols to `_contracts.py`**

Add at the top of `_contracts.py` (after existing imports):

```python
from collections.abc import Sequence
from personalscraper.api.torrent._base import TorrentLimits, TorrentSource
```

Note: `TorrentItem` is already imported. Append before `__all__`:

```python
@runtime_checkable
class TorrentAdder(Protocol):
    """Capability — add a torrent to the client (D1/§5.2).

    Composed by QBitClient and TransmissionClient. Returns info_hash (D6).
    Duplicate adds are idempotent (D7). Passing limits to a client without
    TorrentLimiter must raise UnsupportedCapabilityError (D8).
    """

    def add(
        self,
        source: TorrentSource,
        *,
        category: str | None = None,
        tags: Sequence[str] = (),
        paused: bool = False,
        limits: TorrentLimits | None = None,
    ) -> str:
        """Add a torrent from a source.

        Args:
            source: Discriminated value object — magnet or file bytes.
            category: Category label.
            tags: Tag strings.
            paused: Add in paused state if True.
            limits: Transfer limits; raise UnsupportedCapabilityError if
                client lacks TorrentLimiter and limits is not None (D8).

        Returns:
            info_hash string of the added torrent.
        """
        ...


@runtime_checkable
class TorrentLimiter(Protocol):
    """Capability — apply transfer limits to an existing torrent (D2/§5.2).

    Composed by QBitClient only. Callers gate via
    isinstance(client, TorrentLimiter) before calling apply_limits.
    """

    def apply_limits(self, info_hash: str, limits: TorrentLimits) -> None:
        """Apply transfer limits to the torrent.

        Args:
            info_hash: Lowercase hex info_hash of the target torrent.
            limits: Limits to apply; None fields are no-ops.
        """
        ...
```

Update `__all__` to add `"TorrentAdder"` and `"TorrentLimiter"` (keep alphabetical order).

- [ ] **4. Add `UnsupportedCapabilityError` to `_errors.py`**

Add before `TORRENT_CONNECT_ERRORS`:

```python
class UnsupportedCapabilityError(Exception):
    """Raised when a capability unsupported by the client is requested (D8).

    Raised by TransmissionClient.add() when limits is not None — Transmission
    has no ratio/bandwidth/seedtime limit fields. Gate via
    isinstance(client, TorrentLimiter) before passing limits.
    """
```

Add `"UnsupportedCapabilityError"` to `__all__`.

- [ ] **5. Run tests — expect all pass**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_torrent_write_contracts.py -v 2>&1 | tail -15
```

- [ ] **6. Run existing torrent tests for regressions**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_qbittorrent.py tests/unit/test_torrent_capabilities_composition.py tests/unit/test_torrent_factory.py -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **7. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/api/torrent/_contracts.py personalscraper/api/torrent/_errors.py tests/unit/test_torrent_write_contracts.py && git commit -m "feat(torrent-write): add TorrentAdder, TorrentLimiter Protocols and UnsupportedCapabilityError"
```
