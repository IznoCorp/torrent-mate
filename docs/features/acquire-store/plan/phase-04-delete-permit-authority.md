# Phase 04 — core/delete_permit + acquire/delete_authority

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce the neutral `DeletePermit` / `SeedObligationRecorder` Protocols in `core/`,
add the `AllowAllPermit` fail-open no-op, and implement `acquire/delete_authority.py` which
resolves deletion candidates against persisted `seed_obligation.dispatched_path` with a
path-exists guard. Fail-open on every error path.

**Architecture:** `core/delete_permit.py` imports only stdlib/typing (mirror `core/_contracts.py`).
The concrete `DeleteAuthority` in `acquire/` imports `core/` and `acquire/store.py` — never
`indexer/`, `dispatch/`, or `maintenance/`. Deletion-time lookup joins on the persisted
`dispatched_path` column; `content_path` from the torrent client is NOT used (DESIGN §7.2).

**Tech stack:** `core.sqlite`, `acquire.store.ConcreteAcquireStore`, `personalscraper.logger.get_logger`.

---

## Gate (from Phase 3)

- `personalscraper/acquire/store.py` exists; `build_acquire_store` importable.
- `personalscraper/acquire/migrations/001_init.sql` present; `user_version=1` after migration.
- `AcquireContext.store` is set (not `None`) in `build_acquire_context`.
- `make check` green.

---

## File map

| Action | Path                                          |
| ------ | --------------------------------------------- |
| Create | `personalscraper/core/delete_permit.py`       |
| Create | `personalscraper/acquire/delete_authority.py` |
| Create | `tests/acquire/test_delete_authority.py`      |

---

### Task 1 — Create `core/delete_permit.py`

**Files:**

- Create: `personalscraper/core/delete_permit.py`
- Test: `tests/core/test_delete_permit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_delete_permit.py
"""Tests for core.delete_permit: Protocols + AllowAllPermit."""
from __future__ import annotations

from pathlib import Path
from personalscraper.core.delete_permit import (
    ALLOW,
    AllowAllPermit,
    DeletePermit,
    PermitDecision,
    SeedObligationRecorder,
)


def test_allow_all_permit_returns_allow(tmp_path: Path) -> None:
    permit = AllowAllPermit()
    decision = permit.may_delete(tmp_path / "somefile.mkv")
    assert decision is ALLOW


def test_allow_all_permit_implements_protocol() -> None:
    permit = AllowAllPermit()
    assert isinstance(permit, DeletePermit)


def test_permit_decision_allow_is_singleton() -> None:
    assert ALLOW is ALLOW


def test_veto_carries_reason() -> None:
    from personalscraper.core.delete_permit import veto
    decision = veto("seeding: lacale min_seed_time not met")
    assert decision is not ALLOW
    assert "lacale" in str(decision)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/core/test_delete_permit.py -v 2>&1 | tail -15
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `personalscraper/core/delete_permit.py`**

```python
# personalscraper/core/delete_permit.py
"""Neutral deletion-authority port types (RP3).

Import direction: stdlib + typing only (mirror core/_contracts.py).
Never imported by acquire/ implementation modules at the top level —
inject via the composition root.

The deleters (maintenance/disk_cleaner, dispatch/) depend ONLY on these
core port types. The concrete acquire/ implementation is injected at the
composition root. This ensures deleters never import acquire/.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class _Allow:
    """Singleton sentinel meaning the deletion is permitted."""

    def __repr__(self) -> str:
        return "ALLOW"


@dataclass(frozen=True)
class _Veto:
    """A deletion veto with a human-readable reason."""

    reason: str

    def __repr__(self) -> str:
        return f"VETO({self.reason!r})"

    def __str__(self) -> str:
        return f"VETO: {self.reason}"


#: Singleton ALLOW sentinel returned by permit implementations.
ALLOW: _Allow = _Allow()

PermitDecision = _Allow | _Veto


def veto(reason: str) -> _Veto:
    """Construct a VETO decision with the given reason string.

    Args:
        reason: Human-readable explanation for the veto.

    Returns:
        A _Veto instance carrying the reason.
    """
    return _Veto(reason=reason)


@runtime_checkable
class DeletePermit(Protocol):
    """Protocol for deletion-authority implementations.

    A ``DeletePermit`` is consulted before any media deletion.
    Implementations MUST be fail-open: any lookup error → ALLOW.
    VETO is only returned on a positively-known unmet seed obligation.
    """

    def may_delete(self, path: Path) -> PermitDecision:
        """Return ALLOW or a VETO for the given path.

        Args:
            path: The filesystem path about to be deleted.

        Returns:
            ``ALLOW`` if deletion is permitted, ``veto(reason)`` if it is not.
        """
        ...


@runtime_checkable
class SeedObligationRecorder(Protocol):
    """Protocol for recording a seed obligation at dispatch time.

    Implementations MUST be fail-soft: any write error is swallowed and
    logged; the caller is never interrupted by an obligation-write failure.
    """

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
        """Correlate staging_source to a live seeding torrent and record the obligation.

        Called BEFORE the FS move (write-before-move guarantee).

        Args:
            staging_source: Absolute path of the file in the staging area.
            dispatched_dest: Absolute path of the destination after dispatch.
        """
        ...


class AllowAllPermit:
    """Fail-open no-op DeletePermit — always returns ALLOW.

    Used as the default for tests, for dispatch/maintenance when no store
    is present, and as the fallback when the store is unreadable.
    Also implements SeedObligationRecorder as a no-op.
    """

    def may_delete(self, path: Path) -> PermitDecision:
        """Always permit the deletion.

        Args:
            path: Ignored.

        Returns:
            Always ``ALLOW``.
        """
        return ALLOW

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
        """No-op recorder — does nothing.

        Args:
            staging_source: Ignored.
            dispatched_dest: Ignored.
        """


__all__ = [
    "ALLOW",
    "AllowAllPermit",
    "DeletePermit",
    "PermitDecision",
    "SeedObligationRecorder",
    "veto",
]
```

- [ ] **Step 4: Run test — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/core/test_delete_permit.py -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add personalscraper/core/delete_permit.py tests/core/test_delete_permit.py
git commit -m "feat(acquire-store): core/delete_permit.py — DeletePermit + AllowAllPermit protocols"
```

---

### Task 2 — Create `acquire/delete_authority.py`

**Files:**

- Create: `personalscraper/acquire/delete_authority.py`

- [ ] **Step 1: Create `personalscraper/acquire/delete_authority.py`**

```python
# personalscraper/acquire/delete_authority.py
"""Concrete DeletePermit + SeedObligationRecorder over acquire/store (RP3).

