# Phase 04a — Orchestrator (`acquire/orchestrator.py`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `GrabOrchestrator` — the §1 chain for ONE claimed `WantedItem`.
Covers the full RETRYABLE/TERMINAL failure taxonomy, `GrabSucceeded`/`GrabFailed`/
`WantedAbandoned` emission, `GrabOutcome`, and golden fetch+add tests. The NEGATIVE
seed-write assert is load-bearing.

**Architecture:** `orchestrator.py` takes narrow deps (NOT `AppContext`): `tracker_registry`,
`transports`, `torrent_client`, `event_bus`, `ranking`. The `AcquisitionService` (4b) drives
it in a batch loop; `GrabOrchestrator` handles exactly one item. `CircuitOpenError` is caught
separately from `ApiError` — they are siblings, not a subtype relationship.

**Tech Stack:** Python 3.12, frozen kw_only dataclasses, `acquire/desired.py`,
`acquire/_dedup.py`, `acquire/_filters.py`, `api/tracker/_registry.py`,
`api/tracker/_fetch.py` (`resolve_source`), `api/torrent/_contracts.py` (`TorrentAdder`),
`core/event_bus.py`, `core/_contracts.py` (`CircuitOpenError`), `acquire/events.py`.

---

## Gate (start of phase)

Previous phases produced:

- `acquire/desired.py`: `Resolution`, `QualityProfile`, `SourceCriteria`, `effective_quality`
- `acquire/_dedup.py`: `SearchOutcome`, `dedup()`, `normalize_title_core`
- `acquire/_filters.py`: `apply_hard_filters()`
- `api/tracker/_registry.py`: `search_candidates()`, `transports()`

---

## File Map

- **Create:** `personalscraper/acquire/orchestrator.py`
- **Test:** `tests/acquire/test_orchestrator.py`

---

## Task 1: `GrabOutcome` dataclass

**Files:**

- Create: `personalscraper/acquire/orchestrator.py`
- Test: `tests/acquire/test_orchestrator.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/acquire/test_orchestrator.py
"""Non-vacuous tests for GrabOrchestrator.

Load-bearing tests called out explicitly:
- Golden fetch+add happy path (mocked TorrentAdder → GrabSucceeded payload)
- NEGATIVE seed-write assert (record_dispatch/seed.add call_count == 0)
- Auth-fail → TERMINAL WantedAbandoned
- Conflict-dup (idempotent add) → GrabSucceeded (not an error)
- CircuitOpenError caught separately → RETRYABLE GrabFailed (not a batch crash)
- All-filtered → TERMINAL WantedAbandoned('all_filtered')
- All-trackers-errored → RETRYABLE GrabFailed('trackers_unavailable')
"""
from __future__ import annotations

from personalscraper.acquire.orchestrator import GrabOutcome


def test_grab_outcome_is_frozen_dataclass() -> None:
    outcome = GrabOutcome(grabbed=True, info_hash="abc123", event_emitted="GrabSucceeded")
    assert outcome.grabbed is True
    assert outcome.info_hash == "abc123"
```

- [ ] **Step 2: Run to verify fails**

```bash
cd /Users/izno/dev/PersonnalScaper
python -m pytest tests/acquire/test_orchestrator.py::test_grab_outcome_is_frozen_dataclass -v
```

Expected: `ImportError`.

- [ ] **Step 3: Scaffold `orchestrator.py` with `GrabOutcome`**

