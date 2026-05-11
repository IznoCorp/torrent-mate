# Phase 4 — Cross-cutting events

**Depends on**: Phase 3 (bus is the only emit path; pipeline emits lifecycle + ItemProgressed; subscribers in place).
**Commits expected**: **6** (one per sub-phase; 5 integration sub-phases 4.1–4.5 + 1 phase-gate commit at sub-phase 4.6).
**Goal**: Wire 5 cross-cutting components into the bus, one integration per atomic sub-phase. Each component starts emitting its declared event(s); `TelegramSubscriber` (rewritten in Phase 3) adds the new subscriptions for circuit/disk in the same sub-phase as the corresponding emit. The `event_bus: EventBus | None` optional contract is used here as a migration aid and is paid off in Phase 5.

## Scope

**In scope** (DESIGN.md §Migration / CircuitBreaker, DiskGuard, Dispatch, Trailers, Indexer integrations):

- `core/circuit.py` emits `CircuitBreakerOpened`, `CircuitBreakerClosed`, `CircuitBreakerHalfOpened`.
- `indexer/_disk_guard.py` (extracted if needed) emits `DiskFullWarning`.
- `dispatch/dispatcher.py` (+ `_movie.py`, `_tv.py`) emits `ItemDispatched`.
- `trailers/service.py` (or equivalent) emits `TrailerDownloaded`.
- `indexer/scanner/_modes/*.py` orchestrator emits `LibraryScanCompleted`.
- `TelegramSubscriber` gains `CircuitBreakerOpened` + `DiskFullWarning` subscriptions (in the relevant sub-phases).
- Each integration adds its event class, its factory, its tests, and the subscriber update — **all in the same sub-phase**.

**Out of scope**:

- Removing the `| None` from `CircuitBreaker.__init__(event_bus=...)` — Phase 5 (deliberate separation so Phase 4 stays purely additive).
- `DebugLogSubscriber` — Phase 5.
- `docs/reference/event-bus.md` — Phase 5.

---

## Sub-phase 4.1 — CircuitBreaker emits + Telegram subscription

**Files**:

- Modify: `personalscraper/core/circuit.py` — add events + emit + constructor accepts `event_bus: EventBus | None = None` and `name: str = "anonymous"`.
- Modify: every `CircuitBreaker(...)` construction site in `personalscraper/` — pass `event_bus=app.event_bus` and `name="..."`.
- Modify: `personalscraper/subscribers/telegram.py` — subscribe to `CircuitBreakerOpened` and dispatch an alert.
- Modify: `tests/fixtures/event_samples.py` — add 3 factories.
- Create: `tests/core/test_circuit_events.py`
- Modify: `tests/subscribers/test_telegram.py`

**Behavior delivered**:

`core/circuit.py` (events embedded — DESIGN budget keeps the module ≤ 350 LOC total):

```python
@dataclass(frozen=True, kw_only=True)
class CircuitBreakerOpened(Event):
    breaker: str
    failure_count: int
    last_error_class: str
    last_error_message: str

@dataclass(frozen=True, kw_only=True)
class CircuitBreakerClosed(Event):
    breaker: str

@dataclass(frozen=True, kw_only=True)
class CircuitBreakerHalfOpened(Event):
    breaker: str
```

`CircuitBreaker.__init__` gains `event_bus: EventBus | None = None` and `name: str = "anonymous"`. State-transition helpers (`_open`, `_close`, `_half_open`) emit when `event_bus is not None`. The `source` field is overridden at event construction:

```python
self._event_bus.emit(CircuitBreakerOpened(
    source=f"core.circuit.{self._name}",
    breaker=self._name,
    failure_count=self._failures,
    last_error_class=type(last_exc).__name__,
    last_error_message=str(last_exc),
))
```

ContextVar capture happens automatically at event construction — if the trip occurs inside a pipeline run, the event carries the run's `correlation_id`.

`TelegramSubscriber` gains:

```python
self._tokens.append(bus.subscribe(CircuitBreakerOpened, self.on_circuit_opened))

def on_circuit_opened(self, event: CircuitBreakerOpened) -> None:
    self._send_html(
        f"⚠️ Circuit breaker tripped: <b>{event.breaker}</b> "
        f"({event.failure_count} failures, "
        f"last: {event.last_error_class}: {event.last_error_message})"
    )
```