Deletion-time resolver: joins on seed_obligation.dispatched_path (exact
match + descendants). Does NOT use torrent-client content_path — those two
trees never overlap after ingest (DESIGN §7.2).

Fail-open contract: store absent / unreadable / lock-timeout / no-obligation
/ any lookup error → ALLOW. VETO only on positively-known unmet obligation.

Logging: personalscraper.logger.get_logger (NOT structlog.get_logger).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING

from personalscraper.core.delete_permit import (
    ALLOW,
    AllowAllPermit,
    DeletePermit,
    PermitDecision,
    SeedObligationRecorder,
    veto,
)
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire.store import ConcreteAcquireStore

log = get_logger("acquire.delete_authority")


class DeleteAuthority:
    """Implements DeletePermit and SeedObligationRecorder over the acquire store.

    Injected into dispatch/run.py and maintenance/disk_cleaner.py at the
    composition root. Never imported by those modules directly.

    Attributes:
        _store: The ConcreteAcquireStore (or None if store is absent).
    """

    def __init__(self, store: "ConcreteAcquireStore | None") -> None:
        """Initialise with the acquire store.

        Args:
            store: The ConcreteAcquireStore, or None to use fail-open fallback.
        """
        self._store = store

    def may_delete(self, path: Path) -> PermitDecision:
        """Consult persisted seed obligations before permitting a deletion.

        Fail-open: any error → ALLOW. VETO only when a positively-known
        unmet obligation exists AND the dispatched_path still exists on disk
        (path-exists guard makes stale obligations inert).

        Args:
            path: Absolute path about to be deleted.

        Returns:
            ALLOW if permitted, veto(reason) if a live unmet obligation exists.
        """
        if self._store is None:
            log.debug("acquire.delete_authority.no_store", path=str(path))
            return ALLOW

        try:
            obligation = self._store.seed.find_by_dispatched_path(path)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "acquire.delete_authority.lookup_failed",
                path=str(path),
                error=str(exc),
            )
            return ALLOW

        if obligation is None:
            # No obligation → ALLOW
            return ALLOW

        # Path-exists guard: a stale obligation (crash before move) is inert.
        if obligation.dispatched_path is not None and not Path(obligation.dispatched_path).exists():
            log.debug(
                "acquire.delete_authority.stale_obligation_inert",
                path=str(path),
                info_hash=obligation.info_hash,
            )
            return ALLOW

        # Check whether the seed obligation is satisfied.
        now = int(time.time())
        seed_time_elapsed = now - obligation.added_at
        seed_time_met = seed_time_elapsed >= obligation.min_seed_time_s
        # ratio satisfaction check is deferred to Ratio C1; here we only check time.
        if seed_time_met:
            return ALLOW

        reason = (
            f"seeding obligation not met: tracker={obligation.source_tracker} "
            f"info_hash={obligation.info_hash[:8]}... "
            f"elapsed={seed_time_elapsed}s < required={obligation.min_seed_time_s}s"
        )
        log.warning(
            "acquire.delete_authority.veto",
            path=str(path),
            info_hash=obligation.info_hash,
            source_tracker=obligation.source_tracker,
            seed_time_elapsed=seed_time_elapsed,
            min_seed_time_s=obligation.min_seed_time_s,
        )
        return veto(reason)

    def record_dispatch(
        self,
        *,
        staging_source: Path,
        dispatched_dest: Path,
    ) -> None:
        """No-op at this phase — write-before-move logic added in Phase 5.

        Args:
            staging_source: Staging path of the media file.
            dispatched_dest: Destination path after dispatch.
        """
        # Phase 5 adds basename+size torrent correlation here.
        log.debug(
            "acquire.delete_authority.record_dispatch.noop",
            staging_source=str(staging_source),
            dispatched_dest=str(dispatched_dest),
        )


