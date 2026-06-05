# Phase 07 — `AppContext.torrent_client` Field

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** Add `torrent_client: QBitClient | TransmissionClient | None = None` to `AppContext`. Default `None` ensures read-only commands (info, library queries) that don't configure a torrent client keep working (D9). 1 commit.

**Tech Stack:** Python 3.11, `dataclasses`, pytest

---

## Gate

- Both clients compose `TorrentAdder`; `QBitClient` also composes `TorrentLimiter`.
- `make check` passes.

---

## Files

- Modify: `personalscraper/core/app_context.py`
- Create: `tests/unit/test_app_context_torrent.py`

---

## Steps

- [ ] **1. Check current `AppContext` fields**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "torrent_client" personalscraper/core/app_context.py
```

Expected: no match (field does not exist yet).

- [ ] **2. Write failing test** in `tests/unit/test_app_context_torrent.py`:

```python
"""Tests for AppContext.torrent_client field (DESIGN D3/D9)."""
from __future__ import annotations
import dataclasses
from unittest.mock import MagicMock
from personalscraper.core.app_context import AppContext

def test_torrent_client_field_exists() -> None:
    """AppContext declares a torrent_client field."""
    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "torrent_client" in fields

def test_torrent_client_defaults_none() -> None:
    """torrent_client defaults to None — read-only commands must not break (D9)."""
    ctx = AppContext(
        config=MagicMock(), settings=MagicMock(),
        event_bus=MagicMock(), provider_registry=MagicMock(),
        torrent_client=None,
    )
    assert ctx.torrent_client is None

def test_torrent_client_can_be_set() -> None:
    """torrent_client accepts a concrete client object."""
    mock_client = MagicMock()
    ctx = AppContext(
        config=MagicMock(), settings=MagicMock(),
        event_bus=MagicMock(), provider_registry=MagicMock(),
        torrent_client=mock_client,
    )
    assert ctx.torrent_client is mock_client
```

- [ ] **3. Run — confirm TypeError**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_app_context_torrent.py -q 2>&1 | tail -5
```

Expected: `TypeError: __init__() got unexpected keyword argument 'torrent_client'`.

- [ ] **4. Update `AppContext` in `core/app_context.py`**

Add to `TYPE_CHECKING` block:

```python
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
```

Add field to `AppContext` dataclass after `provider_registry`:

```python
    torrent_client: "QBitClient | TransmissionClient | None" = None
```

Add to the class docstring `Attributes:` section:

```
        torrent_client: Active torrent client, or ``None`` when no torrent
            client is configured (DESIGN D3/D9). Boundary modules read this
            field to pass the client to pipeline steps without re-building it.
```

- [ ] **5. Run tests — expect all pass**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_app_context_torrent.py -v 2>&1 | tail -10
```

- [ ] **6. Run full suite to check no regressions** (AppContext is frozen; existing code that constructs it without `torrent_client` will still work because the field has a default)

```bash
cd /Users/izno/dev/PersonnalScaper && make test 2>&1 | tail -10
```

Expected: all pass; 0 collection ERRORs.

- [ ] **7. Check architecture boundary test** still passes (it asserts which modules can receive AppContext):

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/architecture/ -q 2>&1 | tail -8
```

Expected: all pass.

- [ ] **8. Lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint 2>&1 | tail -5
```

- [ ] **9. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/core/app_context.py tests/unit/test_app_context_torrent.py && git commit -m "feat(torrent-write): add torrent_client field to AppContext (D3/D9)"
```
