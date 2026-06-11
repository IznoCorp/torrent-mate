# Phase 04b — Service + State Machine + Wiring (`acquire/service.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add `AcquisitionService` (batch loop + `RunSummary`), the three new store methods
(`claim_for_search`, `mark_grabbed`, `list_stale_searching`), `WantedItem.id` field,
`list_pending()` SELECT id fix, `WantedSubStore` Protocol updates, `GrabCore` sub-handle,
`TrackerRegistry.transports()` (already done in phase 02 — verify), and
`_factory.build_acquire_context` wiring. Load-bearing: atomic claim concurrency test and
the attempts-cap → abandoned path.

**Architecture:** `service.py` drives the `GrabOrchestrator` in a loop; the state machine
lives in the new store methods. `WantedItem.id` is added as an optional field (pre-1.0
in-place evolution, no migration needed — `id` is the SQLite implicit rowid). `GrabCore` is
a frozen dataclass carrying `AcquisitionService` + transports, attached as a single new
field on `AcquireContext`.

**Tech Stack:** Python 3.12, SQLite `BEGIN IMMEDIATE`, frozen kw_only dataclasses,
`acquire/store.py`, `acquire/orchestrator.py`, `acquire/_factory.py`, `acquire/context.py`,
`acquire/_ports.py`.

---

## Gate (start of phase)

Previous phases produced:

- `acquire/desired.py`, `acquire/_dedup.py`, `acquire/_filters.py`
- `acquire/orchestrator.py` with `GrabOrchestrator` + `GrabOutcome` + `MAX_ATTEMPTS`
- `api/tracker/_registry.py` with `transports()` (phase 02)

---

## File Map

- **Modify:** `personalscraper/acquire/domain.py` — add `id: int | None = None` to `WantedItem`
- **Modify:** `personalscraper/acquire/store.py` — extend `_WantedSubStore` with `claim_for_search`, `mark_grabbed`, `list_stale_searching`; fix `list_pending` SELECT; fix `_row_to_wanted`
- **Modify:** `personalscraper/acquire/_ports.py` — extend `WantedSubStore` Protocol
- **Create:** `personalscraper/acquire/service.py`
- **Modify:** `personalscraper/acquire/context.py` — add `grab: GrabCore | None` field
- **Modify:** `personalscraper/acquire/_factory.py` — wire `GrabCore` in `build_acquire_context`
- **Test:** `tests/acquire/test_service.py`

---

## Task 1: `WantedItem.id` field + `list_pending` SELECT fix + `_row_to_wanted` fix

`WantedItem` currently has no `id` field — the orchestrator cannot call `claim_for_search`
or `mark_grabbed` without a rowid. This is a pre-1.0 in-place VO evolution: add
`id: int | None = None` as the last field (default None keeps all existing construction
sites valid).

**Files:**

- Modify: `personalscraper/acquire/domain.py`
- Modify: `personalscraper/acquire/store.py`
- Test: `tests/acquire/test_service.py` (golden id round-trip)

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_service.py
"""Tests for AcquisitionService + state machine + WantedItem.id round-trip.

Load-bearing tests called out:
- list_pending()[0].id round-trips the rowid (DESIGN §7, was a blocking gap)
- Two concurrent claim_for_search → exactly one True (atomic claim)
- Failure after 'searching' → row back to 'pending' (retryable)
- attempts >= MAX_ATTEMPTS cap → 'abandoned' + WantedAbandoned
- hash-guard: re-run after add-success+mark_grabbed-crash → no double-emit
"""
from __future__ import annotations

from pathlib import Path
from collections.abc import Iterator

import pytest

from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.store import ConcreteAcquireStore, build_acquire_store
from personalscraper.conf.models.acquire import AcquireConfig
from personalscraper.core.identity import MediaRef


@pytest.fixture
def store(tmp_path: Path) -> Iterator[ConcreteAcquireStore]:
    cfg = AcquireConfig(db_path=tmp_path / "acquire.db")
    s = build_acquire_store(cfg)
    try:
        yield s
    finally:
        s.close()


def _pending_item() -> WantedItem:
    return WantedItem(
        media_ref=MediaRef(tvdb_id=99),
        kind="movie",
        status="pending",
        enqueued_at=1_700_000_000,
    )