```python
# personalscraper/acquire/orchestrator.py
"""Grab orchestrator — single-item §1 chain (RP5b).

``GrabOrchestrator.grab(item)`` executes the full grab pipeline for ONE
claimed ``WantedItem``:

    claim → profile → search → hard-filter → dedup → rank → resolve_source
    → add → mark_grabbed → emit GrabSucceeded

Failure routing (§6.2 taxonomy):
- RETRYABLE  → reset wanted searching→pending, emit GrabFailed
- TERMINAL   → set wanted →abandoned, emit WantedAbandoned

``CircuitOpenError`` is a sibling of ``ApiError`` (NOT a subclass) —
caught in a separate ``except`` clause to avoid silently swallowing it
inside a broad ``except ApiError``.

Dep injection: narrow constructor (NOT AppContext).  ``AcquisitionService``
(phase 4b) drives this in a batch loop.

Import direction: acquire/, api/, core/, events/, conf/ only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from personalscraper.acquire._dedup import SearchOutcome, dedup
from personalscraper.acquire._filters import apply_hard_filters
from personalscraper.acquire.desired import QualityProfile, effective_quality
from personalscraper.acquire.events import GrabFailed, GrabSucceeded, WantedAbandoned
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api.tracker._fetch import resolve_source
from personalscraper.api.tracker._ranking import RankingConfig, rank
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.logger import get_logger

if TYPE_CHECKING:
    from collections.abc import Mapping

    from personalscraper.acquire._ports import WantedSubStore
    from personalscraper.acquire.desired import SourceCriteria
    from personalscraper.acquire.domain import FollowedSeries, WantedItem
    from personalscraper.api.torrent._contracts import TorrentAdder
    from personalscraper.api.tracker._registry import TrackerRegistry
    from personalscraper.api.transport._http import HttpTransport
    from personalscraper.core.event_bus import EventBus

log = get_logger("acquire.orchestrator")

# Maximum grab attempts before a WantedItem is permanently abandoned.
MAX_ATTEMPTS = 5


@dataclass(frozen=True, kw_only=True)
class GrabOutcome:
    """Result of one ``GrabOrchestrator.grab()`` call.

    Attributes:
        grabbed: ``True`` on success (torrent added + mark_grabbed written).
        info_hash: Torrent info-hash on success, or ``None``.
        event_emitted: Name of the event class emitted
            (``"GrabSucceeded"``, ``"GrabFailed"``, ``"WantedAbandoned"``).
        reason: Failure/abandonment reason, or ``None`` on success.
    """

    grabbed: bool
    info_hash: str | None = None
    event_emitted: str = ""
    reason: str | None = None
```

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/acquire/test_orchestrator.py::test_grab_outcome_is_frozen_dataclass -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/orchestrator.py tests/acquire/test_orchestrator.py
git commit -m "feat(grab-core): scaffold GrabOutcome dataclass"
```

---

## Task 2: `GrabOrchestrator` — happy path (golden fetch+add)

**Files:**

- Modify: `personalscraper/acquire/orchestrator.py`
- Modify: `tests/acquire/test_orchestrator.py`

- [ ] **Step 1: Write the golden fetch+add test**

```python
# Add to tests/acquire/test_orchestrator.py
from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch, call
from pathlib import Path

import pytest

from personalscraper.acquire.desired import QualityProfile, Resolution
from personalscraper.acquire.domain import WantedItem
from personalscraper.acquire.events import GrabSucceeded, GrabFailed, WantedAbandoned
from personalscraper.acquire.orchestrator import GrabOrchestrator, GrabOutcome
from personalscraper.acquire._dedup import SearchOutcome
from personalscraper.api._contracts import ApiError, MediaType
from personalscraper.api._units import ByteSize
from personalscraper.api.tracker._base import TrackerResult
from personalscraper.api.tracker._ranking import RankingConfig
from personalscraper.api.torrent._base import TorrentSource
from personalscraper.core._contracts import CircuitOpenError
from personalscraper.core.identity import MediaRef


def _make_wanted(
    status: str = "searching",
    attempts: int = 1,
    wanted_id: int = 42,
    kind: str = "movie",
) -> WantedItem:
    return WantedItem(
        id=wanted_id,
        media_ref=MediaRef(tvdb_id=12345),
        kind=kind,
        status=status,
        enqueued_at=1_700_000_000,
        attempts=attempts,
    )


