# Phase 4 — Cross-cutting events

**Depends on**: Phase 3 (bus is the only emit path; pipeline emits lifecycle + ItemProgressed; subscribers in place).
**Commits expected**: **7** — 4.1 (CircuitBreaker), 4.2a (DiskGuard extraction, conditional), 4.2b (DiskFullWarning emit + Telegram), 4.3 (Dispatch), 4.4 (Trailers), 4.5 (Indexer scan), 4.6 (phase gate).
**Rebalanced from earlier draft**: sub-phase 4.2 split into 4.2a (extract `_disk_guard.py` from `indexer/db.py` if P3 god-module-split hasn't landed; pure mechanical move, zero behavior change) + 4.2b (add the `DiskFullWarning` event, emit, and Telegram subscription). If P3 has already landed, 4.2a is a no-op (zero commits, proceed directly to 4.2b).
**Goal**: Wire 5 cross-cutting components into the bus, one integration per atomic sub-phase. Each component starts emitting its declared event(s); `TelegramSubscriber` (rewritten in Phase 3) adds the new subscriptions for circuit/disk in the same sub-phase as the corresponding emit. The `event_bus: EventBus | None` optional contract is used here as a migration aid and is paid off in Phase 5.

## Scope

**In scope** (DESIGN.md §Migration / CircuitBreaker, DiskGuard, Dispatch, Trailers, Indexer integrations):

- `core/circuit.py` emits `CircuitBreakerOpened`, `CircuitBreakerClosed`, `CircuitBreakerHalfOpened`.
- `indexer/_disk_guard.py` (extracted if needed; today `indexer/db.py::handle_disk_full`) emits `DiskFullWarning`.
- `dispatch/dispatcher.py` (+ `_movie.py`, `_tv.py`) emits `ItemDispatched`.
- `trailers/orchestrator.py` (the coordination point wrapping `personalscraper.scraper.ytdlp_downloader.YtdlpDownloader`) emits `TrailerDownloaded`. The four `trailers/cli.py` Typer entrypoints thread the bus through the orchestrator from their AppContext-aware bootstrap (Phase 2.5).
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

## Sub-phase 4.2a — Conditional extraction: locate + (if needed) extract the disk-guard function

**Conditional sub-phase** — runs IFF the disk-guard function is not already extracted into a dedicated module. The probe handles the three cases that arise depending on whether/where P3 god-module-split landed the extraction.

**Verified current state** (branch `feat/event-bus`, HEAD `dd4a055`): function `handle_disk_full` lives in `personalscraper/indexer/db.py` and `personalscraper/indexer/_disk_guard.py` does NOT exist. Today, this sub-phase IS required (case A below).

**Locator probe — run first, before any edits**:

```bash
# Step 1: find where the function lives today (regardless of file name).
rg --type py 'def handle_disk_full|def check_disk_free|def guard_disk_full|def disk_full_guard' personalscraper/indexer/

# Step 2: if Step 1 returns zero hits, broaden the search — maybe P3 renamed it:
rg --type py 'def .*disk.*(full|free|guard)' personalscraper/indexer/

# Step 3: inventory existing dedicated extraction targets:
ls personalscraper/indexer/_disk_guard.py 2>&1     # standard prep-target name
ls personalscraper/indexer/disk_guard.py 2>&1      # P3 might have used no-underscore
ls personalscraper/indexer/db/disk_guard.py 2>&1   # P3 might have used a sub-package
```

**Branch by probe result** (apply exactly one):

- **Case A — function in `indexer/db.py`, no extraction module exists**: this is today's state. Proceed with the mechanical extraction in this sub-phase (steps below).
- **Case B — function in a dedicated module under `indexer/`, regardless of name (`_disk_guard.py` / `disk_guard.py` / `db/disk_guard.py`)**: 4.2a is a NO-OP. Record the canonical path + canonical function name in the **Phase 4 disk-guard locator** block at the bottom of THIS file (see below) so 4.2b imports the right symbols. Skip to 4.2b. Document in 4.2b commit body: "4.2a no-op: disk-guard already extracted to `<path>::<function>`".
- **Case C — function does not exist under any expected name**: STOP. This means P3 (or some other refactor) renamed it in a way the locator doesn't recognize. Do NOT guess. Surface as a BLOCKER requiring human triage; add a one-paragraph note to the PR description and pause `/implement:feature` for the user to update the locator probe with the correct name. The plan is intentionally fail-loud here — silent guessing produces a broken 4.2b.

**Files** (Case A only — the active path today):

- Create: `personalscraper/indexer/_disk_guard.py` — receives the moved code.
- Modify: `personalscraper/indexer/db.py` — remove the function body. If any external caller imports `handle_disk_full` from `indexer.db`, leave a deprecated re-export `from ._disk_guard import handle_disk_full` for ONE sub-phase only, removed by Phase 5.2 with a sweep grep. (Verify via the pre-flight grep below; if zero external callers, do NOT add a re-export.)
- Modify: every caller of `handle_disk_full` — update import path:
  ```bash
  rg --type py 'handle_disk_full' personalscraper/ tests/ -l
  rg --type py 'from personalscraper\.indexer\.db import .*handle_disk_full' personalscraper/ tests/
  ```

**Behavior delivered**: pure mechanical move. ZERO behavior change. The disk-check function executes identically before and after; only its import path changes.

**Tests written** (Case A):

- `test_handle_disk_full_lives_in_disk_guard_module`: assert `from personalscraper.indexer._disk_guard import handle_disk_full` works and the function is callable.
- All existing tests around disk-full handling continue passing without modification beyond import-path updates.

**Steps**:

- [ ] Run the locator probe (3 steps above). Determine which case applies.
- [ ] **If Case A** (today's state):
  - [ ] Pre-flight grep — enumerate callers.
  - [ ] Write the import-path assertion test.
  - [ ] Move the function to `_disk_guard.py` (no logic change).
  - [ ] Update every caller's import.
  - [ ] Run → pass (zero behavior change).
  - [ ] `make check` green.
  - [ ] Sweep grep: `rg --type py 'from personalscraper\.indexer\.db import .*handle_disk_full' personalscraper/ tests/` → 0.
  - [ ] Record the locator outcome in the "Phase 4 disk-guard locator" block at the bottom of this file (case = A, canonical path = `personalscraper/indexer/_disk_guard.py`, canonical function = `handle_disk_full`).
  - [ ] Commit: `refactor(event-bus): extract handle_disk_full from indexer/db.py into indexer/_disk_guard.py`.
- [ ] **If Case B** (already extracted by P3):
  - [ ] No commit. Record the locator outcome in the "Phase 4 disk-guard locator" block (case = B, canonical path = `<discovered>`, canonical function = `<discovered>`).
  - [ ] Proceed to 4.2b; 4.2b reads the locator block to know what to import.
- [ ] **If Case C** (function not found): STOP per the branch description above.

---

## Sub-phase 4.2b — DiskFullWarning emit + Telegram subscription

**Files**:

- Create: `personalscraper/indexer/events.py` — `DiskFullWarning` + `LibraryScanCompleted` (the latter is filled out in 4.5; declare the module here, add `DiskFullWarning` only in this sub-phase).
- Modify: the **canonical disk-guard module** identified by the "Phase 4 disk-guard locator" block at the bottom of this file (filled by 4.2a). The canonical function gains `event_bus: EventBus | None = None` and emits `DiskFullWarning` when free < threshold. **Read the locator block BEFORE editing — do not assume `_disk_guard.py` / `handle_disk_full`.**
- Modify: every caller of the canonical function (path from locator) — pass `event_bus` from the AppContext-aware bootstrap.
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

**Steps**:

- [ ] Write failing tests.
- [ ] Add `DiskFullWarning` + factory; declare `indexer/events.py`.
- [ ] Add `event_bus: EventBus | None = None` parameter to `handle_disk_full` (purely additive — 4.2a was zero-behavior-change; this is the behavior change).
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
- Modify: `personalscraper/trailers/orchestrator.py` — the coordination point that wraps `personalscraper.scraper.ytdlp_downloader.YtdlpDownloader`. Emit `TrailerDownloaded` after each successful download (verified location via `rg --type py 'YtdlpDownloader' personalscraper/trailers/` — the orchestrator is the single integration site).
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

After `YtdlpDownloader.download(...)` returns a successful download, the orchestrator emits `TrailerDownloaded(media_path=..., trailer_path=..., source_url=...)`. `source_url` comes from yt-dlp's `webpage_url` field (or the `youtube_url` already captured at the orchestrator level — verify exact attribute at impl time; `personalscraper/trailers/orchestrator.py` already tracks `youtube_url=url` at the download call sites, so the same string is available for the event).

**Tests written**:

- `test_trailers_emit_trailer_downloaded_on_success`: monkeypatch yt-dlp; trigger a download; collect; assert one event.
- `test_trailers_do_not_emit_on_failure`: monkeypatch yt-dlp to raise; assert zero events.
- `test_trailer_downloaded_has_factory`.
- `test_trailer_downloaded_envelope_roundtrip`.
- `test_trailers_emit_works_from_pipeline_step_path`: drive the production trailers step `personalscraper.trailers.step::run_trailers_step` (the in-pipeline trailers entry — verified at plan time) inside a stub pipeline that binds `current_correlation_id.set("run-pipeline-abc")` in a try/finally. Monkeypatch the `YtdlpDownloader` to return a successful download stub (no real network). Collect `TrailerDownloaded` via `CollectingSubscriber(bus, TrailerDownloaded)`. Assert: exactly one event, `event.correlation_id == "run-pipeline-abc"` (proves the ContextVar propagates from the pipeline-bound region into the step-emitted event).
- `test_trailers_emit_works_from_standalone_command_path`: invoke `personalscraper trailers download` (CLI) against a fixture media; assert event with the standalone-command's own `run_id` as correlation_id.

**Steps**:

- [ ] Write failing tests.
- [ ] Create `trailers/events.py`.
- [ ] Add emit in `trailers/orchestrator.py` after each successful `YtdlpDownloader.download` call.
- [ ] Thread `event_bus` from both call sites (in-pipeline trailers step + the four `trailers/cli.py` standalone Typer commands; the bus is already threaded at the boundaries from Phase 2.5).
- [ ] Run → pass.
- [ ] `make check` green; `trailers/events.py` ≤ 30 LOC.
- [ ] Commit: `feat(event-bus): trailers orchestrator emits TrailerDownloaded after each successful fetch`.

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

At the end of every scan mode (success or partial failure), the orchestrator emits exactly one `LibraryScanCompleted` event. On total failure (an exception propagates out of the scan body), the orchestrator emits the event in a `finally` block with:

- `scanned` = count of items processed before the exception (`scanned_total_so_far`)
- `errors` = `max(scanned_total_so_far - successful_so_far, 1)` — guarantees `errors ≥ 1` on the failure path so subscribers filtering on `errors > 0` always fire. (A scenario where the exception fires before any item is processed yields `scanned=0, successful=0, errors=1` — the "1" reflects the scan itself failing.)
- `elapsed_s` = `time.monotonic() - start` (always populated, even on failure)

**No sentinel `errors = -1`**: it would force every subscriber to special-case the negative value, and JSON consumers would have to interpret a magic number. The locked formula above keeps `errors` strictly non-negative and semantically meaningful (count of failures), at the cost of a 1-item over-count on early-exception paths — an acceptable trade documented here and reflected in the catalog docstring.

This decision is FINAL — no "decide at implementation time" remains.

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
   - Verification — **explicit set comparison** (catches missing AND extra AND `Event` accidentally registered):
     ```bash
     python -c "
     from personalscraper.core.event_bus import _EVENT_CLASS_REGISTRY
     expected = {
         'PipelineStarted', 'PipelineEnded',
         'StepStarted', 'StepCompleted', 'StepErrored',
         'ItemProgressed', 'ItemDispatched',
         'CircuitBreakerOpened', 'CircuitBreakerClosed', 'CircuitBreakerHalfOpened',
         'DiskFullWarning', 'TrailerDownloaded', 'LibraryScanCompleted',
     }
     actual = set(_EVENT_CLASS_REGISTRY)
     missing = expected - actual
     extra = actual - expected
     assert not missing and not extra, f'missing={missing} extra={extra}'
     assert 'Event' not in actual, 'Event base must not register itself (Invariant 9 / Phase 1.6 module filter)'
     print('OK 13 events:', sorted(actual))
     "
     ```
     The diagnostic names exactly what diverged; the assertion holds only when the registry is bit-for-bit the v1 catalog.
6. **`test_every_event_has_factory` green**: factories for all 13 in `tests/fixtures/event_samples.py`.
7. **Envelope round-trip parametrized test green for all 13**.
8. **AppContext boundary test green**.
9. **Smoke imports**:
   - `python -c "import personalscraper"`.
   - `python -c "from personalscraper.events import PipelineStarted, ItemDispatched, CircuitBreakerOpened, DiskFullWarning, TrailerDownloaded, LibraryScanCompleted"`.
10. **Telegram subscriptions**: assert at the test level that `TelegramSubscriber.__init__` results in 4 subscription tokens (`PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`, `DiskFullWarning`). The regression test `test_telegram_subscriber_has_four_subscriptions_after_phase4` is shipped in **sub-phase 4.2b** (the last Phase-4 sub-phase that adds a Telegram subscription — `DiskFullWarning`). Sub-phase 4.1 already shipped a 3-subscription analogue; 4.2b extends it to 4.
11. **`event_bus | None` audit**: list every call site that still relies on the `| None` default:
    ```bash
    rg 'event_bus: EventBus \| None' --type py personalscraper/
    rg 'CircuitBreaker\(' --type py personalscraper/ | grep -v 'event_bus='
    ```
    Document the count in the gate commit message — this is the work for Phase 5.

**Steps**:

- [ ] Re-read each sub-phase 4.1 / 4.2a / 4.2b / 4.3 / 4.4 / 4.5; every checkbox checked. (4.2a may have been a documented no-op if `_disk_guard.py` was already extracted by P3.)
- [ ] Run gate items 1–11; resolve red.
- [ ] Commit: `chore(event-bus): phase 4 gate — all cross-cutting events emitting`.

---

## Roll-back plan

Phase 4 is **additive**: each sub-phase introduces a new event and a new emit without changing any existing contract. Roll-back per sub-phase:

- Revert the sub-phase commit → the event class disappears, the emit disappears, the subscriber subscription disappears, the factory disappears. Other sub-phases unaffected.

The `| None` on `CircuitBreaker.__init__(event_bus=...)` is deliberately preserved through Phase 4 to make each sub-phase reversible independently. Phase 5 tightens this contract.

## Open questions left for this phase

DESIGN §Open Questions:

- **#1 (\_disk_guard.py extraction location)**: resolved by the 4.2a / 4.2b split. 4.2a conditionally performs the extraction (no-op if P3 already did it); 4.2b builds the emit on top.
- **#2, #3**: out of scope / resolved earlier.

No new open questions introduced by Phase 4.

---

## Phase 4 disk-guard locator (filled in by 4.2a)

Populated during sub-phase 4.2a Step 1 (locator probe). Sub-phase 4.2b reads this block to know which symbol to import and where to emit.

- **Case** (A / B / C — circle one when filled): `<TBD-by-4.2a>`
- **Canonical module path**: `<TBD-by-4.2a>` (e.g. `personalscraper/indexer/_disk_guard.py`)
- **Canonical function name**: `<TBD-by-4.2a>` (e.g. `handle_disk_full`)
- **Probe output excerpt** (paste the `rg` line that identified it): `<TBD-by-4.2a>`

`<TBD>` placeholders are the only "to-be-filled" markers allowed in this plan — they exist because the locator outcome depends on runtime probe; the agent in 4.2a fills them when it runs the probe. After 4.2a commits, this block is frozen for the rest of the phase.