def test_list_pending_populates_id(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING (DESIGN §7): list_pending()[0].id round-trips the rowid."""
    rowid = store.wanted.add(_pending_item())
    pending = store.wanted.list_pending()
    assert len(pending) == 1
    assert pending[0].id == rowid, (
        f"Expected id={rowid}, got id={pending[0].id} — list_pending must SELECT id"
    )
```

- [ ] **Step 2: Run to verify fails**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/acquire/test_service.py::test_list_pending_populates_id -v
```

Expected: `FAILED` — `pending[0].id` is `None` (field doesn't exist yet or SELECT missing).

- [ ] **Step 3: Add `id: int | None = None` to `WantedItem` in `domain.py`**

In `personalscraper/acquire/domain.py`, add `id: int | None = None` as a new field in
`WantedItem` after `attempts`. Also update `__post_init__` if needed (no change required —
`id` has no constraint).

The final field order in `WantedItem`:

```python
@dataclass(frozen=True)
class WantedItem:
    media_ref: MediaRef
    kind: WantedKind
    status: WantedStatus
    enqueued_at: int
    followed_id: int | None = None
    season: int | None = None
    episode: int | None = None
    criteria_json: str | None = None
    last_search_at: int | None = None
    attempts: int = 0
    id: int | None = None          # rowid — populated by list_pending() / get()
```

- [ ] **Step 4: Fix `_row_to_wanted` in `store.py` to populate `id`**

In `personalscraper/acquire/store.py`, update `_row_to_wanted` to pass `id=row["id"]`:

```python
def _row_to_wanted(row: sqlite3.Row) -> WantedItem:
    return WantedItem(
        media_ref=_media_ref_from_json(row["media_ref_json"]),
        kind=cast(WantedKind, row["kind"]),
        status=cast(WantedStatus, row["status"]),
        enqueued_at=row["enqueued_at"],
        followed_id=row["followed_id"],
        season=row["season"],
        episode=row["episode"],
        criteria_json=row["criteria_json"],
        last_search_at=row["last_search_at"],
        attempts=row["attempts"],
        id=row["id"],
    )
```

- [ ] **Step 5: Fix `list_pending` SELECT to include `id`**

In `_WantedSubStore.list_pending`, change:

```sql
SELECT followed_id, media_ref_json, kind, season, episode,
       status, criteria_json, enqueued_at, last_search_at, attempts
FROM wanted WHERE status = 'pending'
ORDER BY id
```

to:

```sql
SELECT id, followed_id, media_ref_json, kind, season, episode,
       status, criteria_json, enqueued_at, last_search_at, attempts
FROM wanted WHERE status = 'pending'
ORDER BY id
```

Also fix `get()` to include `id` in the SELECT and pass it through `_row_to_wanted`.

- [ ] **Step 6: Run the id round-trip test**

```bash
python -m pytest tests/acquire/test_service.py::test_list_pending_populates_id -v
```

Expected: PASSED.

- [ ] **Step 7: Run existing store tests to confirm no regressions**

```bash
python -m pytest tests/acquire/test_store.py -v
```

Expected: all PASSED (domain VO changes are backward-compatible — `id` defaults to `None`).

- [ ] **Step 8: Commit**

```bash
git add personalscraper/acquire/domain.py personalscraper/acquire/store.py \
    tests/acquire/test_service.py
git commit -m "feat(grab-core): WantedItem.id field + list_pending SELECT id + _row_to_wanted fix"
```

---

## Task 2: `claim_for_search`, `mark_grabbed`, `list_stale_searching` store methods

**Files:**

- Modify: `personalscraper/acquire/store.py`
- Modify: `personalscraper/acquire/_ports.py`
- Modify: `tests/acquire/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/acquire/test_service.py
import time


def test_claim_for_search_atomic_only_one_wins(tmp_path: Path) -> None:
    """LOAD-BEARING (DESIGN §7): two claim_for_search on same row → exactly one True."""
    cfg = AcquireConfig(db_path=tmp_path / "acquire2.db")
    store1 = build_acquire_store(cfg)
    store2 = build_acquire_store(cfg)
    try:
        rowid = store1.wanted.add(_pending_item())
        now = int(time.time())
        result1 = store1.wanted.claim_for_search(rowid, now)
        result2 = store2.wanted.claim_for_search(rowid, now)
        wins = [r for r in (result1, result2) if r is True]
        assert len(wins) == 1, (
            f"Exactly one claim must win; got result1={result1}, result2={result2}"
        )
    finally:
        store1.close()
        store2.close()


def test_claim_for_search_stamps_attempts_and_last_search_at(store: ConcreteAcquireStore) -> None:
    rowid = store.wanted.add(_pending_item())
    now = 1_700_000_100
    won = store.wanted.claim_for_search(rowid, now)
    assert won is True
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "searching"
    assert item.attempts == 1
    assert item.last_search_at == now


def test_claim_for_search_returns_false_when_already_searching(store: ConcreteAcquireStore) -> None:
    rowid = store.wanted.add(_pending_item())
    now = int(time.time())
    assert store.wanted.claim_for_search(rowid, now) is True
    # Second call on same row (now searching) must return False
    assert store.wanted.claim_for_search(rowid, now) is False


def test_mark_grabbed_persists_status_and_hash(store: ConcreteAcquireStore) -> None:
    rowid = store.wanted.add(_pending_item())
    store.wanted.claim_for_search(rowid, int(time.time()))
    store.wanted.mark_grabbed(rowid, "deadbeef1234")
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "grabbed"
    assert item.grabbed_hash == "deadbeef1234"


def test_list_stale_searching_returns_old_searching_rows(store: ConcreteAcquireStore) -> None:
    rowid = store.wanted.add(_pending_item())
    old_ts = 1_000_000  # far in the past
    store.wanted.claim_for_search(rowid, old_ts)
    # Stale = last_search_at older than (now - threshold)
    stale = store.wanted.list_stale_searching(older_than=old_ts + 1)
    assert any(i.id == rowid for i in stale)


def test_list_stale_searching_excludes_recent(store: ConcreteAcquireStore) -> None:
    rowid = store.wanted.add(_pending_item())
    now = int(time.time())
    store.wanted.claim_for_search(rowid, now)
    # Nothing is stale since last_search_at == now
    stale = store.wanted.list_stale_searching(older_than=now - 1)
    assert not any(i.id == rowid for i in stale)
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_service.py::test_claim_for_search_stamps_attempts_and_last_search_at -v
```

Expected: `AttributeError` — `claim_for_search` not defined.

- [ ] **Step 3: Add `grabbed_hash` column awareness + new store methods to `store.py`**

`mark_grabbed` needs to persist the `info_hash`. The `wanted` table already has a
`grabbed_hash` column if it was added in a migration — check `acquire/migrations/` first.

```bash
ls /Users/izno/dev/PersonnalScaper/personalscraper/acquire/migrations/
grep -r "grabbed_hash\|info_hash" /Users/izno/dev/PersonnalScaper/personalscraper/acquire/migrations/ --include="*.sql"
```

If `grabbed_hash` column is absent, create a new migration:
`personalscraper/acquire/migrations/002_add_grabbed_hash.sql`:

```sql
-- 002_add_grabbed_hash.sql
-- Add grabbed_hash column to wanted for idempotence guard (RP5b).
ALTER TABLE wanted ADD COLUMN grabbed_hash TEXT;
PRAGMA user_version = 2;
```

Add `grabbed_hash: str | None = None` field to `WantedItem` in `domain.py` (after `id`).
Update `_row_to_wanted` to include `grabbed_hash=row["grabbed_hash"]`.
Update `list_pending` and `get` SELECTs to include `grabbed_hash`.

Then add these methods to `_WantedSubStore` in `store.py`:

```python
    def claim_for_search(self, wanted_id: int, now: int) -> bool:
        """Atomically claim a pending item for searching.

        Runs one ``UPDATE … WHERE id=? AND status='pending'`` inside a
        ``BEGIN IMMEDIATE`` transaction (the single serialisation point for
        concurrent grabbers). Returns ``True`` iff this call won the claim.
        Stamps ``attempts + 1`` and ``last_search_at = now``.

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            now: Unix epoch seconds (stamps ``last_search_at``).

        Returns:
            ``True`` if this caller won the claim; ``False`` if the row
            was already claimed by another caller (``rowcount == 0``).
        """
        with _write_tx(self._conn):
            cur = self._conn.execute(
                """
                UPDATE wanted
                SET status = 'searching',
                    attempts = attempts + 1,
                    last_search_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (now, wanted_id),
            )
            return cur.rowcount == 1

    def mark_grabbed(self, wanted_id: int, info_hash: str) -> None:
        """Persist status='grabbed' and the info_hash for the idempotence guard.

        Persisting the hash means a crash between ``add()`` and this write
        does NOT double-emit ``GrabSucceeded`` on re-run (the re-run sees
        the hash and short-circuits — DESIGN §7).

        Args:
            wanted_id: Rowid of the ``wanted`` row.
            info_hash: Torrent info-hash returned by ``TorrentAdder.add()``.
        """
        with _write_tx(self._conn):
            self._conn.execute(
                """
                UPDATE wanted
                SET status = 'grabbed', grabbed_hash = ?
                WHERE id = ?
                """,
                (info_hash, wanted_id),
            )

    def list_stale_searching(self, older_than: int) -> list[WantedItem]:
        """Return wanted rows stuck in 'searching' with last_search_at < older_than.

        Feeds back into the run loop alongside ``list_pending`` to recover
        items whose process was killed mid-grab before any status write.

        Args:
            older_than: Unix epoch seconds threshold.

        Returns:
            List of :class:`WantedItem` (possibly empty).
        """
        self._conn.row_factory = sqlite3.Row
        rows = self._conn.execute(
            """
            SELECT id, followed_id, media_ref_json, kind, season, episode,
                   status, criteria_json, enqueued_at, last_search_at, attempts,
                   grabbed_hash
            FROM wanted
            WHERE status = 'searching' AND last_search_at < ?
            ORDER BY id
            """,
            (older_than,),
        ).fetchall()
        return [_row_to_wanted(r) for r in rows]