def _make_result(
    title: str = "Inception 2010 MULTi 1080p BluRay x265-GRP",
    resolution: str | None = "1080p",
    seeders: int = 50,
    info_hash: str | None = "aaaa1234",
) -> TrackerResult:
    return TrackerResult(
        provider="lacale",
        tracker_id="t1",
        title=title,
        size=ByteSize(5_000_000_000),
        seeders=seeders,
        leechers=0,
        resolution=resolution,
        info_hash=info_hash,
        download_url="https://lacale.test/torrent/1",
    )


def _make_orchestrator(
    search_outcome: SearchOutcome | None = None,
    torrent_source: TorrentSource | None = None,
    add_return: str = "aaaa1234",
    mark_grabbed_side_effect: Exception | None = None,
    followed_series=None,
) -> tuple[GrabOrchestrator, MagicMock, MagicMock, MagicMock]:
    """Build a GrabOrchestrator with mocked dependencies.

    Returns (orchestrator, mock_registry, mock_torrent_client, mock_store).
    """
    result = _make_result()
    if search_outcome is None:
        search_outcome = SearchOutcome(
            results=[result],
            trackers_queried=1,
            trackers_errored=0,
        )

    mock_registry = MagicMock()
    mock_registry.search_candidates.return_value = search_outcome

    mock_transport = MagicMock()
    mock_transports = {"lacale": mock_transport}
    mock_registry.transports.return_value = mock_transports

    if torrent_source is None:
        torrent_source = MagicMock(spec=TorrentSource)
        torrent_source.info_hash = add_return

    mock_torrent_client = MagicMock()
    mock_torrent_client.add.return_value = add_return

    mock_wanted_store = MagicMock()
    mock_wanted_store.mark_grabbed.side_effect = mark_grabbed_side_effect

    mock_follow_store = MagicMock()
    mock_follow_store.get.return_value = followed_series

    mock_store = MagicMock()
    mock_store.wanted = mock_wanted_store
    mock_store.follow = mock_follow_store

    mock_event_bus = MagicMock()
    ranking = RankingConfig(
        min_seeders=0,
        criteria=[],
        bonuses=MagicMock(freeleech=0, silverleech=0),
    )

    orchestrator = GrabOrchestrator(
        tracker_registry=mock_registry,
        torrent_client=mock_torrent_client,
        store=mock_store,
        event_bus=mock_event_bus,
        ranking=ranking,
    )
    return orchestrator, mock_registry, mock_torrent_client, mock_store


def test_grab_happy_path_emits_grab_succeeded() -> None:
    """GOLDEN: fetch+add → mark_grabbed + exact GrabSucceeded payload."""
    orchestrator, mock_registry, mock_torrent_client, mock_store = _make_orchestrator()

    with patch("personalscraper.acquire.orchestrator.resolve_source") as mock_resolve:
        mock_source = MagicMock(spec=TorrentSource)
        mock_resolve.return_value = mock_source
        mock_torrent_client.add.return_value = "aaaa1234"

        item = _make_wanted()
        outcome = orchestrator.grab(item, QualityProfile())

    assert outcome.grabbed is True
    assert outcome.info_hash == "aaaa1234"
    assert outcome.event_emitted == "GrabSucceeded"

    # mark_grabbed must be called with the item id + info_hash
    mock_store.wanted.mark_grabbed.assert_called_once_with(42, "aaaa1234")

    # GrabSucceeded event emitted
    emitted_events = [call.args[0] for call in mock_store._mock_children.get("emit", MagicMock()).call_args_list]
    # Check via event_bus
    orchestrator._event_bus.emit.assert_called()
    emit_call = orchestrator._event_bus.emit.call_args[0][0]
    assert isinstance(emit_call, GrabSucceeded)
    assert emit_call.info_hash == "aaaa1234"
    assert emit_call.source_tracker == "lacale"
