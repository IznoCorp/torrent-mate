# Phase 02 — `build_acquire_context` factory + tests

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `build_acquire_context()` in `acquire/_factory.py` and cover it with unit tests that exercise delegation to `build_tracker_registry`, `store=None` default, `torrent_client` propagation, and `TrackerConfigError` surfacing.

**Architecture:** The factory mirrors `build_tracker_registry` — thin, config-driven, no new validation. It delegates tracker construction entirely to the existing RP5a factory.

**Tech Stack:** Python 3.12, unittest.mock, pytest

---

## Gate (Phase 01 → Phase 02)

Phase 01 must have produced:

- `personalscraper/acquire/__init__.py` — importable
- `personalscraper/acquire/_ports.py` — `AcquireStore` Protocol
- `personalscraper/acquire/context.py` — `AcquireContext` frozen dataclass with `close()`
- `tests/acquire/test_context.py` — all close() tests passing

Verify:

```bash
pytest tests/acquire/ -v    # all pass
python -c "from personalscraper.acquire.context import AcquireContext; print('OK')"
```

---

## Sub-phase 2.1: Write failing factory tests

**Files:**

- Create: `tests/acquire/test_factory.py`

- [ ] **Step 1: Create the failing test file**

```python
"""Unit tests for build_acquire_context — acquire-lobe RP5c."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestBuildAcquireContext:
    """build_acquire_context() wires tracker_registry, leaves store=None, propagates torrent_client."""

    def _minimal_config(self) -> MagicMock:
        """Return a MagicMock config with the attributes build_acquire_context reads."""
        config = MagicMock()
        # build_tracker_registry reads config.tracker, config.ranking
        return config

    def test_store_is_none_by_default(self) -> None:
        """build_acquire_context sets store=None — RP3 fills it later."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch(
            "personalscraper.acquire._factory.build_tracker_registry"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(
                config, settings, event_bus=event_bus, cb_policy=cb_policy
            )

        assert ctx.store is None

    def test_torrent_client_none_when_not_passed(self) -> None:
        """torrent_client defaults to None when not supplied."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch(
            "personalscraper.acquire._factory.build_tracker_registry"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(
                config, settings, event_bus=event_bus, cb_policy=cb_policy
            )

        assert ctx.torrent_client is None

    def test_torrent_client_propagated_when_passed(self) -> None:
        """torrent_client is stored on the context when explicitly passed."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()
        fake_client = MagicMock()

        with patch(
            "personalscraper.acquire._factory.build_tracker_registry"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            ctx = build_acquire_context(
                config,
                settings,
                event_bus=event_bus,
                cb_policy=cb_policy,
                torrent_client=fake_client,
            )

        assert ctx.torrent_client is fake_client

    def test_delegates_to_build_tracker_registry(self) -> None:
        """build_acquire_context calls build_tracker_registry with config.tracker, config.ranking."""
        from personalscraper.acquire._factory import build_acquire_context

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        with patch(
            "personalscraper.acquire._factory.build_tracker_registry"
        ) as mock_build:
            fake_registry = MagicMock()
            mock_build.return_value = fake_registry
            ctx = build_acquire_context(
                config, settings, event_bus=event_bus, cb_policy=cb_policy
            )

        mock_build.assert_called_once_with(
            config.tracker,
            config.ranking,
            settings=settings,
            event_bus=event_bus,
            cb_policy=cb_policy,
        )
        assert ctx.tracker_registry is fake_registry

    def test_tracker_config_error_surfaces(self) -> None:
        """TrackerConfigError from build_tracker_registry propagates unchanged."""
        from personalscraper.acquire._factory import build_acquire_context
        from personalscraper.api.tracker._errors import TrackerConfigError, TrackerConfigIssue

        config = self._minimal_config()
        settings = MagicMock()
        event_bus = MagicMock()
        cb_policy = MagicMock()

        issue = TrackerConfigIssue(
            severity="error",
            code="missing_credentials",
            provider="lacale",
            message="no key",
        )
        with patch(
            "personalscraper.acquire._factory.build_tracker_registry",
            side_effect=TrackerConfigError([issue]),
        ):
            with pytest.raises(TrackerConfigError):
                build_acquire_context(
                    config, settings, event_bus=event_bus, cb_policy=cb_policy
                )
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/acquire/test_factory.py -v
```