```

- [ ] **Step 4: Update `WantedSubStore` Protocol in `_ports.py`**

Add the three new method signatures to `WantedSubStore`:

```python
    def claim_for_search(self, wanted_id: int, now: int) -> bool:
        """Atomically claim a pending item; return True iff this call won."""
        ...

    def mark_grabbed(self, wanted_id: int, info_hash: str) -> None:
        """Persist status='grabbed' + info_hash for the idempotence guard."""
        ...

    def list_stale_searching(self, older_than: int) -> list[WantedItem]:
        """Return wanted rows stuck in 'searching' older than the threshold."""
        ...
```

- [ ] **Step 5: Run store tests**

```bash
python -m pytest tests/acquire/test_service.py -v
```

Expected: All new store tests PASSED. Note: `test_mark_grabbed_persists_status_and_hash`
expects `item.grabbed_hash` — this requires `grabbed_hash` on `WantedItem` and in the SELECT.

- [ ] **Step 6: Run full store test suite to confirm no regressions**

```bash
python -m pytest tests/acquire/test_store.py tests/acquire/test_service.py -v
```

Expected: all PASSED.

- [ ] **Step 7: Commit**

```bash
git add personalscraper/acquire/domain.py personalscraper/acquire/store.py \
    personalscraper/acquire/_ports.py \
    personalscraper/acquire/migrations/ \
    tests/acquire/test_service.py