```

- [ ] **Step 2: Run to verify fails**

```bash
python -m pytest tests/acquire/test_orchestrator.py::test_grab_happy_path_emits_grab_succeeded -v
```

Expected: `AttributeError` — `GrabOrchestrator` not defined yet.

- [ ] **Step 3: Implement `GrabOrchestrator` with full §1 chain**

```python
class GrabOrchestrator:
    """Single-item grab chain (§1 of DESIGN).

    Executes claim → profile → search → hard-filter → dedup → rank →
    resolve_source → add → mark_grabbed → emit for ONE ``WantedItem``.

    Deps injected at construction (NOT AppContext — boundary rule).

    Attributes:
        _tracker_registry: Multi-tracker search provider.
        _torrent_client: Active ``TorrentAdder`` implementation.
        _store: ``AcquireStore`` for status transitions.
        _event_bus: In-process event bus (fire-and-forget).
        _ranking: Ranking configuration for soft-scoring.
    """

    def __init__(
        self,
        *,
        tracker_registry: "TrackerRegistry",
        torrent_client: "TorrentAdder",
        store: "AcquireStore",
        event_bus: "EventBus",
        ranking: RankingConfig,
    ) -> None:
        """Initialise the orchestrator with injected narrow deps.

        Args:
            tracker_registry: Multi-tracker search coordinator.
            torrent_client: Torrent add capability.
            store: Acquire store for status writes.
            event_bus: In-process event bus.
            ranking: Ranking configuration.
        """
        self._tracker_registry = tracker_registry
        self._torrent_client = torrent_client
        self._store = store
        self._event_bus = event_bus
        self._ranking = ranking

    def _resolve_profile(self, item: "WantedItem") -> QualityProfile:
        """Resolve effective QualityProfile for *item*.

        Merges ``FollowedSeries.quality_profile_json`` (series default) with
        ``WantedItem.criteria_json`` (per-item override) via
        :func:`~personalscraper.acquire.desired.effective_quality`.

        Falls back to the permissive ``QualityProfile()`` when no series or
        criteria JSON is present.

        Args:
            item: The wanted item being grabbed.

        Returns:
            The effective :class:`QualityProfile` for this grab.
        """
        from personalscraper.acquire.desired import (  # noqa: PLC0415
            SourceCriteria,
            source_criteria_from_json,
        )
        from personalscraper.acquire.desired import (  # noqa: PLC0415
            quality_profile_from_json,
        )

        series_profile = QualityProfile()
        if item.followed_id is not None:
            followed = self._store.follow.get(item.followed_id)
            if followed and followed.quality_profile_json:
                series_profile = quality_profile_from_json(followed.quality_profile_json)

        item_criteria = SourceCriteria()
        if item.criteria_json:
            item_criteria = source_criteria_from_json(item.criteria_json)

        return effective_quality(series_profile, item_criteria)

    def grab(self, item: "WantedItem", profile: QualityProfile | None = None) -> GrabOutcome:
        """Execute the full grab chain for one claimed WantedItem.

        The item must already be in ``status='searching'`` (claimed by
        ``AcquisitionService.claim_for_search``).

        Failure routing (§6.2):
        - RETRYABLE  → ``searching → pending``, emit ``GrabFailed``
        - TERMINAL   → ``searching → abandoned``, emit ``WantedAbandoned``

        ``CircuitOpenError`` is caught SEPARATELY from ``ApiError`` because
        they are siblings in the exception hierarchy (not subtype), and
        conflating them would silently swallow circuit-open signals.

        Args:
            item: The claimed ``WantedItem`` (must have ``item.id`` set).
            profile: Pre-resolved :class:`QualityProfile` (optional; if
                ``None`` the orchestrator resolves it from the store).

        Returns:
            :class:`GrabOutcome` describing the result.
        """
        assert item.id is not None, "item.id must be set — call list_pending() which SELECTs id"  # noqa: S101

        effective_profile = profile if profile is not None else self._resolve_profile(item)
        media_type = MediaType.TV if item.kind == "episode" else MediaType.MOVIE
        query = item.media_ref.tvdb_id or str(item.media_ref.tmdb_id or "")
        year: int | None = None  # year resolution is a Follow D3 concern

        # --- Search ---
        try:
            outcome: SearchOutcome = self._tracker_registry.search_candidates(
                query, media_type, year
            )
        except CircuitOpenError:
            return self._retryable(item, "circuit_open")
        except ApiError:
            return self._retryable(item, "search_api_error")

        if outcome.all_errored:
            return self._retryable(item, "trackers_unavailable")

        if not outcome.results:
            return self._terminal(item, "no_candidates")

        # --- Hard-filter (BEFORE dedup — DESIGN §15) ---
        filtered = apply_hard_filters(outcome.results, effective_profile)
        if not filtered:
            return self._terminal(item, "all_filtered")

        # --- Dedup ---
        deduped = dedup(filtered)

        # --- Rank + pick top ---
        ranked = rank(deduped, self._ranking)
        if not ranked:
            return self._terminal(item, "no_candidates_after_rank")
        top_result, _score = ranked[0]

        # --- Resolve source (fetch .torrent) ---
        transports = self._tracker_registry.transports()
        try:
            source = resolve_source(top_result, transports)
        except Exception as exc:  # noqa: BLE001
            from personalscraper.api.tracker._errors import TrackerAuthError  # noqa: PLC0415
            if isinstance(exc, TrackerAuthError):
                return self._terminal(item, f"auth_failed:{top_result.provider}")
            return self._retryable(item, f"fetch_failed:{type(exc).__name__}")

        # --- Add torrent ---
        try:
            info_hash = self._torrent_client.add(
                source,
                category=None,
                tags=(top_result.provider,),
            )
        except CircuitOpenError:
            return self._retryable(item, "add_circuit_open")
        except ApiError as exc:
            # 409 Conflict = already present (idempotent) → treat as success
            if exc.http_status == 409:
                info_hash = top_result.info_hash or ""
            else:
                return self._retryable(item, f"add_api_error:{exc.http_status}")

        # --- Persist + emit ---
        try:
            self._store.wanted.mark_grabbed(item.id, info_hash)
        except sqlite3.OperationalError:
            # DB lock: RETRYABLE — the torrent is added, hash will guard re-run
            return self._retryable(item, "db_lock_on_mark_grabbed")

        event = GrabSucceeded(
            media_ref=item.media_ref,
            info_hash=info_hash,
            source_tracker=top_result.provider,
            category=None,
            tags=(top_result.provider,),
        )
        self._event_bus.emit(event)

        log.info(
            "acquire.grab.succeeded",
            wanted_id=item.id,
            info_hash=info_hash,
            provider=top_result.provider,
        )
        return GrabOutcome(grabbed=True, info_hash=info_hash, event_emitted="GrabSucceeded")

    def _retryable(self, item: "WantedItem", reason: str) -> GrabOutcome:
        """Transition item searching→pending and emit GrabFailed (RETRYABLE).

        Args:
            item: The claimed item to reset.
            reason: Machine-readable failure reason.

        Returns:
            :class:`GrabOutcome` with ``grabbed=False``.
        """
        self._store.wanted.set_status(item.id, "pending")
        event = GrabFailed(
            media_ref=item.media_ref,
            source_tracker=None,
            reason=reason,
        )
        self._event_bus.emit(event)
        log.warning("acquire.grab.retryable", wanted_id=item.id, reason=reason)
        return GrabOutcome(grabbed=False, event_emitted="GrabFailed", reason=reason)

    def _terminal(self, item: "WantedItem", reason: str) -> GrabOutcome:
        """Transition item searching→abandoned and emit WantedAbandoned (TERMINAL).

        Args:
            item: The claimed item to abandon.
            reason: Machine-readable abandonment reason.

        Returns:
            :class:`GrabOutcome` with ``grabbed=False``.
        """
        self._store.wanted.set_status(item.id, "abandoned")
        event = WantedAbandoned(media_ref=item.media_ref, reason=reason)
        self._event_bus.emit(event)
        log.warning("acquire.grab.terminal", wanted_id=item.id, reason=reason)
        return GrabOutcome(grabbed=False, event_emitted="WantedAbandoned", reason=reason)


