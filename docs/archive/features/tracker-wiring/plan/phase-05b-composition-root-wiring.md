# Phase 5b — Composition-root wiring + integration tests

## Gate

**Requires Phase 5a:**

```bash
python -c "
from unittest.mock import MagicMock
from personalscraper.core.app_context import AppContext
ctx = AppContext(config=MagicMock(), settings=MagicMock(),
                 event_bus=MagicMock(), provider_registry=MagicMock())
assert ctx.tracker_registry is None
print('ok')
"
# Expected: ok
```

---

## Goal

Wire `build_tracker_registry()` into `_build_app_context` (lazy import, after
`provider_registry` is constructed) and call `tracker_registry.close()` in
`per_step_boundary`'s `finally`. Then add integration tests proving the wiring
is live end-to-end.

---

## Files

- **Modify:** `personalscraper/cli_helpers/__init__.py`
- **Create:** `tests/integration/api/tracker/__init__.py`
- **Create:** `tests/integration/api/tracker/test_composition_root.py`

---

## Tasks

### Task 5b.1 — Wire into `_build_app_context`

Open `personalscraper/cli_helpers/__init__.py`.

Inside `_build_app_context`, after the block that conditionally builds
`torrent_client` (the block ending with `torrent_client = raw_client`),
add the following tracker-wiring block **before** the `return AppContext(...)`
call:

```python
    # RP5a: build tracker registry at boot (lazy import mirrors the
    # provider_registry pattern — keeps --help / init-config network-light).
    # TrackerConfigError surfaces here on any misconfig: fail-loud at the same
    # boundary as RegistryConfigError (metadata/torrent).
    from personalscraper.api.tracker._factory import build_tracker_registry  # noqa: PLC0415

    tracker_registry = build_tracker_registry(
        config.tracker,
        config.ranking,
        settings=settings,
        event_bus=event_bus,
        cb_policy=cb_policy,
    )
```

Then update the `return AppContext(...)` call to pass the new field:

```python
    return AppContext(
        config=config,
        settings=settings,
        event_bus=event_bus,
        provider_registry=provider_registry,
        torrent_client=torrent_client,
        tracker_registry=tracker_registry,
    )
```

Also extend the `_build_app_context` docstring to mention tracker wiring.
After the paragraph about the torrent client, add:

```
    The :class:`TrackerRegistry` is built unconditionally for every command
    that goes through the single composition root (DESIGN §Components.4).
    The default config (all trackers disabled) produces an empty registry
    and boots silently. A misconfigured tracker raises
    :class:`~personalscraper.api.tracker._errors.TrackerConfigError` at this
    boundary — fail-loud, parity with ``RegistryConfigError``.
```

- [ ] Apply both edits to `personalscraper/cli_helpers/__init__.py`.

---

### Task 5b.2 — Release in `per_step_boundary`

In the same file, locate `per_step_boundary`'s `finally` block:

```python
    finally:
        current_correlation_id.reset(token)
        app_context.provider_registry.close()
```

Add tracker close **after** `provider_registry.close()`:

```python
        if app_context.tracker_registry is not None:
            app_context.tracker_registry.close()
```

- [ ] Apply the edit.

- [ ] **Verify smoke boot:**

  ```bash
  python -c "import personalscraper; print('ok')"
  # Expected: ok
  ```

- [ ] **Commit sub-phase 5b wiring:**
  ```bash
  git add personalscraper/cli_helpers/__init__.py
  git commit -m "feat(tracker-wiring): wire tracker_registry into composition root"
  ```

---

### Task 5b.3 — Integration tests

- [ ] Create the integration test package:

  ```bash
  mkdir -p tests/integration/api/tracker
  touch tests/integration/api/tracker/__init__.py
  ```

- [ ] **Create** `tests/integration/api/tracker/test_composition_root.py`:

