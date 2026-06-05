# Phase 08 — Fail-Fast in `_build_app_context()`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** When a torrent client is configured and enabled, `_build_app_context()` calls `build_active_torrent_client()`, asserts it composes `TorrentAdder`, and raises `RegistryConfigError` if not (D3). No client configured → `torrent_client=None`, no error (D9). 1 commit.

**Tech Stack:** `personalscraper.cli_helpers`, `personalscraper.api.metadata.registry.RegistryConfigError`, pytest

---

## Gate

- `AppContext.torrent_client` field present with `None` default.
- Architecture boundary tests pass.
- `make check` passes.

---

## Files

- Modify: `personalscraper/cli_helpers/__init__.py`
- Create: `tests/unit/test_build_app_context_torrent.py`

---

## Steps

- [ ] **1. Find `RegistryConfigError`**

```bash
cd /Users/izno/dev/PersonnalScaper && rg -t py "class RegistryConfigError" personalscraper/ 2>&1 | head -5
```

Note the import path for the next step.

- [ ] **2. Write failing tests** in `tests/unit/test_build_app_context_torrent.py`:

```python
"""Tests for torrent fail-fast in _build_app_context() (D3/D9)."""
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest

def _cfg(active="", enabled=True):
    cfg = MagicMock()
    cfg.torrent.active = active
    cfg.torrent.clients = {active: MagicMock(enabled=enabled)} if active else {}
    cfg.thresholds.circuit_breaker_threshold = 5
    cfg.thresholds.circuit_breaker_cooldown = 60.0
    cfg.providers = {}
    return cfg

_PATCHES = [
    "personalscraper.cli_helpers.ProviderRegistry",
    "personalscraper.cli_helpers.CircuitPolicy",
]

class TestBuildAppContextTorrent:
    def test_no_active_torrent_client_gives_none(self):
        from personalscraper.cli_helpers import _build_app_context
        with patch(_PATCHES[0]) as R, patch(_PATCHES[1]):
            R.return_value = MagicMock()
            ctx = _build_app_context(_cfg(active=""), MagicMock())
        assert ctx.torrent_client is None

    def test_capable_client_wired(self):
        from personalscraper.cli_helpers import _build_app_context
        from personalscraper.api.torrent._contracts import TorrentAdder
        mock_client = MagicMock(spec=TorrentAdder)
        with (patch(_PATCHES[0]) as R, patch(_PATCHES[1]),
              patch("personalscraper.cli_helpers.build_active_torrent_client",
                    return_value=mock_client)):
            R.return_value = MagicMock()
            ctx = _build_app_context(_cfg(active="qbittorrent"), MagicMock())
        assert ctx.torrent_client is mock_client

    def test_incapable_client_raises(self):
        from personalscraper.cli_helpers import _build_app_context
        from personalscraper.api.metadata.registry import RegistryConfigError
        mock_client = MagicMock(spec=[])  # satisfies nothing
        with (patch(_PATCHES[0]) as R, patch(_PATCHES[1]),
              patch("personalscraper.cli_helpers.build_active_torrent_client",
                    return_value=mock_client)):
            R.return_value = MagicMock()
            with pytest.raises(RegistryConfigError, match="TorrentAdder"):
                _build_app_context(_cfg(active="qbittorrent"), MagicMock())
```

- [ ] **3. Run — confirm test_capable_client_wired and test_incapable_client_raises fail**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_build_app_context_torrent.py -q 2>&1 | tail -8
```

- [ ] **4. Update `_build_app_context()` in `cli_helpers/__init__.py`**

Add `import os` at module level if not already present (check: `grep -n "^import os" personalscraper/cli_helpers/__init__.py`).

Add to the lazy imports block inside `_build_app_context()`:

```python
    import os  # noqa: PLC0415 (already at module level — remove this if so)
    from personalscraper.api.metadata.registry import RegistryConfigError  # noqa: PLC0415
    from personalscraper.api.torrent._contracts import TorrentAdder  # noqa: PLC0415
    from personalscraper.api.torrent._factory import build_active_torrent_client  # noqa: PLC0415
```

After the `provider_registry = ProviderRegistry(...)` line, add:

```python
    # D3/D9: Boot-wire the torrent client when configured; fail-fast if incapable.
    # No client configured (torrent.active="") → torrent_client=None, no error.
    torrent_client = None
    if config.torrent.active:
        raw_client = build_active_torrent_client(config.torrent, os.environ)
        if not isinstance(raw_client, TorrentAdder):
            raise RegistryConfigError(
                f"Active torrent client {config.torrent.active!r} does not compose "
                "TorrentAdder. Verify the client implementation or configuration."
            )
        torrent_client = raw_client
```

Update the `return AppContext(...)` call to include `torrent_client=torrent_client`.

Also expose `build_active_torrent_client` as a module-level name for testability by adding to the top-level imports in `cli_helpers/__init__.py`:

```python
from personalscraper.api.torrent._factory import build_active_torrent_client as build_active_torrent_client  # noqa: PLC0415
```

(This lets the test patch `personalscraper.cli_helpers.build_active_torrent_client` cleanly. If `_build_app_context` already imports it lazily inside the function, patch the lazy import path instead: `personalscraper.api.torrent._factory.build_active_torrent_client`.)

- [ ] **5. Run tests — expect all pass**

```bash
cd /Users/izno/dev/PersonnalScaper && pytest tests/unit/test_build_app_context_torrent.py -v 2>&1 | tail -15
```

- [ ] **6. Run full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && make test 2>&1 | tail -10
```

Expected: all pass; 0 ERRORs.

- [ ] **7. Lint**

```bash
cd /Users/izno/dev/PersonnalScaper && make lint 2>&1 | tail -5
```

- [ ] **8. Commit**

```bash
cd /Users/izno/dev/PersonnalScaper && git add personalscraper/cli_helpers/__init__.py tests/unit/test_build_app_context_torrent.py && git commit -m "feat(torrent-write): add torrent capability fail-fast in _build_app_context() (D3/D9)"
```
