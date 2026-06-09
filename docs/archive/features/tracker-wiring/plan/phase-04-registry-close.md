# Phase 4 — `TrackerRegistry.close()` + regression guard

## Gate

**Requires Phase 3:**

```bash
python -m pytest tests/unit/test_tracker_factory.py -q
# Expected: all passed, 0 failed
```

---

## Goal

Add `TrackerRegistry.close()` to `personalscraper/api/tracker/_registry.py`.
It iterates `self._trackers`, calls `transport.close()` on each client's
`_transport` attribute (if present and callable), swallows per-provider
exceptions with a debug log (parity with `ProviderRegistry.close()`), and
is a no-op on an empty registry.

The existing `__init__` signature is **not changed** — the 4 pre-existing
dict-ctor tests must remain green.

---

## Files

- **Modify:** `personalscraper/api/tracker/_registry.py`
- **Create:** `tests/unit/test_tracker_registry_close.py`

---

## Tasks

### Task 4.1 — Add `close()` to `TrackerRegistry`

Open `personalscraper/api/tracker/_registry.py`. After the `search_all` method,
append the following method inside the `TrackerRegistry` class (same indentation
level as `search_all`):

```python
    def close(self) -> None:
        """Release the HttpTransport owned by each tracker client.

        Iterates ``self._trackers`` and calls ``close()`` on each client's
        ``_transport`` attribute when present, mirroring
        ``ProviderRegistry.close()``. Per-client exceptions are caught,
        logged at DEBUG level, and do not propagate — a failing close on one
        tracker must not prevent the others from releasing their sessions.

        An empty registry (no active trackers) closes cleanly as a no-op.
        """
        for name, client in list(self._trackers.items()):
            transport = getattr(client, "_transport", None)
            if transport is None:
                continue
            close_fn = getattr(transport, "close", None)
            if not callable(close_fn):
                continue
            try:
                close_fn()
            except Exception as exc:  # noqa: BLE001
                log.debug(
                    "tracker_transport_close_failed",
                    tracker=name,
                    exc_type=type(exc).__name__,
                )
```

- [ ] Apply the edit above.
- [ ] Verify the method is importable:
  ```bash
  python -c "
  from personalscraper.api.tracker._registry import TrackerRegistry
  from personalscraper.api.tracker._ranking import RankingConfig
  r = TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())
  r.close()
  print('ok')
  "
  # Expected: ok
  ```

---

### Task 4.2 — Write unit tests

- [ ] **Create** `tests/unit/test_tracker_registry_close.py`:

```python
"""Unit tests for TrackerRegistry.close() — tracker-wiring RP5a.

Verifies:
- Empty registry closes as a no-op (no exception).
- close() calls _transport.close() on each client.
- A client with no _transport attribute is skipped gracefully.
- A _transport.close() that raises is swallowed (does not propagate).
- All transports are attempted even when one raises.
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry


def _make_registry(trackers: dict) -> TrackerRegistry:
    return TrackerRegistry(
        trackers=trackers,
        priority=list(trackers),
        ranking=RankingConfig(),
    )


def _stub_client(name: str) -> MagicMock:
    """Return a mock client whose _transport.close() is trackable."""
    client = MagicMock()
    client._transport = MagicMock()
    client._transport.close = MagicMock()
    return client


class TestTrackerRegistryClose:
    def test_empty_registry_closes_cleanly(self) -> None:
        """No trackers → close() is a no-op, no exception raised."""
        registry = _make_registry({})
        registry.close()  # must not raise

    def test_close_calls_transport_close_on_each_client(self) -> None:
        """close() must call _transport.close() for every client in the registry."""
        lacale = _stub_client("lacale")
        c411 = _stub_client("c411")
        registry = _make_registry({"lacale": lacale, "c411": c411})
        registry.close()
        lacale._transport.close.assert_called_once()
        c411._transport.close.assert_called_once()

    def test_client_without_transport_is_skipped(self) -> None:
        """A client with no _transport attribute must not raise."""
        client = MagicMock(spec=[])  # no attributes — getattr returns None
        del client._transport  # ensure absent
        registry = _make_registry({"ghost": client})
        registry.close()  # must not raise

    def test_transport_close_exception_is_swallowed(self) -> None:
        """If _transport.close() raises, the exception must not propagate."""
        client = _stub_client("lacale")
        client._transport.close.side_effect = RuntimeError("session already closed")
        registry = _make_registry({"lacale": client})
        registry.close()  # must not raise

    def test_all_transports_closed_even_when_one_raises(self) -> None:
        """A failing close on client A must not prevent client B from being closed."""
        lacale = _stub_client("lacale")
        lacale._transport.close.side_effect = RuntimeError("boom")
        c411 = _stub_client("c411")
        registry = _make_registry({"lacale": lacale, "c411": c411})
        registry.close()
        # c411 must still have been closed despite lacale raising:
        c411._transport.close.assert_called_once()

    def test_existing_dict_ctor_still_works(self) -> None:
        """Regression guard: __init__ signature unchanged — no keyword-only drift."""
        from unittest.mock import MagicMock as MM
        stub = MM()
        stub.search = MM(return_value=[])
        r = TrackerRegistry(
            trackers={"lacale": stub},
            priority=["lacale"],
            ranking=RankingConfig(),
            priority_by_media_type={"movie": ["lacale"]},
        )
        assert r._priority == ["lacale"]
```

- [ ] **Run:**
  ```bash
  python -m pytest tests/unit/test_tracker_registry_close.py -v
  # Expected: 6 passed, 0 failed
  ```

---

### Task 4.3 — Confirm all pre-existing registry tests still pass

- [ ] **Run:**
  ```bash
  python -m pytest tests/unit/test_tracker_registry_priority_by_media_type.py \
                   tests/unit/test_tracker_registry_except_scope.py \
                   tests/unit/test_tracker_capabilities_composition.py -v
  # Expected: all pass — __init__ signature unchanged
  ```

---

### Task 4.4 — Commit

```bash
git add personalscraper/api/tracker/_registry.py \
        tests/unit/test_tracker_registry_close.py
git commit -m "feat(tracker-wiring): TrackerRegistry.close() + regression guard"
```

---

## Gate exit checklist

- [ ] `pytest tests/unit/test_tracker_registry_close.py` → 6 passed, 0 failed
- [ ] Pre-existing registry tests all pass (regression guard)
- [ ] `python -c "import personalscraper"` → exit 0
- [ ] Commit SHA recorded
