# Phase 01 — acquire/ package skeleton, AcquireStore Protocol, AcquireContext + close() tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `acquire/` package with the `AcquireStore` Protocol, the `AcquireContext` frozen dataclass, and mutation-proven unit tests for `close()`.

**Architecture:** `personalscraper/acquire/` is a new peer package. It imports only downward (`api/`, `core/`, `events/`). No behaviour — pure structure and lifecycle.

**Tech Stack:** Python 3.12, dataclasses, typing.Protocol, pytest, unittest.mock

---

## Gate (Phase 0 → Phase 01)

Phase 0 is the repo as-is on `feat/acquire-lobe`. Verify before starting:

```bash
python -c "import personalscraper"          # must exit 0
make check                                   # must be green (all tests pass)
```

---

## Sub-phase 1.1: Create `acquire/` package with `_ports.py`

**Files:**

- Create: `personalscraper/acquire/__init__.py`
- Create: `personalscraper/acquire/_ports.py`
- Create: `tests/acquire/__init__.py`

- [ ] **Step 1: Write the failing import test**

```python
# tests/acquire/test_context.py  (create file)
"""Unit tests for AcquireContext — acquire-lobe RP5c."""
from __future__ import annotations

def test_acquire_store_protocol_importable() -> None:
    from personalscraper.acquire._ports import AcquireStore
    assert hasattr(AcquireStore, "close")
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
pytest tests/acquire/test_context.py::test_acquire_store_protocol_importable -v
```

Expected: `ModuleNotFoundError` — package does not exist yet.

- [ ] **Step 3: Create `personalscraper/acquire/__init__.py`**

```python
"""Acquisition lobe — home of the RP5b orchestrator (future) and the RP5c injection handle.

This package is a peer of ``ingest``, ``sort``, ``dispatch``, and ``indexer``.
At RP5c it contains only the injection context (``AcquireContext``) and the
``AcquireStore`` Protocol seam.  No behaviour is implemented here yet.

Import direction: ``acquire/`` may import downward only (``api/``, ``core/``,
``conf/``, ``events/``). It must never import the triage packages (``ingest``,
``sort``, ``sorter``, ``process``, ``scraper``, ``dispatch``, ``indexer``,
``enforce``, ``verify``, ``insights``, ``maintenance``, ``reports``,
``trailers``, ``pipeline``, ``pipeline_steps``, ``commands``).
"""

from personalscraper.acquire.context import AcquireContext

__all__ = ["AcquireContext"]
```

- [ ] **Step 4: Create `personalscraper/acquire/_ports.py`**

```python
"""Port protocols for the acquire lobe — RP5c structural seam.

Only the lifecycle contract is defined here.  RP3 will extend
``AcquireStore`` with query/write methods when the database is wired.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AcquireStore(Protocol):
    """Minimal store contract — lifecycle only.

    RP3 supplies the concrete implementation and fills the
    ``AcquireContext.store`` slot.  The only obligation RP5c needs
    is ``close()`` so the context's lifecycle can propagate it.
    """

    def close(self) -> None:
        """Release all resources held by the store (connections, threads, …)."""
        ...


__all__ = ["AcquireStore"]
```

- [ ] **Step 5: Create `tests/acquire/__init__.py`**

Empty file — makes the directory a package so pytest discovers it.

```python

```

- [ ] **Step 6: Run the import test — expect PASS**

```bash
pytest tests/acquire/test_context.py::test_acquire_store_protocol_importable -v
```

Expected: `PASSED` (the package is importable now).

Note: the `__init__.py` imports `AcquireContext` which does not exist yet — the test will fail at collection if `context.py` is missing. Create a stub `context.py` (next task) to unblock.

- [ ] **Step 7: Stub `context.py` to unblock collection**

```python
# personalscraper/acquire/context.py  (stub, expanded in Task 2)
"""AcquireContext — stub (expanded in Task 2)."""
```

- [ ] **Step 8: Commit**

```bash
git add personalscraper/acquire/__init__.py \
        personalscraper/acquire/_ports.py \
        personalscraper/acquire/context.py \
        tests/acquire/__init__.py \
        tests/acquire/test_context.py
git commit -m "feat(acquire-lobe): add acquire/ package skeleton and AcquireStore Protocol"
```

---

## Sub-phase 1.2: Implement `AcquireContext` frozen dataclass

**Files:**

- Modify: `personalscraper/acquire/context.py`
- Modify: `tests/acquire/test_context.py`

- [ ] **Step 1: Add failing tests for AcquireContext structure**

Append to `tests/acquire/test_context.py`:

```python
import dataclasses
from unittest.mock import MagicMock, call


def test_acquire_context_is_frozen_dataclass() -> None:
    """AcquireContext is a frozen dataclass — mutating a field must raise."""
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.api.tracker._ranking import RankingConfig

    registry = TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())
    ctx = AcquireContext(tracker_registry=registry)
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.tracker_registry = registry  # type: ignore[misc]


def test_acquire_context_fields() -> None:
    """AcquireContext has tracker_registry, store, torrent_client fields."""
    from personalscraper.acquire.context import AcquireContext

    fields = {f.name for f in dataclasses.fields(AcquireContext)}
    assert fields == {"tracker_registry", "store", "torrent_client"}


def test_acquire_context_store_and_torrent_client_default_none() -> None:
    """store and torrent_client default to None."""
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.api.tracker._ranking import RankingConfig

    registry = TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())
    ctx = AcquireContext(tracker_registry=registry)
    assert ctx.store is None
    assert ctx.torrent_client is None
```

