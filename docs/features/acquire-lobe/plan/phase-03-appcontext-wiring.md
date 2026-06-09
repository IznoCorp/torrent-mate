# Phase 03 — AppContext swap + cli_helpers wiring + wiring tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Swap `AppContext.tracker_registry` → `AppContext.acquire`; update `cli_helpers/__init__.py` to call `build_acquire_context` and close via `app_context.acquire.close()`; adapt existing wiring tests.

**Architecture:** One-field swap in `AppContext` (drop `tracker_registry`, add `acquire: AcquireContext`). The only current consumer is `cli_helpers/__init__.py` — blast radius is one module + its tests.

**Tech Stack:** Python 3.12, dataclasses, pytest, unittest.mock

---

## Gate (Phase 02 → Phase 03)

Phase 02 must have produced:

- `personalscraper/acquire/_factory.py` — `build_acquire_context` implemented
- `tests/acquire/test_factory.py` — all tests passing

Verify:

```bash
pytest tests/acquire/ -v     # all pass
python -c "from personalscraper.acquire._factory import build_acquire_context; print('OK')"
```

---

## Task 1: Swap `AppContext` fields

**Files:**

- Modify: `personalscraper/core/app_context.py`

- [ ] **Step 1: Write the failing field-check test**

Add a new file `tests/acquire/test_appcontext_swap.py`:

```python
"""Verify AppContext.acquire replaces tracker_registry — acquire-lobe RP5c."""

from __future__ import annotations

import dataclasses


def test_appcontext_has_acquire_field() -> None:
    """AppContext must have an 'acquire' field after the RP5c swap."""
    from personalscraper.core.app_context import AppContext

    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "acquire" in fields, "'acquire' field missing from AppContext"


def test_appcontext_no_tracker_registry_field() -> None:
    """AppContext must NOT have a 'tracker_registry' field after the RP5c swap."""
    from personalscraper.core.app_context import AppContext

    fields = {f.name for f in dataclasses.fields(AppContext)}
    assert "tracker_registry" not in fields, (
        "'tracker_registry' still present — should have been folded into AcquireContext"
    )
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
pytest tests/acquire/test_appcontext_swap.py -v
```

Expected: `AssertionError` — `acquire` not yet present, `tracker_registry` still there.

- [ ] **Step 3: Edit `personalscraper/core/app_context.py`**

Replace the existing `AppContext` dataclass with the version below.
Key changes:

- Drop `tracker_registry` field and its `TYPE_CHECKING` import
- Add `acquire: AcquireContext` field (non-optional)
- Add `TYPE_CHECKING` import for `AcquireContext`

```python
"""Process-scoped service bundle.

``AppContext`` is the long-lived service container constructed once per
process at the system boundary (CLI entry, launchd scan entry, future Web UI
or Watcher boot). It carries the services that EVERY pipeline run,
indexer scan, or trailer-CLI invocation needs: ``config`` (the typed JSON5
configuration), ``settings`` (Pydantic env-var settings), ``event_bus``
(the in-process :class:`EventBus`), and ``acquire`` (the acquisition lobe's
injection handle introduced in RP5c).

**Boundary-only rule** (DESIGN.md §Architecture, codified by the AST test
at ``tests/architecture/test_app_context_boundary.py``): internal
components MUST NOT receive AppContext "for convenience". Inject the
specific services they need (a ``Config``, a single ``MetadataClient``,
etc.) — never the whole bundle. The allowlist of authorized boundary
modules lives in the same test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Imported under TYPE_CHECKING to avoid circular imports.
    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus


@dataclass(frozen=True)
class AppContext:
    """Long-lived process-scoped service bundle.

    Constructed exactly once per process at the system boundary. Frozen
    because the bundle's identity is part of every event's correlation
    context — swapping a service mid-process would break invariants that
    later phases (subscribers, AST boundary test) rely on.

    Attributes:
        config: The typed JSON5 configuration loaded at boundary.
        settings: The Pydantic env-var settings (API keys, paths).
        event_bus: The in-process ``EventBus`` for cross-component events.
        provider_registry: The configured :class:`ProviderRegistry`
            instantiated at boot. Bundles every metadata provider
            (TMDB, TVDB, OMDB, …) with circuit policy + event-bus
            instrumentation.
        torrent_client: Active torrent client, or ``None`` when no torrent
            client is configured. Shared with the acquisition lobe
            (borrowed by ``AcquireContext``).
        acquire: Acquisition lobe injection handle (RP5c). Owns the
            ``TrackerRegistry`` (migrated from RP5a) and the optional
            ``AcquireStore`` slot (filled by RP3). Always built at boot;
            sub-deps may be ``None`` (``store``, ``torrent_client``).
    """

    config: "Config"
    settings: "Settings"
    event_bus: "EventBus"
    provider_registry: "ProviderRegistry"
    torrent_client: "QBitClient | TransmissionClient | None" = None
    acquire: "AcquireContext | None" = None  # non-optional in production; None only in legacy tests


__all__ = ["AppContext"]
```

> **Note:** `acquire` is typed `AcquireContext | None` with `None` default so that the existing `_stub_app()` helpers in the test suite (which pass no `acquire` kwarg) do not break. The production composition root always sets it. Tests that verify wiring correctness (Task 3) must assert `acquire is not None`.

- [ ] **Step 4: Run swap tests — expect PASS**

```bash
pytest tests/acquire/test_appcontext_swap.py -v
```

Expected: both tests pass.

- [ ] **Step 5: Run full test suite to catch any breakage**

```bash
make test
```

Expected: all existing tests pass (the `None` default absorbs old stubs).

- [ ] **Step 6: Commit**