__all__ = ["GrabOrchestrator", "GrabOutcome", "MAX_ATTEMPTS"]
```

Also add `import sqlite3` at the top of `orchestrator.py`.

- [ ] **Step 4: Run happy path test**

```bash
python -m pytest tests/acquire/test_orchestrator.py::test_grab_happy_path_emits_grab_succeeded -v
```

Expected: PASSED.

- [ ] **Step 5: Commit**

```bash
git add personalscraper/acquire/orchestrator.py tests/acquire/test_orchestrator.py
git commit -m "feat(grab-core): GrabOrchestrator full §1 chain + happy path golden"
```

---

## Task 3: Adversarial tests — failure taxonomy + NEGATIVE seed-write assert

**Files:**

- Modify: `tests/acquire/test_orchestrator.py`

> **LOAD-BEARING TESTS:** The NEGATIVE seed-write assert (`seed.add call_count==0`) and
> the `CircuitOpenError` separate-catch test are explicitly required by DESIGN §11.

- [ ] **Step 1: Write the adversarial tests**

```python
# Add to tests/acquire/test_orchestrator.py
from personalscraper.api.tracker._errors import TrackerAuthError


def test_all_trackers_errored_retryable_grab_failed() -> None:
    """DESIGN §6.2: all trackers errored → RETRYABLE GrabFailed('trackers_unavailable')."""
    all_error_outcome = SearchOutcome(
        results=[], trackers_queried=2, trackers_errored=2
    )
    orchestrator, _, _, mock_store = _make_orchestrator(search_outcome=all_error_outcome)
    item = _make_wanted()
    outcome = orchestrator.grab(item, QualityProfile())
    assert not outcome.grabbed
    assert outcome.event_emitted == "GrabFailed"
    assert outcome.reason == "trackers_unavailable"
    # Row must be reset to pending (retryable)
    mock_store.wanted.set_status.assert_called_once_with(42, "pending")


