# Phase 3a — Factory unit tests: error cases

## Gate

**Requires Phase 2:**

```bash
python -c "from personalscraper.api.tracker._factory import build_tracker_registry; print('ok')"
# Expected: ok
```

---

## Goal

Write the first half of `tests/unit/test_tracker_factory.py`, covering the
three error codes (`missing_credentials`, `unknown_provider`,
`protocol_mismatch`) plus the all-disabled silent-boot case. Every test is
non-vacuous: it either asserts the registry contents or asserts
`TrackerConfigError` is raised with the expected `code`.

---

## Files

- **Create:** `tests/unit/test_tracker_factory.py`

---

## Tasks

### Task 3a.1 — Write error-case tests

- [ ] **Create** `tests/unit/test_tracker_factory.py`:

```python
"""Unit tests for build_tracker_registry — tracker-wiring RP5a.

All I/O mocked (HttpTransport patched). Part A: error cases and silent boot.
Part B (phase-03b): warning case, severity split, happy path.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.api.tracker._contracts import TorrentSearchable
from personalscraper.api.tracker._errors import TrackerConfigError
from personalscraper.api.tracker._factory import build_tracker_registry
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.tracker._registry import TrackerRegistry
from personalscraper.api.transport._policy import CircuitPolicy
from personalscraper.conf.models.api_config import TrackerConfig, TrackerProviderConfig
from personalscraper.core.event_bus import EventBus


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _ranking() -> RankingConfig:
    return RankingConfig()


def _policy() -> CircuitPolicy:
    return CircuitPolicy(failure_threshold=5, cooldown_seconds=1.0)


def _settings() -> MagicMock:
    return MagicMock()


def _cfg(providers: dict[str, bool], priority: list[str] | None = None) -> TrackerConfig:
    return TrackerConfig(
        providers={k: TrackerProviderConfig(enabled=v) for k, v in providers.items()},
        priority=priority if priority is not None else list(providers),
    )


def _env(*names: str) -> dict[str, str]:
    return {n: f"fake_{n}" for n in names}


# ---------------------------------------------------------------------------
# Stub clients
# ---------------------------------------------------------------------------

class _StubSearchable:
    provider_name: str = "stub"

    @classmethod
    def policy(cls, api_key: str) -> MagicMock:  # type: ignore[return]
        return MagicMock()

    def __init__(self, transport: Any) -> None:
        self._transport = transport

    def search(self, query: str, media_type: Any = None,
               year: int | None = None) -> list:
        return []


class _NotSearchable:
    """Stub client that does NOT implement TorrentSearchable."""

    provider_name: str = "bad"

    @classmethod
    def policy(cls, api_key: str) -> MagicMock:  # type: ignore[return]
        return MagicMock()

    def __init__(self, transport: Any) -> None:
        self._transport = transport


# ---------------------------------------------------------------------------
# Error: missing_credentials
# ---------------------------------------------------------------------------

class TestMissingCredentials:
    def test_enabled_tracker_no_key_raises(self) -> None:
        cfg = _cfg({"lacale": True}, priority=["lacale"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(), env={},
            )

        codes = [i.code for i in exc_info.value.issues]
        assert "missing_credentials" in codes

    def test_error_names_the_provider(self) -> None:
        cfg = _cfg({"lacale": True}, priority=["lacale"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(), env={},
            )

        providers = [i.provider for i in exc_info.value.issues]
        assert "lacale" in providers

    def test_error_names_the_missing_key(self) -> None:
        cfg = _cfg({"c411": True}, priority=["c411"])

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(), env={},
            )

        assert any("C411_API_KEY" in i.message for i in exc_info.value.issues)


# ---------------------------------------------------------------------------
# Error: unknown_provider (name in priority absent from providers)
# ---------------------------------------------------------------------------

class TestUnknownProvider:
    def test_ghost_in_priority_raises(self) -> None:
        cfg = TrackerConfig(
            providers={"lacale": TrackerProviderConfig(enabled=False)},
            priority=["lacale", "ghost"],
        )

        with pytest.raises(TrackerConfigError) as exc_info:
            build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(), env={},
            )

        codes = [i.code for i in exc_info.value.issues]
        assert "unknown_provider" in codes
        providers = [i.provider for i in exc_info.value.issues]
        assert "ghost" in providers


# ---------------------------------------------------------------------------
# Error: protocol_mismatch
# ---------------------------------------------------------------------------

class TestProtocolMismatch:
    def test_non_searchable_client_raises(self) -> None:
        cfg = _cfg({"lacale": True}, priority=["lacale"])

        with patch("personalscraper.api.tracker._factory._TRACKER_CLASSES",
                   {"lacale": "tests.unit.test_tracker_factory:_NotSearchable"}), \
             patch("personalscraper.api.tracker._factory.HttpTransport"):
            with pytest.raises(TrackerConfigError) as exc_info:
                build_tracker_registry(
                    cfg, _ranking(), settings=_settings(),
                    event_bus=EventBus(), cb_policy=_policy(),
                    env=_env("LACALE_API_KEY"),
                )

        codes = [i.code for i in exc_info.value.issues]
        assert "protocol_mismatch" in codes


# ---------------------------------------------------------------------------
# All-disabled: silent boot, empty registry
# ---------------------------------------------------------------------------

class TestAllDisabled:
    def test_all_disabled_returns_empty_registry(self) -> None:
        cfg = _cfg({"lacale": False, "c411": False}, priority=[])

        registry = build_tracker_registry(
            cfg, _ranking(), settings=_settings(),
            event_bus=EventBus(), cb_policy=_policy(), env={},
        )

        assert isinstance(registry, TrackerRegistry)
        assert registry._trackers == {}

    def test_all_disabled_no_warning_emitted(self, caplog: pytest.LogCaptureFixture) -> None:
        """disabled_in_priority must NOT be emitted when zero trackers are active."""
        cfg = TrackerConfig(
            providers={
                "lacale": TrackerProviderConfig(enabled=False),
                "c411": TrackerProviderConfig(enabled=False),
            },
            priority=["lacale", "c411"],
        )

        with caplog.at_level("WARNING"):
            registry = build_tracker_registry(
                cfg, _ranking(), settings=_settings(),
                event_bus=EventBus(), cb_policy=_policy(), env={},
            )

        assert registry._trackers == {}
        assert "disabled_in_priority" not in caplog.text
```

- [ ] **Run:**
  ```bash
  python -m pytest tests/unit/test_tracker_factory.py -v
  # Expected: all tests in this file pass, 0 failed
  ```

---

### Task 3a.2 — Commit

```bash
git add tests/unit/test_tracker_factory.py
git commit -m "test(tracker-wiring): factory unit tests — error cases + silent boot"
```

---

## Gate exit checklist

- [ ] `pytest tests/unit/test_tracker_factory.py` → all passed, 0 failed
- [ ] Commit SHA recorded