def build_delete_authority(
    store: "ConcreteAcquireStore | None",
) -> DeleteAuthority:
    """Build a DeleteAuthority over the given store.

    Args:
        store: The ConcreteAcquireStore, or None for fail-open no-op.

    Returns:
        A DeleteAuthority ready for injection into dispatch/maintenance.
    """
    return DeleteAuthority(store=store)


__all__ = ["DeleteAuthority", "build_delete_authority"]
```

- [ ] **Step 2: Commit**

```bash
git add personalscraper/acquire/delete_authority.py
git commit -m "feat(acquire-store): acquire/delete_authority.py — deletion-time resolver (path-exists guard)"
```

---

### Task 3 — Adversarial fail-open mutation tests

**Files:**

- Create: `tests/acquire/test_delete_authority.py`

- [ ] **Step 1: Write the adversarial tests**

```python
# tests/acquire/test_delete_authority.py
"""Adversarial fail-open mutation tests for DeleteAuthority (DESIGN §12).

Verifies:
- Inject VETO → deleter sees VETO.
- Remove obligation → deleter sees ALLOW.
- Store absent → ALLOW.
- Store unreadable (raises on lookup) → ALLOW.
- Path-exists guard: stale obligation (dispatched_path missing) → ALLOW.
- Seedtime MET → ALLOW.
- Seedtime NOT met → VETO.
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personalscraper.acquire.delete_authority import DeleteAuthority, build_delete_authority
from personalscraper.acquire.domain import SeedObligation
from personalscraper.acquire.store import build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.delete_permit import ALLOW


@pytest.fixture()
def store(tmp_path: Path):
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    yield s
    s.close()


def _obligation(dispatched_path: str | None, min_seed_time_s: int = 999999) -> SeedObligation:
    return SeedObligation(
        info_hash="abc123def456",
        source_tracker="lacale",
        min_seed_time_s=min_seed_time_s,
        min_ratio=1.0,
        added_at=int(time.time()),
        dispatched_path=dispatched_path,
    )


def test_store_absent_returns_allow(tmp_path: Path) -> None:
    """No store → always ALLOW (fail-open)."""
    auth = build_delete_authority(store=None)
    decision = auth.may_delete(tmp_path / "movie.mkv")
    assert decision is ALLOW


def test_no_obligation_returns_allow(store, tmp_path: Path) -> None:
    """No matching obligation → ALLOW."""
    auth = build_delete_authority(store=store)
    decision = auth.may_delete(tmp_path / "movie.mkv")
    assert decision is ALLOW


def test_veto_on_active_unmet_obligation(store, tmp_path: Path) -> None:
    """Active obligation with seedtime NOT met → VETO."""
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")
    ob = _obligation(dispatched_path=str(path), min_seed_time_s=999999)
    store.seed.add(ob)
    auth = build_delete_authority(store=store)
    decision = auth.may_delete(path)
    assert decision is not ALLOW
    assert "lacale" in str(decision)


def test_allow_when_seedtime_met(store, tmp_path: Path) -> None:
    """Obligation with seedtime already elapsed → ALLOW."""
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")
    # added_at far in the past so elapsed >> min_seed_time_s
    past = int(time.time()) - 100_000
    ob = SeedObligation(
        info_hash="abc123",
        source_tracker="lacale",
        min_seed_time_s=3600,  # 1 hour, already elapsed
        min_ratio=1.0,
        added_at=past,
        dispatched_path=str(path),
    )
    store.seed.add(ob)
    auth = build_delete_authority(store=store)
    decision = auth.may_delete(path)
    assert decision is ALLOW


def test_stale_obligation_inert_when_path_missing(store, tmp_path: Path) -> None:
    """Path-exists guard: if dispatched_path no longer exists → ALLOW (stale)."""
    missing_path = tmp_path / "gone.mkv"
    # Do NOT create the file
    ob = _obligation(dispatched_path=str(missing_path), min_seed_time_s=999999)
    store.seed.add(ob)
    auth = build_delete_authority(store=store)
    decision = auth.may_delete(missing_path)
    assert decision is ALLOW


def test_store_lookup_exception_returns_allow(tmp_path: Path) -> None:
    """If store.seed.find_by_dispatched_path raises → ALLOW (fail-open)."""
    mock_store = MagicMock()
    mock_store.seed.find_by_dispatched_path.side_effect = RuntimeError("DB locked")
    auth = DeleteAuthority(store=mock_store)
    decision = auth.may_delete(tmp_path / "movie.mkv")
    assert decision is ALLOW


def test_removing_obligation_allows_deletion(store, tmp_path: Path) -> None:
    """After obligation is satisfied, may_delete returns ALLOW."""
    path = tmp_path / "movie.mkv"
    path.write_text("fake content")
    ob = _obligation(dispatched_path=str(path), min_seed_time_s=999999)
    row_id = store.seed.add(ob)
    # Mark obligation satisfied
    store.seed.mark_satisfied(row_id, satisfied_at=int(time.time()))
    auth = build_delete_authority(store=store)
    # Satisfied obligation is excluded by the query (satisfied_at IS NULL filter)
    decision = auth.may_delete(path)
    assert decision is ALLOW
```

- [ ] **Step 2: Run adversarial tests — expect PASS**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/test_delete_authority.py -v 2>&1 | tail -20
```

Expected: all 7 pass.

- [ ] **Step 3: Commit**

```bash
git add tests/acquire/test_delete_authority.py
git commit -m "test(acquire-store): adversarial fail-open mutation tests for DeleteAuthority"
```

---

### Task 4 — Wire `delete_authority` into `AcquireContext` + phase gate

**Files:**

- Modify: `personalscraper/acquire/_factory.py`
- Modify: `personalscraper/acquire/context.py`

- [ ] **Step 1: Add `delete_authority` slot to `AcquireContext`**

In `personalscraper/acquire/context.py`, add:

```python
if TYPE_CHECKING:
    from personalscraper.acquire.delete_authority import DeleteAuthority

# In AcquireContext dataclass, add field:
delete_authority: "DeleteAuthority | None" = None
```

Update `close()` docstring to note `delete_authority` is not lifecycle-owned (stateless).

- [ ] **Step 2: Update `_factory.py` to build and attach `delete_authority`**

In `personalscraper/acquire/_factory.py`:

```python
from personalscraper.acquire.delete_authority import build_delete_authority

# After building store:
delete_authority = build_delete_authority(store=store)

return AcquireContext(
    tracker_registry=tracker_registry,
    store=store,
    delete_authority=delete_authority,
    torrent_client=torrent_client,
)
```

- [ ] **Step 3: Run full test suite**

```bash
cd /Users/izno/dev/PersonnalScaper && python -m pytest tests/acquire/ tests/core/ -x -q 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 4: Run make check (phase gate)**

```bash
cd /Users/izno/dev/PersonnalScaper && make check 2>&1 | tail -30
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/context.py personalscraper/acquire/_factory.py
git commit -m "chore(acquire-store): phase 4 gate — DeletePermit + DeleteAuthority wired into AcquireContext"
```