def test_all_filtered_terminal_wanted_abandoned() -> None:
    """Zero survivors after hard-filter → TERMINAL WantedAbandoned('all_filtered')."""
    # Profile requires 2160p; result is 720p
    from personalscraper.acquire.desired import Resolution
    strict_profile = QualityProfile(min_resolution=Resolution.R2160P)
    result_720p = _make_result(resolution="720p")
    outcome_720p = SearchOutcome(results=[result_720p], trackers_queried=1, trackers_errored=0)
    orchestrator, _, _, mock_store = _make_orchestrator(search_outcome=outcome_720p)
    item = _make_wanted()
    outcome = orchestrator.grab(item, strict_profile)
    assert not outcome.grabbed
    assert outcome.event_emitted == "WantedAbandoned"
    assert outcome.reason == "all_filtered"
    mock_store.wanted.set_status.assert_called_once_with(42, "abandoned")


def test_auth_fail_terminal_wanted_abandoned() -> None:
    """TrackerAuthError on resolve_source → TERMINAL WantedAbandoned."""
    orchestrator, _, _, mock_store = _make_orchestrator()
    item = _make_wanted()
    with patch("personalscraper.acquire.orchestrator.resolve_source") as mock_resolve:
        mock_resolve.side_effect = TrackerAuthError(
            provider="lacale", http_status=403, message="forbidden"
        )
        outcome = orchestrator.grab(item, QualityProfile())
    assert not outcome.grabbed
    assert outcome.event_emitted == "WantedAbandoned"
    assert "auth_failed" in (outcome.reason or "")
    mock_store.wanted.set_status.assert_called_once_with(42, "abandoned")