**Tests written**:

- `test_circuit_breaker_emits_opened_on_trip`: construct breaker with bus + name; subscribe `CollectingSubscriber(bus, CircuitBreakerOpened)`; cause N failures up to the open threshold; assert exactly one `CircuitBreakerOpened` with `breaker="tmdb"`, `failure_count=N`, `last_error_class`, `last_error_message`.
- `test_circuit_breaker_emits_closed_on_recovery`: same with `CircuitBreakerClosed`.
- `test_circuit_breaker_emits_half_opened_on_probe`: same with `CircuitBreakerHalfOpened`.
- `test_circuit_breaker_without_bus_does_not_raise`: construct with `event_bus=None`; cause trip; assert no exception.
- `test_circuit_breaker_event_source_includes_name`: collect the event; assert `event.source == "core.circuit.tmdb"`.
- `test_circuit_breaker_long_lived_singleton_captures_correlation_id`: construct breaker OUTSIDE any pipeline run; bind ContextVar to `"run-xyz"`; trigger trip; collect event; assert `event.correlation_id == "run-xyz"`. (Proves DESIGN ContextVar mechanism works for long-lived emitters.)
- `test_circuit_breaker_events_have_factories`: assert all 3 in `EVENT_SAMPLE_FACTORIES`.
- `test_circuit_breaker_events_envelope_roundtrip`: parametrized round-trip for all 3.
- `test_telegram_subscriber_alerts_on_circuit_opened`: subscribe Telegram; emit `CircuitBreakerOpened(breaker="tmdb", failure_count=5, last_error_class="TimeoutError", last_error_message="...")`; monkeypatch `_send_html`; assert one send with the rendered alert body containing `"tmdb"`, `"5"`, `"TimeoutError"`.

**Steps**:

- [ ] Write failing tests.
- [ ] Add events + factories + register in registry.
- [ ] Add `event_bus` + `name` to `CircuitBreaker.__init__`.
- [ ] Add emits at state-transition helpers.
- [ ] Update every `CircuitBreaker(...)` call site (grep first):
  ```bash
  rg 'CircuitBreaker\(' --type py personalscraper/ -l
  ```
  Pass `event_bus=...` from the constructor's caller (which has `AppContext` access at this point — Phase 2 guarantees boundaries).
- [ ] Update `TelegramSubscriber` to subscribe to `CircuitBreakerOpened`.
- [ ] Run tests → pass.
- [ ] `make check` green; `core/circuit.py` ≤ 350 LOC; `subscribers/telegram.py` ≤ 200 LOC.
- [ ] Commit: `feat(event-bus): CircuitBreaker emits state-transition events; Telegram alerts on Opened`.

---

## Sub-phase 4.2 — DiskGuard extraction + DiskFullWarning emit + Telegram subscription

**Files**:

- (Conditional) Create: `personalscraper/indexer/_disk_guard.py` — extract disk-free check from `indexer/db.py` if not already extracted by the P3 god-module-split feature.
- Create: `personalscraper/indexer/events.py` — `DiskFullWarning` + `LibraryScanCompleted` (the latter is filled out in 4.5; declare the module here, add `DiskFullWarning` only in this sub-phase).
- Modify: every caller of the disk check — pass `event_bus`.
- Modify: `personalscraper/subscribers/telegram.py` — subscribe to `DiskFullWarning`.
- Modify: `tests/fixtures/event_samples.py` — add factory.
- Create: `tests/indexer/test_disk_guard_events.py`
- Modify: `tests/subscribers/test_telegram.py`

**Behavior delivered**:

```python
# personalscraper/indexer/events.py
@dataclass(frozen=True, kw_only=True)
class DiskFullWarning(Event):
    disk_path: Path
    free_bytes: int
    threshold_bytes: int
```

DiskGuard logic: when a disk-check call discovers free space below threshold, emit `DiskFullWarning(disk_path=..., free_bytes=..., threshold_bytes=...)` if `event_bus is not None`. The `event_bus` is threaded from the AppContext-aware caller (e.g., the indexer scanner orchestrator or the dispatcher pre-flight check).