Expected: `ModuleNotFoundError` — `acquire/_factory.py` does not exist yet.

---

## Sub-phase 2.2: Implement `build_acquire_context`

**Files:**

- Create: `personalscraper/acquire/_factory.py`

- [ ] **Step 1: Write the factory**

```python
"""Config-driven factory for AcquireContext — acquire-lobe RP5c.

Mirrors ``api/tracker/_factory.py``: thin assembler at the composition-root
boundary. Delegates tracker construction entirely to the unchanged
``build_tracker_registry`` from RP5a. Adds no new validation — boot
validation remains RP5a's; ``TrackerConfigError`` still surfaces at the same
boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from personalscraper.acquire.context import AcquireContext
from personalscraper.api.tracker._factory import build_tracker_registry

if TYPE_CHECKING:
    from personalscraper.api.torrent.qbittorrent import QBitClient
    from personalscraper.api.torrent.transmission import TransmissionClient
    from personalscraper.api.transport._policy import CircuitPolicy
    from personalscraper.conf.models.config import Config
    from personalscraper.config import Settings
    from personalscraper.core.event_bus import EventBus


def build_acquire_context(
    config: "Config",
    settings: "Settings",
    *,
    event_bus: "EventBus",
    cb_policy: "CircuitPolicy",
    torrent_client: "QBitClient | TransmissionClient | None" = None,
) -> AcquireContext:
    """Build the AcquireContext at the composition-root boundary.

    Delegates tracker registry construction to the unchanged
    :func:`~personalscraper.api.tracker._factory.build_tracker_registry`
    (RP5a). Sets ``store=None`` — RP3 fills the slot when the acquisition
    DB is wired. Borrows ``torrent_client`` from the caller; does NOT build
    or validate it (that is the torrent-client boundary's responsibility).

    ``TrackerConfigError`` raised by ``build_tracker_registry`` propagates
    unchanged — fail-loud at the same boundary as ``RegistryConfigError``.

    Args:
        config: Typed JSON5 configuration loaded at the boundary.
        settings: Pydantic env-var settings (API keys, paths).
        event_bus: In-process event bus forwarded to the tracker registry.
        cb_policy: Circuit-breaker policy forwarded to the tracker registry.
        torrent_client: Already-built torrent client, or ``None``.
            Lifecycle is NOT owned by ``AcquireContext`` — it is shared with
            the ``ingest`` boundary.

    Returns:
        A populated :class:`AcquireContext` with ``tracker_registry`` set,
        ``store=None``, and ``torrent_client`` forwarded.

    Raises:
        TrackerConfigError: Any error-severity issue found in the tracker
            config (surfaced by ``build_tracker_registry``).
    """
    tracker_registry = build_tracker_registry(
        config.tracker,
        config.ranking,
        settings=settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
    )
    return AcquireContext(
        tracker_registry=tracker_registry,
        store=None,
        torrent_client=torrent_client,
    )


__all__ = ["build_acquire_context"]
```

- [ ] **Step 2: Run factory tests — expect all PASS**

```bash
pytest tests/acquire/test_factory.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 3: Run full acquire test suite**

```bash
pytest tests/acquire/ -v
```

Expected: all tests pass (context + factory).

- [ ] **Step 4: Commit**

```bash
git add personalscraper/acquire/_factory.py tests/acquire/test_factory.py
git commit -m "feat(acquire-lobe): add build_acquire_context factory + unit tests"
```

---

## Phase 02 Exit Criteria

```bash
pytest tests/acquire/ -v                     # all pass
python -c "from personalscraper.acquire._factory import build_acquire_context; print('OK')"
make lint                                    # zero errors
```