```python
"""Integration tests for tracker-registry composition-root wiring.

Verifies _build_app_context() populates tracker_registry, that
TrackerConfigError surfaces at boot, and that per_step_boundary calls close().
Network is not touched: build_tracker_registry is patched throughout.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.tracker._errors import TrackerConfigError, TrackerConfigIssue
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.cli_helpers import _build_app_context, per_step_boundary
from personalscraper.core.app_context import AppContext


def _config() -> MagicMock:
    cfg = MagicMock()
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 300.0
    cfg.torrent.active = ""
    return cfg


def _settings() -> MagicMock:
    return MagicMock()


def _empty_registry() -> TrackerRegistry:
    return TrackerRegistry(trackers={}, priority=[], ranking=RankingConfig())


class TestBuildAppContextTrackerWiring:
    def test_tracker_registry_set_from_factory(self) -> None:
        """_build_app_context must store the factory's return value."""
        stub = _empty_registry()

        with patch("personalscraper.api.tracker._factory.build_tracker_registry",
                   return_value=stub), \
             patch("personalscraper.api.metadata.registry.ProviderRegistry"):
            ctx = _build_app_context(_config(), _settings())

        assert ctx.tracker_registry is stub

    def test_tracker_config_error_surfaces_at_boot(self) -> None:
        """TrackerConfigError from the factory must propagate out of _build_app_context."""
        issue = TrackerConfigIssue(
            severity="error", code="missing_credentials",
            provider="lacale", message="LACALE_API_KEY absent",
        )

        with patch("personalscraper.api.tracker._factory.build_tracker_registry",
                   side_effect=TrackerConfigError([issue])), \
             patch("personalscraper.api.metadata.registry.ProviderRegistry"):
            with pytest.raises(TrackerConfigError) as exc_info:
                _build_app_context(_config(), _settings())

        assert exc_info.value.issues[0].code == "missing_credentials"

    def test_app_context_direct_construction_defaults_to_none(self) -> None:
        """Direct AppContext construction (test fixtures) still defaults to None."""
        ctx = AppContext(
            config=MagicMock(), settings=MagicMock(),
            event_bus=MagicMock(), provider_registry=MagicMock(),
        )
        assert ctx.tracker_registry is None


class TestPerStepBoundaryClose:
    def test_close_called_on_normal_exit(self) -> None:
        """per_step_boundary must call tracker_registry.close() on normal exit."""
        stub_registry = MagicMock(spec=TrackerRegistry)

        with patch("personalscraper.cli_helpers._build_app_context") as mock_build, \
             patch("personalscraper.cli_helpers.current_correlation_id"):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.tracker_registry = stub_registry
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass

        stub_registry.close.assert_called_once()

    def test_close_called_when_body_raises(self) -> None:
        """per_step_boundary must call close() even when the body raises."""
        stub_registry = MagicMock(spec=TrackerRegistry)

        with patch("personalscraper.cli_helpers._build_app_context") as mock_build, \
             patch("personalscraper.cli_helpers.current_correlation_id"):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.tracker_registry = stub_registry
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with pytest.raises(RuntimeError):
                with per_step_boundary(_config(), _settings()):
                    raise RuntimeError("body error")

        stub_registry.close.assert_called_once()

    def test_none_tracker_registry_does_not_raise(self) -> None:
        """per_step_boundary must not crash when tracker_registry is None."""
        with patch("personalscraper.cli_helpers._build_app_context") as mock_build, \
             patch("personalscraper.cli_helpers.current_correlation_id"):
            mock_ctx = MagicMock(spec=AppContext)
            mock_ctx.tracker_registry = None
            mock_ctx.provider_registry = MagicMock()
            mock_build.return_value = mock_ctx

            with per_step_boundary(_config(), _settings()):
                pass  # must not raise
```

- [ ] **Run integration tests:**

  ```bash
  python -m pytest tests/integration/api/tracker/test_composition_root.py -v
  # Expected: all passed, 0 failed
  ```

- [ ] **Run full suite:**

  ```bash
  make check
  # Expected: exits 0
  ```

- [ ] **Commit sub-phase 5b tests:**
  ```bash
  git add tests/integration/api/tracker/__init__.py \
          tests/integration/api/tracker/test_composition_root.py
  git commit -m "test(tracker-wiring): composition-root integration tests"
  ```

---

## Gate exit checklist

- [ ] `pytest tests/integration/api/tracker/test_composition_root.py` → all passed
- [ ] `python -c "import personalscraper"` → exit 0
- [ ] `make check` → exits 0
- [ ] Two commits recorded (wiring, integration tests)