```bash
git add personalscraper/core/app_context.py tests/acquire/test_appcontext_swap.py
git commit -m "feat(acquire-lobe): swap AppContext — drop tracker_registry, add acquire field"
```

---

## Task 2: Wire `cli_helpers/__init__.py`

**Files:**

- Modify: `personalscraper/cli_helpers/__init__.py`

- [ ] **Step 1: Replace the `build_tracker_registry` block in `_build_app_context`**

In `_build_app_context`, replace this block (lines ~132–153):

```python
    # RP5a: build tracker registry at boot …
    from personalscraper.api.tracker._factory import build_tracker_registry  # noqa: PLC0415

    tracker_registry = build_tracker_registry(
        config.tracker,
        config.ranking,
        settings=settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
    )

    return AppContext(
        config=config,
        settings=settings,
        event_bus=event_bus,
        provider_registry=provider_registry,
        torrent_client=torrent_client,
        tracker_registry=tracker_registry,
    )
```

With:

```python
    # RP5c: build the acquisition lobe handle at boot. Delegates tracker
    # registry construction to build_tracker_registry (RP5a unchanged).
    # TrackerConfigError surfaces here on any misconfig — fail-loud at the
    # same boundary as RegistryConfigError.
    from personalscraper.acquire._factory import build_acquire_context  # noqa: PLC0415

    acquire = build_acquire_context(
        config,
        settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
        torrent_client=torrent_client,
    )

    return AppContext(
        config=config,
        settings=settings,
        event_bus=event_bus,
        provider_registry=provider_registry,
        torrent_client=torrent_client,
        acquire=acquire,
    )
```

- [ ] **Step 2: Replace the `per_step_boundary` close path**

In `per_step_boundary`, replace:

```python
        app_context.provider_registry.close()
        if app_context.tracker_registry is not None:
            app_context.tracker_registry.close()
```

With:

```python
        app_context.provider_registry.close()
        if app_context.acquire is not None:
            app_context.acquire.close()
```

- [ ] **Step 3: Update the `_build_app_context` docstring**

Replace the paragraph beginning `"The :class:`TrackerRegistry`..."` with:

```
    The :class:`AcquireContext` (RP5c) is built unconditionally for every
    command that goes through the single composition root. It owns the
    :class:`TrackerRegistry` (migrated from RP5a) and the optional
    ``AcquireStore`` slot (RP3). A misconfigured tracker raises
    :class:`~personalscraper.api.tracker._errors.TrackerConfigError` at this
    boundary — fail-loud, parity with ``RegistryConfigError``.
```

- [ ] **Step 4: Run lint and tests**

```bash
make lint
pytest tests/cli_helpers/ -v
```

Expected: lint clean, cli_helpers tests pass.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/cli_helpers/__init__.py
git commit -m "feat(acquire-lobe): wire cli_helpers to build_acquire_context, close via acquire.close()"
```

---

## Task 3: Adapt wiring tests

**Files:**

- Modify: `tests/test_pipeline_app_context.py`
- Modify: `tests/acquire/test_appcontext_swap.py`

- [ ] **Step 1: Update `_stub_app()` to include `acquire`**

In `tests/test_pipeline_app_context.py`, update `_stub_app()`:

```python
def _stub_app() -> AppContext:
    """Build an :class:`AppContext` whose config/settings are MagicMocks.

    Suitable for tests that never reach disk I/O. The :class:`EventBus`
    is a real instance so subscribe/emit machinery behaves correctly.
    """
    from unittest.mock import MagicMock

    from personalscraper.acquire.context import AcquireContext
    from personalscraper.api.metadata.registry import ProviderRegistry
    from personalscraper.core.app_context import AppContext
    from personalscraper.core.event_bus import EventBus

    config = MagicMock()
    config.disks = []
    config.paths.staging_dir = MagicMock()
    ingest_entry = MagicMock()
    ingest_entry.id = 97
    ingest_entry.role = "ingest"
    config.staging_dirs = [ingest_entry]
    config.paths.data_dir = MagicMock()
    settings = MagicMock()
    acquire = AcquireContext(tracker_registry=MagicMock())
    return AppContext(
        config=config,
        settings=settings,
        event_bus=EventBus(),
        provider_registry=MagicMock(spec=ProviderRegistry),
        acquire=acquire,
    )
```

- [ ] **Step 2: Add a wiring close-propagation test**

Add to `tests/acquire/test_appcontext_swap.py`:

```python
def test_per_step_boundary_calls_acquire_close(tmp_path: "Path") -> None:
    """per_step_boundary must call app_context.acquire.close() on exit."""
    from unittest.mock import MagicMock, patch

    from personalscraper.cli_helpers import per_step_boundary

    fake_acquire = MagicMock()
    fake_acquire.close = MagicMock()

    fake_ctx = MagicMock()
    fake_ctx.acquire = fake_acquire
    fake_ctx.provider_registry = MagicMock()

    with patch("personalscraper.cli_helpers._build_app_context", return_value=fake_ctx):
        with per_step_boundary(MagicMock(), MagicMock()):
            pass

    fake_acquire.close.assert_called_once()
```

- [ ] **Step 3: Run full test suite**

```bash
make test
```

Expected: all tests pass (existing pipeline tests + new wiring tests).

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline_app_context.py tests/acquire/test_appcontext_swap.py
git commit -m "test(acquire-lobe): adapt wiring tests for acquire field and close propagation"
```

---

## Phase 03 Exit Criteria

```bash
make test                                   # all pass
python -c "
import dataclasses
from personalscraper.core.app_context import AppContext
f = {x.name for x in dataclasses.fields(AppContext)}
assert 'acquire' in f and 'tracker_registry' not in f
print('swap OK')
"
make lint                                   # zero errors
```