def test_circuit_open_error_caught_separately_retryable() -> None:
    """LOAD-BEARING: CircuitOpenError on search → RETRYABLE, not a batch crash."""
    orchestrator, mock_registry, _, mock_store = _make_orchestrator()
    mock_registry.search_candidates.side_effect = CircuitOpenError("cb open")
    item = _make_wanted()
    # Must NOT raise — must return retryable outcome
    outcome = orchestrator.grab(item, QualityProfile())
    assert not outcome.grabbed
    assert outcome.event_emitted == "GrabFailed"
    assert outcome.reason == "circuit_open"
    mock_store.wanted.set_status.assert_called_once_with(42, "pending")


def test_conflict_409_on_add_treated_as_success() -> None:
    """409 Conflict (already in client) → idempotent success, not an error."""
    orchestrator, _, mock_torrent_client, mock_store = _make_orchestrator()
    mock_torrent_client.add.side_effect = ApiError(
        provider="lacale", http_status=409, message="Conflict"
    )
    item = _make_wanted()
    with patch("personalscraper.acquire.orchestrator.resolve_source"):
        outcome = orchestrator.grab(item, QualityProfile())
    assert outcome.grabbed is True
    assert outcome.event_emitted == "GrabSucceeded"


def test_negative_seed_write_assert() -> None:
    """LOAD-BEARING (DESIGN §9 + §11-g): seed.add / record_dispatch NEVER called at grab time."""
    orchestrator, _, _, mock_store = _make_orchestrator()
    item = _make_wanted()
    with patch("personalscraper.acquire.orchestrator.resolve_source"):
        orchestrator.grab(item, QualityProfile())
    # Seed sub-store must never be touched
    assert mock_store.seed.add.call_count == 0, (
        "seed.add must NOT be called at grab time — seed obligation is a dispatch concern"
    )
    # Confirm no record_dispatch call either (belt-and-suspenders)
    for call_item in mock_store.mock_calls:
        assert "record_dispatch" not in str(call_item), (
            f"record_dispatch must not be called at grab time: {call_item}"
        )


def test_db_lock_on_mark_grabbed_is_retryable() -> None:
    """OperationalError on mark_grabbed → RETRYABLE (torrent still added)."""
    import sqlite3
    orchestrator, _, _, mock_store = _make_orchestrator(
        mark_grabbed_side_effect=sqlite3.OperationalError("locked")
    )
    item = _make_wanted()
    with patch("personalscraper.acquire.orchestrator.resolve_source"):
        outcome = orchestrator.grab(item, QualityProfile())
    assert not outcome.grabbed
    assert outcome.event_emitted == "GrabFailed"
    assert "db_lock" in (outcome.reason or "")


def test_no_candidates_terminal() -> None:
    """Clean search with zero hits → TERMINAL WantedAbandoned('no_candidates')."""
    no_results = SearchOutcome(results=[], trackers_queried=1, trackers_errored=0)
    orchestrator, _, _, mock_store = _make_orchestrator(search_outcome=no_results)
    item = _make_wanted()
    outcome = orchestrator.grab(item, QualityProfile())
    assert not outcome.grabbed
    assert outcome.event_emitted == "WantedAbandoned"
    assert outcome.reason == "no_candidates"
```

- [ ] **Step 2: Run all orchestrator tests**

```bash
python -m pytest tests/acquire/test_orchestrator.py -v
```

Expected: All tests PASSED (10+).

- [ ] **Step 3: Lint + size check**

```bash
python -m ruff check personalscraper/acquire/orchestrator.py tests/acquire/test_orchestrator.py
python -m mypy personalscraper/acquire/orchestrator.py
python scripts/check-module-size.py personalscraper/acquire/orchestrator.py
```

Expected: zero errors; under 300 LOC (split with 4b keeps both under budget).

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -10
```

Expected: passing summary, no regressions.

- [ ] **Step 5: Commit phase gate**

```bash
git add personalscraper/acquire/orchestrator.py tests/acquire/test_orchestrator.py
git commit -m "feat(grab-core): adversarial failure taxonomy + NEGATIVE seed-write assert + phase 04a gate"
```