Add `import pytest` and `import dataclasses` at the top of the test file.

- [ ] **Step 2: Run failing tests**

```bash
pytest tests/acquire/test_context.py -v
```

Expected: collection error or `AttributeError` — `AcquireContext` not yet defined.

- [ ] **Step 3: Implement `AcquireContext` in `context.py`**

```python
"""AcquireContext — frozen injection handle for the acquisition lobe (RP5c).

Mirrors the ``AppContext`` pattern: a frozen dataclass constructed once at
the composition root and carrying the owned/borrowed service handles needed
by the acquisition lobe.

Import direction: this module imports only from ``personalscraper.api`` and
``personalscraper.acquire._ports`` — never from triage packages.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient


@dataclass(frozen=True)
class AcquireContext:
    """Frozen injection handle for the acquisition lobe.

    Constructed once per process at the composition root (inside
    ``_build_app_context``) and stored as ``AppContext.acquire``.

    Ownership semantics:
    - ``tracker_registry``: OWNED — RP5a port, migrated from ``AppContext``.
      ``close()`` will call ``tracker_registry.close()``.
    - ``store``: OWNED (when present) — filled by RP3; ``close()`` propagates.
    - ``torrent_client``: BORROWED — shared with ``ingest``; its lifecycle is
      managed by the ``ingest`` boundary, NOT here. ``close()`` must NOT call
      ``torrent_client.close()``.

    Attributes:
        tracker_registry: Configured ``TrackerRegistry`` (always present at
            boot; may be empty when all trackers are disabled).
        store: ``AcquireStore`` implementation or ``None``.  Slot filled by
            RP3 when the acquisition DB is wired.
        torrent_client: Active torrent client or ``None``.  Borrowed from
            the shared port — ``close()`` does not own its lifecycle.
    """

    tracker_registry: "TrackerRegistry"
    store: "AcquireStore | None" = None
    torrent_client: "QBitClient | TransmissionClient | None" = None

    def close(self) -> None:
        """Close OWNED resources: tracker_registry and store (when present).

        Does NOT close ``torrent_client`` — that handle is shared with the
        ``ingest`` boundary which owns its lifecycle.

        Raises:
            Nothing — resource-release errors must not propagate to the
            caller.  Individual close() failures should be handled at the
            resource level (e.g. TrackerRegistry.close() is already fail-soft).
        """
        self.tracker_registry.close()
        if self.store is not None:
            self.store.close()


__all__ = ["AcquireContext"]
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/acquire/test_context.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/context.py tests/acquire/test_context.py
git commit -m "feat(acquire-lobe): implement AcquireContext frozen dataclass"
```

---

## Sub-phase 1.3: Mutation-proven close() non-ownership guard tests

**Files:**

- Modify: `tests/acquire/test_context.py`

- [ ] **Step 1: Add the close() behaviour tests**

Append to `tests/acquire/test_context.py`:

```python
class TestAcquireContextClose:
    """AcquireContext.close() owns tracker_registry + store; borrows torrent_client."""

    def _make_ctx(
        self,
        *,
        store: object = None,
        torrent_client: object = None,
    ):
        """Build an AcquireContext with a mock TrackerRegistry."""
        from personalscraper.acquire.context import AcquireContext

        registry = MagicMock()
        return AcquireContext(
            tracker_registry=registry,
            store=store,
            torrent_client=torrent_client,
        )

    def test_close_calls_tracker_registry_close(self) -> None:
        """close() must call tracker_registry.close() exactly once."""
        ctx = self._make_ctx()
        ctx.close()
        ctx.tracker_registry.close.assert_called_once()

    def test_close_calls_store_close_when_present(self) -> None:
        """close() must call store.close() when store is not None."""
        store = MagicMock()
        ctx = self._make_ctx(store=store)
        ctx.close()
        store.close.assert_called_once()

    def test_close_skips_store_when_none(self) -> None:
        """close() must not raise and must not call store.close() when store is None."""
        ctx = self._make_ctx(store=None)
        ctx.close()  # no error

    def test_close_does_not_call_torrent_client_close(self) -> None:
        """NON-OWNERSHIP GUARD: close() must NEVER call torrent_client.close().

        This test is mutation-proven: if ``close()`` is modified to call
        ``self.torrent_client.close()``, ``assert_not_called()`` will fail
        (RED), catching the ownership violation immediately.
        """
        torrent_client = MagicMock()
        ctx = self._make_ctx(torrent_client=torrent_client)
        ctx.close()
        torrent_client.close.assert_not_called()

    def test_close_does_not_call_torrent_client_close_even_with_store(self) -> None:
        """Non-ownership guard holds when both store and torrent_client are set."""
        store = MagicMock()
        torrent_client = MagicMock()
        ctx = self._make_ctx(store=store, torrent_client=torrent_client)
        ctx.close()
        torrent_client.close.assert_not_called()
        store.close.assert_called_once()
```

- [ ] **Step 2: Run tests — expect all PASS**

```bash
pytest tests/acquire/test_context.py -v
```

Expected: all tests pass (including the 5 new close() tests).

- [ ] **Step 3: Commit**

```bash
git add tests/acquire/test_context.py
git commit -m "test(acquire-lobe): add mutation-proven close() non-ownership guard"
```

---

## Phase 01 Exit Criteria

```bash
pytest tests/acquire/ -v   # all tests pass
python -c "from personalscraper.acquire.context import AcquireContext; print('OK')"
python -c "from personalscraper.acquire._ports import AcquireStore; print('OK')"
make lint                  # zero errors
```