git commit -m "feat(grab-core): claim_for_search + mark_grabbed + list_stale_searching + grabbed_hash"
```

---

## Task 3: `AcquisitionService` + `RunSummary` + attempts cap

**Files:**

- Create: `personalscraper/acquire/service.py`
- Modify: `tests/acquire/test_service.py`

- [ ] **Step 1: Write the failing tests**

```python
# Add to tests/acquire/test_service.py
from unittest.mock import MagicMock, patch

from personalscraper.acquire.orchestrator import GrabOutcome, MAX_ATTEMPTS
from personalscraper.acquire.service import AcquisitionService, RunSummary


def _make_service(store, orchestrator=None) -> AcquisitionService:
    if orchestrator is None:
        orchestrator = MagicMock()
        orchestrator.grab.return_value = GrabOutcome(
            grabbed=True, info_hash="abc", event_emitted="GrabSucceeded"
        )
    return AcquisitionService(store=store, orchestrator=orchestrator)


def test_run_summary_counts_grabbed(store: ConcreteAcquireStore) -> None:
    rowid = store.wanted.add(_pending_item())
    service = _make_service(store)
    summary = service.run(limit=10)
    assert isinstance(summary, RunSummary)
    assert summary.grabbed >= 0  # at least tried


def test_run_claims_and_grabs_pending_items(store: ConcreteAcquireStore) -> None:
    store.wanted.add(_pending_item())
    store.wanted.add(_pending_item())
    mock_orch = MagicMock()
    mock_orch.grab.return_value = GrabOutcome(
        grabbed=True, info_hash="h1", event_emitted="GrabSucceeded"
    )
    service = _make_service(store, mock_orch)
    summary = service.run(limit=10)
    assert mock_orch.grab.call_count == 2
    assert summary.grabbed == 2