**Open question resolution** (DESIGN §Open Questions #1): if the P3 god-module-split feature has NOT landed when event-bus implementation begins, this sub-phase performs the extraction. The extraction is a single mechanical move:

1. Identify the disk-check function in `indexer/db.py`.
2. Move it to `indexer/_disk_guard.py` with no behavioral change.
3. Update imports (sweep grep for the old path).
4. THEN add the bus parameter and emit.

If P3 has landed already, skip the extraction step and only add the emit at the existing `_disk_guard.py` site.

`TelegramSubscriber` gains:

```python
self._tokens.append(bus.subscribe(DiskFullWarning, self.on_disk_full))

def on_disk_full(self, event: DiskFullWarning) -> None:
    self._send_html(
        f"🪐 Disk full warning: <code>{event.disk_path}</code> "
        f"free={event.free_bytes // 1_000_000_000}GB threshold={event.threshold_bytes // 1_000_000_000}GB"
    )
```

**Tests written**:

- `test_disk_guard_emits_warning_when_below_threshold`: monkeypatch `shutil.disk_usage` to return free < threshold; call disk-check with bus; collect `DiskFullWarning`; assert one event with correct payload.
- `test_disk_guard_does_not_emit_when_above_threshold`: monkeypatch to return free > threshold; assert zero events.
- `test_disk_guard_without_bus_does_not_raise`: pass `event_bus=None`; call with low free; assert no exception.
- `test_disk_full_warning_has_factory`.
- `test_disk_full_warning_envelope_roundtrip`.
- `test_telegram_subscriber_alerts_on_disk_full_warning`: monkeypatch send; emit event; assert send call body contains the disk path and free/threshold bytes.
- **Regression test (if extraction was performed)**: `test_disk_check_function_relocated_to_disk_guard`: import the function from its new location; assert callable.

**Steps**:

- [ ] Determine whether `_disk_guard.py` already exists; if not, perform the extraction first.
- [ ] Write failing tests.
- [ ] Add `DiskFullWarning` + factory; declare `indexer/events.py`.
- [ ] Add emit at the disk-check site.
- [ ] Thread `event_bus` from callers (indexer scanner orchestrator, dispatcher pre-flight).
- [ ] Update `TelegramSubscriber`.
- [ ] Run tests → pass.
- [ ] `make check` green; `indexer/events.py` ≤ 60 LOC; `subscribers/telegram.py` ≤ 200 LOC.
- [ ] Commit: `feat(event-bus): DiskGuard emits DiskFullWarning; Telegram alerts on it`.

---

## Sub-phase 4.3 — Dispatch emits ItemDispatched

**Files**:

- Create: `personalscraper/dispatch/events.py`
- Modify: `personalscraper/dispatch/dispatcher.py` + `_movie.py` + `_tv.py` + `_transfer.py` — emit after each successful move/merge/replace.
- Modify: `tests/fixtures/event_samples.py` — add factory.
- Create: `tests/dispatch/test_dispatch_events.py`

**Behavior delivered**:

```python
# personalscraper/dispatch/events.py
@dataclass(frozen=True, kw_only=True)
class ItemDispatched(Event):
    item: str
    target_disk: Path
    category_id: str
    action: Literal["moved", "merged", "replaced"]
```

After each successful transfer, the dispatcher emits `ItemDispatched(item=item_name, target_disk=disk_root, category_id=category_id, action="moved" | "merged" | "replaced")`.

The dispatcher receives `event_bus: EventBus` from its caller (the pipeline step). Since the pipeline step has `ctx.app.event_bus`, the wiring is mechanical.

**Tests written**:

- `test_dispatch_movie_emits_item_dispatched_moved`: stub a movie dispatch of a new item; collect; assert one event with `action="moved"`.
- `test_dispatch_movie_emits_item_dispatched_replaced`: stub a movie dispatch where the target already exists; assert `action="replaced"`.
- `test_dispatch_tv_emits_item_dispatched_merged`: stub a TV merge; assert `action="merged"`.
- `test_dispatch_dry_run_does_not_emit`: dispatch with `dry_run=True`; assert zero events. **Anchored in DESIGN.md §Event catalog Notes**: `ItemDispatched` only fires for completed transfers (real moves); the `action` field is `Literal["moved","merged","replaced"]` with no `"skipped"` value, so dry-run runs logically cannot emit.
- `test_item_dispatched_has_factory`.
- `test_item_dispatched_envelope_roundtrip`: explicitly verify `target_disk: Path` round-trips through str.
- `test_item_dispatched_action_literal_values`: parametrized over `["moved", "merged", "replaced"]`; each round-trips correctly.

**Steps**:

- [ ] Write failing tests.
- [ ] Create `dispatch/events.py`.
- [ ] Add emits in the dispatcher's per-action code paths.
- [ ] Thread `event_bus` from the dispatch step's caller.
- [ ] Run → pass.
- [ ] `make check` green; `dispatch/events.py` ≤ 50 LOC.
- [ ] Commit: `feat(event-bus): dispatcher emits ItemDispatched after successful transfers`.

---

## Sub-phase 4.4 — Trailers emit TrailerDownloaded

**Files**:

- Create: `personalscraper/trailers/events.py`
- Modify: `personalscraper/trailers/service.py` (or actual download site) — emit after successful download.
- Modify: `tests/fixtures/event_samples.py` — add factory.
- Create: `tests/trailers/test_trailer_events.py`

**Behavior delivered**:

```python
# personalscraper/trailers/events.py
@dataclass(frozen=True, kw_only=True)
class TrailerDownloaded(Event):
    media_path: Path
    trailer_path: Path
    source_url: str
```

After yt-dlp returns a successful download, emit `TrailerDownloaded(media_path=..., trailer_path=..., source_url=...)`. `source_url` comes from yt-dlp's `webpage_url` field (or equivalent).

**Tests written**:

- `test_trailers_emit_trailer_downloaded_on_success`: monkeypatch yt-dlp; trigger a download; collect; assert one event.
- `test_trailers_do_not_emit_on_failure`: monkeypatch yt-dlp to raise; assert zero events.
- `test_trailer_downloaded_has_factory`.
- `test_trailer_downloaded_envelope_roundtrip`.
- `test_trailers_emit_works_from_pipeline_step_path`: run a synthetic trailers pipeline step; assert event with correlation_id matching the run.
- `test_trailers_emit_works_from_standalone_command_path`: invoke `personalscraper trailers download` (CLI) against a fixture media; assert event with the standalone-command's own `run_id` as correlation_id.

**Steps**:

- [ ] Write failing tests.
- [ ] Create `trailers/events.py`.
- [ ] Add emit after successful download.
- [ ] Thread `event_bus` from both call sites (pipeline step + standalone command).
- [ ] Run → pass.
- [ ] `make check` green; `trailers/events.py` ≤ 30 LOC.
- [ ] Commit: `feat(event-bus): trailers service emits TrailerDownloaded after each successful fetch`.

---

## Sub-phase 4.5 — Indexer scan emits LibraryScanCompleted

**Files**:

- Modify: `personalscraper/indexer/events.py` — add `LibraryScanCompleted` (file was created in 4.2 for `DiskFullWarning`).
- Modify: `personalscraper/indexer/scanner/_modes/*.py` orchestrator — emit at end of each mode.
- Modify: `tests/fixtures/event_samples.py` — add factory.
- Create: `tests/indexer/test_scan_completed_events.py`

**Behavior delivered**:

```python
@dataclass(frozen=True, kw_only=True)
class LibraryScanCompleted(Event):
    mode: str           # "quick" | "incremental" | "enrich" | "full" | "verify" | "backfill"
    scanned: int
    errors: int
    elapsed_s: float
```

At the end of every scan mode (success or partial failure), the orchestrator emits exactly one `LibraryScanCompleted` event. On total failure (exception propagates), the orchestrator emits the event in a `finally` with `errors = scanned_total - successful` or a sentinel `errors = -1` (decide at impl time — document in commit message).

**Tests written**:

- `test_quick_scan_emits_library_scan_completed`: run quick scan against a fixture; collect; assert one event with `mode="quick"`, `scanned > 0`.
- `test_each_scan_mode_emits_its_mode_string`: parametrize over all 6 modes; assert event's `mode` matches.
- `test_scan_emits_on_partial_failure`: stub a mode where some items error; assert one event with `errors > 0`.
- `test_library_scan_completed_has_factory`.
- `test_library_scan_completed_envelope_roundtrip`.
- `test_launchd_scan_event_correlation_id_is_scan_run_id`: invoke the launchd scan entry; collect; assert `event.correlation_id` equals the `run_id` bound by the scan's AppContext bootstrap (Phase 2.5).

**Steps**:

- [ ] Write failing tests.
- [ ] Add `LibraryScanCompleted` to `indexer/events.py`.
- [ ] Add emit at end of each mode's orchestrator path.
- [ ] Thread `event_bus` if not already done in Phase 2.5.
- [ ] Run → pass.
- [ ] `make check` green; `indexer/events.py` ≤ 60 LOC total (DiskFullWarning + LibraryScanCompleted).
- [ ] Commit: `feat(event-bus): indexer scan orchestrator emits LibraryScanCompleted per mode`.

---

## Sub-phase 4.6 — Phase 4 gate

**Hard verification gate**:

1. **`make lint`** → zero.
2. **`make test`** → all pass; total grew by Phase 4 test count (~40+).
3. **`make check`** → green.
4. **Module sizes**:
   - `core/circuit.py` ≤ 350 LOC.
   - `indexer/events.py` ≤ 60.
   - `dispatch/events.py` ≤ 50.
   - `trailers/events.py` ≤ 30.
   - `subscribers/telegram.py` ≤ 200.
5. **Event catalog completeness**: every concrete event from DESIGN §Event catalog (v1) exists and is registered:
   - `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`, `StepErrored`, `ItemProgressed` (Phase 3).
   - `ItemDispatched` (Phase 4.3).
   - `CircuitBreakerOpened`, `CircuitBreakerClosed`, `CircuitBreakerHalfOpened` (Phase 4.1).
   - `DiskFullWarning` (Phase 4.2).
   - `TrailerDownloaded` (Phase 4.4).
   - `LibraryScanCompleted` (Phase 4.5).
   - Total: **13 concrete events** (does NOT include `Event` base — Phase 1 §1.6 committed to `Event.__init_subclass__` registration which fires only for subclasses).
   - Verification:
     ```bash
     python -c "from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY; names = sorted(_EVENT_CLASS_REGISTRY.keys()); assert len(names) == 13, f'expected 13 got {len(names)}: {names}'; print(names)"
     ```
     Output must list exactly these 13 names (alphabetically) and the assertion must hold.
6. **`test_every_event_has_factory` green**: factories for all 13 in `tests/fixtures/event_samples.py`.
7. **Envelope round-trip parametrized test green for all 13**.
8. **AppContext boundary test green**.
9. **Smoke imports**:
   - `python -c "import personalscraper"`.
   - `python -c "from personalscraper.events import PipelineStarted, ItemDispatched, CircuitBreakerOpened, DiskFullWarning, TrailerDownloaded, LibraryScanCompleted"`.
10. **Telegram subscriptions**: assert at the test level that `TelegramSubscriber.__init__` results in 4 subscription tokens (`PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`, `DiskFullWarning`). New regression test added in 4.2: `test_telegram_subscriber_has_four_subscriptions_after_phase4`.
11. **`event_bus | None` audit**: list every call site that still relies on the `| None` default:
    ```bash
    rg 'event_bus: EventBus \| None' --type py personalscraper/
    rg 'CircuitBreaker\(' --type py personalscraper/ | grep -v 'event_bus='
    ```
    Document the count in the gate commit message — this is the work for Phase 5.

**Steps**:

- [ ] Re-read each sub-phase 4.1–4.5; every checkbox checked.
- [ ] Run gate items 1–11; resolve red.
- [ ] Commit: `chore(event-bus): phase 4 gate — all cross-cutting events emitting`.

---

## Roll-back plan

Phase 4 is **additive**: each sub-phase introduces a new event and a new emit without changing any existing contract. Roll-back per sub-phase:

- Revert the sub-phase commit → the event class disappears, the emit disappears, the subscriber subscription disappears, the factory disappears. Other sub-phases unaffected.

The `| None` on `CircuitBreaker.__init__(event_bus=...)` is deliberately preserved through Phase 4 to make each sub-phase reversible independently. Phase 5 tightens this contract.

## Open questions left for this phase

DESIGN §Open Questions:

- **#1 (\_disk_guard.py extraction location)**: resolved in Sub-phase 4.2. If P3 hasn't landed, 4.2 performs the extraction; if it has, 4.2 builds on the extracted module.
- **#2, #3**: out of scope / resolved earlier.

No new open questions introduced by Phase 4.