def test_run_respects_limit(store: ConcreteAcquireStore) -> None:
    for _ in range(5):
        store.wanted.add(_pending_item())
    mock_orch = MagicMock()
    mock_orch.grab.return_value = GrabOutcome(
        grabbed=True, info_hash="h", event_emitted="GrabSucceeded"
    )
    service = _make_service(store, mock_orch)
    summary = service.run(limit=2)
    assert mock_orch.grab.call_count == 2
    assert summary.grabbed == 2


def test_attempts_cap_abandons_item(store: ConcreteAcquireStore) -> None:
    """LOAD-BEARING (DESIGN §6.2): attempts >= MAX_ATTEMPTS → abandoned + WantedAbandoned."""
    import time
    from personalscraper.acquire.events import WantedAbandoned
    rowid = store.wanted.add(_pending_item())
    # Exhaust attempts by claiming MAX_ATTEMPTS times without success
    for _ in range(MAX_ATTEMPTS):
        now = int(time.time())
        store.wanted.claim_for_search(rowid, now)
        store.wanted.set_status(rowid, "pending")  # reset to pending as if retried

    # One more claim should still work (attempt count is MAX_ATTEMPTS)
    now = int(time.time())
    won = store.wanted.claim_for_search(rowid, now)
    assert won is True

    mock_event_bus = MagicMock()
    mock_orch = MagicMock()
    # Service should detect attempts >= MAX_ATTEMPTS and abandon before calling grab
    service = AcquisitionService(
        store=store,
        orchestrator=mock_orch,
        event_bus=mock_event_bus,
    )
    summary = service.run(limit=10)
    # Grab should NOT have been called (service abandons at cap check)
    assert mock_orch.grab.call_count == 0
    # Item should be abandoned
    item = store.wanted.get(rowid)
    assert item is not None
    assert item.status == "abandoned"
    # WantedAbandoned must have been emitted
    emitted = [c.args[0] for c in mock_event_bus.emit.call_args_list]
    assert any(isinstance(e, WantedAbandoned) and "attempts_cap" in e.reason for e in emitted)
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_service.py::test_run_claims_and_grabs_pending_items -v
```

Expected: `ImportError` — `AcquisitionService` not defined.

- [ ] **Step 3: Create `service.py`**

```python
# personalscraper/acquire/service.py
"""Acquisition service — batch grab loop + atomic-claim state machine (RP5b).

``AcquisitionService.run()`` iterates ``list_pending`` + ``list_stale_searching``,
claims each item via ``claim_for_search`` (atomic ``BEGIN IMMEDIATE`` UPDATE),
checks the attempts cap (→ abandoned), then delegates to ``GrabOrchestrator.grab()``.

Import direction: acquire/, api/, core/, events/ only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from personalscraper.acquire.events import WantedAbandoned
from personalscraper.acquire.orchestrator import MAX_ATTEMPTS
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from personalscraper.acquire._ports import AcquireStore
    from personalscraper.acquire.orchestrator import GrabOrchestrator
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.service")

# Stale-searching threshold: items stuck in 'searching' for longer than this
# are eligible for recovery (process killed mid-grab).
_STALE_THRESHOLD_S = 3600  # 1 hour


@dataclass(frozen=True, kw_only=True)
class RunSummary:
    """Summary of one ``AcquisitionService.run()`` call.

    Attributes:
        grabbed: Count of items successfully grabbed.
        retried: Count of items reset to pending (RETRYABLE failure).
        abandoned: Count of items abandoned (TERMINAL failure or attempts cap).
        skipped: Count of items whose claim was lost to a concurrent process.
    """

    grabbed: int = 0
    retried: int = 0
    abandoned: int = 0
    skipped: int = 0


class AcquisitionService:
    """Batch grab loop over the wanted queue (RP5b).

    Attributes:
        _store: Acquire store for queue reads + status writes.
        _orchestrator: Single-item grab chain.
        _event_bus: In-process event bus (for attempts-cap WantedAbandoned).
    """

    def __init__(
        self,
        *,
        store: "AcquireStore",
        orchestrator: "GrabOrchestrator",
        event_bus: "EventBus | None" = None,
    ) -> None:
        """Initialise the service with injected deps.

        Args:
            store: Acquire store.
            orchestrator: Single-item grab chain.
            event_bus: Optional event bus for emitting WantedAbandoned on cap.
        """
        self._store = store
        self._orchestrator = orchestrator
        self._event_bus = event_bus

    def run(self, *, limit: int | None = None) -> RunSummary:
        """Process the pending + stale-searching wanted queue.

        For each item:
        1. ``claim_for_search(id, now)`` — atomic; skip if False (concurrent loss).
        2. Check ``attempts >= MAX_ATTEMPTS`` — abandon without calling grab.
        3. Delegate to ``GrabOrchestrator.grab(item)``.

        Args:
            limit: Maximum number of items to attempt in this run. ``None`` =
                no limit (process all pending + stale items).

        Returns:
            :class:`RunSummary` with outcome counts.
        """
        now = int(time.time())
        stale_threshold = now - _STALE_THRESHOLD_S

        pending = self._store.wanted.list_pending()
        stale = self._store.wanted.list_stale_searching(older_than=stale_threshold)

        # Merge pending + stale; de-duplicate by id (a stale row is NOT pending).
        seen_ids: set[int] = set()
        queue = []
        for item in pending + stale:
            if item.id is not None and item.id not in seen_ids:
                seen_ids.add(item.id)
                queue.append(item)

        if limit is not None:
            queue = queue[:limit]

        grabbed = retried = abandoned = skipped = 0

        for item in queue:
            assert item.id is not None  # noqa: S101 — ensured by list_pending SELECT
            won = self._store.wanted.claim_for_search(item.id, now)
            if not won:
                skipped += 1
                log.debug("acquire.service.claim_lost", wanted_id=item.id)
                continue

            # Re-fetch to get the updated attempts count after claim
            current = self._store.wanted.get(item.id)
            if current is None:
                skipped += 1
                continue

            if current.attempts >= MAX_ATTEMPTS:
                self._store.wanted.set_status(item.id, "abandoned")
                event = WantedAbandoned(
                    media_ref=item.media_ref, reason="attempts_cap"
                )
                if self._event_bus is not None:
                    self._event_bus.emit(event)
                log.warning(
                    "acquire.service.attempts_cap_abandoned",
                    wanted_id=item.id,
                    attempts=current.attempts,
                )
                abandoned += 1
                continue

            outcome = self._orchestrator.grab(current)
            if outcome.grabbed:
                grabbed += 1
            elif outcome.event_emitted == "WantedAbandoned":
                abandoned += 1
            else:
                retried += 1

        log.info(
            "acquire.service.run_complete",
            grabbed=grabbed,
            retried=retried,
            abandoned=abandoned,
            skipped=skipped,
        )
        return RunSummary(
            grabbed=grabbed, retried=retried, abandoned=abandoned, skipped=skipped
        )


__all__ = ["AcquisitionService", "RunSummary"]
```

- [ ] **Step 4: Run service tests**

```bash
python -m pytest tests/acquire/test_service.py -v
```

Expected: All PASSED including `test_attempts_cap_abandons_item`.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/service.py tests/acquire/test_service.py
git commit -m "feat(grab-core): AcquisitionService + RunSummary + attempts cap"
```

---

## Task 4: `GrabCore` handle + `AcquireContext` wiring + `_factory` update

**Files:**

- Create (inline in `service.py` or separate): `GrabCore` frozen dataclass in `service.py`
- Modify: `personalscraper/acquire/context.py`
- Modify: `personalscraper/acquire/_factory.py`

- [ ] **Step 1: Add `GrabCore` dataclass to `service.py`**

```python
# Add to personalscraper/acquire/service.py (after imports, before AcquisitionService)

@dataclass(frozen=True, kw_only=True)
class GrabCore:
    """Single sub-handle bundling the grab orchestrator + service + transports.

    Attached as ``AcquireContext.grab`` (one new field). Built inside
    ``_factory.build_acquire_context`` — the only frame holding registry +
    ``config.ranking`` + ``torrent_client`` + ``event_bus`` + ``store`` together.

    ``GrabCore is None`` when ``torrent_client is None`` (read-only commands
    can still search+filter+rank via the registry, but cannot add).

    Attributes:
        service: Batch acquisition loop.
        orchestrator: Single-item grab chain (also accessible directly for CLI --dry-run).
    """

    service: AcquisitionService
    orchestrator: "GrabOrchestrator"
```

- [ ] **Step 2: Add `grab: GrabCore | None = None` to `AcquireContext`**

In `personalscraper/acquire/context.py`, add ONE new field at the end:

```python
    grab: "GrabCore | None" = None
```

Update the `close()` docstring to mention `grab` does NOT need closing (it holds no
resources — all owned resources are on `tracker_registry` and `store`).

Update `TYPE_CHECKING` imports to add `GrabCore`:

```python
if TYPE_CHECKING:
    ...
    from personalscraper.acquire.service import GrabCore
```

- [ ] **Step 3: Wire `GrabCore` in `build_acquire_context`**

In `personalscraper/acquire/_factory.py`, after building `tracker_registry` and `store`,
add `GrabCore` construction when `torrent_client` is not `None`:

```python
    grab: GrabCore | None = None
    if torrent_client is not None:
        from personalscraper.acquire.orchestrator import GrabOrchestrator  # noqa: PLC0415
        from personalscraper.acquire.service import AcquisitionService, GrabCore  # noqa: PLC0415

        orchestrator = GrabOrchestrator(
            tracker_registry=tracker_registry,
            torrent_client=torrent_client,
            store=store,
            event_bus=event_bus,
            ranking=config.ranking,
        )
        service = AcquisitionService(
            store=store,
            orchestrator=orchestrator,
            event_bus=event_bus,
        )
        grab = GrabCore(service=service, orchestrator=orchestrator)

    return AcquireContext(
        tracker_registry=tracker_registry,
        store=store,
        delete_authority=delete_authority,
        torrent_client=torrent_client,
        grab=grab,
    )
```

- [ ] **Step 4: Write a wiring smoke test**

```python
# Add to tests/acquire/test_factory.py (existing file)
# or tests/acquire/test_service.py

def test_build_acquire_context_no_torrent_client_grab_is_none(tmp_path) -> None:
    """Without torrent_client, grab slot must be None."""
    from personalscraper.acquire._factory import build_acquire_context
    from unittest.mock import MagicMock
    # Build a minimal config/settings/event_bus/cb_policy stub
    # (mirrors existing test_factory.py fixtures)
    # ... (use existing config fixture from test_factory.py)
    pass  # Extend the existing factory test instead — see below
```

Instead, open `tests/acquire/test_factory.py` and verify it already tests
`build_acquire_context`. Add a single assertion:

```python
# In the existing test that calls build_acquire_context without torrent_client:
assert ctx.grab is None
```

- [ ] **Step 5: Run factory + context tests**

```bash
python -m pytest tests/acquire/test_factory.py tests/acquire/test_context.py -v
```

Expected: all PASSED.

- [ ] **Step 6: Lint + size check**

```bash
python -m ruff check personalscraper/acquire/service.py personalscraper/acquire/context.py \
    personalscraper/acquire/_factory.py
python -m mypy personalscraper/acquire/service.py
python scripts/check-module-size.py personalscraper/acquire/service.py
```

Expected: zero errors; `service.py` under 200 LOC.

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: passing summary, no regressions.

- [ ] **Step 8: Commit phase gate**

```bash
git add personalscraper/acquire/service.py personalscraper/acquire/context.py \
    personalscraper/acquire/_factory.py tests/acquire/test_service.py \
    tests/acquire/test_factory.py
git commit -m "feat(grab-core): GrabCore handle + AcquireContext wiring + phase 04b gate"
```
