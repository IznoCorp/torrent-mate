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
- `test_telegram_cassette_circuit_opened` (extends `tests/subscribers/test_telegram_cassette.py` planted in Phase 3.6): register a `responses` / `requests-mock` cassette for the Telegram bot send URL; emit `CircuitBreakerOpened(...)` via `TelegramSubscriber`; assert exactly one HTTP request was made with the expected `parse_mode=HTML` body containing the breaker name, failure count, and error class. **This is the Phase-4 half of the Phase 5.6 §14 cassette-fallback for the manual smoke test** — the cassette file MUST be the same `tests/subscribers/test_telegram_cassette.py` (not a separate file), so the Phase 5.6 fallback `pytest tests/subscribers/test_telegram_cassette.py -v` exercises all 4 events in one invocation.

**Steps**:

- [x] Write failing tests.
- [x] Add events + factories + register in registry.
- [x] Add `event_bus` + `name` to `CircuitBreaker.__init__`.
- [x] Add emits at state-transition helpers.
- [x] Update every `CircuitBreaker(...)` call site (grep first):
  ```bash
  rg 'CircuitBreaker\(' --type py personalscraper/ -l
  ```
  Pass `event_bus=...` from the constructor's caller (which has `AppContext` access at this point — Phase 2 guarantees boundaries).
- [x] Update `TelegramSubscriber` to subscribe to `CircuitBreakerOpened`.
- [x] Run tests → pass.
- [x] `make check` green; `core/circuit.py` ≤ 350 LOC; `subscribers/telegram.py` ≤ 200 LOC.
- [x] Commit: `feat(event-bus): CircuitBreaker emits state-transition events; Telegram alerts on Opened`.

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

- [x] Run the locator probe (3 steps above). Determine which case applies.
- [x] **If Case A** (today's state):
  - [ ] Pre-flight grep — enumerate callers.
  - [ ] Write the import-path assertion test.
  - [ ] Move the function to `_disk_guard.py` (no logic change).
  - [ ] Update every caller's import.
  - [ ] Run → pass (zero behavior change).
  - [ ] `make check` green.
  - [ ] Sweep grep: `rg --type py 'from personalscraper\.indexer\.db import .*handle_disk_full' personalscraper/ tests/` → 0.
  - [ ] Record the locator outcome in the "Phase 4 disk-guard locator" block at the bottom of this file (case = A, canonical path = `personalscraper/indexer/_disk_guard.py`, canonical function = `handle_disk_full`).
  - [ ] Commit: `refactor(event-bus): extract handle_disk_full from indexer/db.py into indexer/_disk_guard.py`.
- [x] **If Case B** (already extracted by P3):
  - [ ] No commit. Record the locator outcome in the "Phase 4 disk-guard locator" block (case = B, canonical path = `<discovered>`, canonical function = `<discovered>`).
  - [ ] Proceed to 4.2b; 4.2b reads the locator block to know what to import.
- [x] **If Case C** (function not found): STOP per the branch description above.

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
- `test_telegram_cassette_disk_full_warning` (extends `tests/subscribers/test_telegram_cassette.py`): register a cassette for the Telegram bot send URL; emit `DiskFullWarning(disk_path=Path("/Volumes/Disk1"), free_bytes=1_000_000_000, threshold_bytes=10_000_000_000)`; assert exactly one HTTP request with `parse_mode=HTML` and a body containing the disk path and free/threshold bytes formatted as GB. **Together with the cassette tests from Phase 3.6 (PipelineEnded, StepErrored) and Phase 4.1 (CircuitBreakerOpened), this completes the 4-event cassette coverage promised by Phase 5.6 §14 fallback.**

**Steps**:

- [x] Write failing tests.
- [x] Add `DiskFullWarning` + factory; declare `indexer/events.py`.
- [x] Add `event_bus: EventBus | None = None` parameter to `handle_disk_full` (purely additive — 4.2a was zero-behavior-change; this is the behavior change).
- [x] Add emit at the disk-check site.
- [x] Thread `event_bus` from callers (indexer scanner orchestrator, dispatcher pre-flight).
- [x] Update `TelegramSubscriber`.
- [x] Run tests → pass.
- [x] `make check` green; `indexer/events.py` ≤ 60 LOC; `subscribers/telegram.py` ≤ 200 LOC.
- [x] Commit: `feat(event-bus): DiskGuard emits DiskFullWarning; Telegram alerts on it`.

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

- [x] Write failing tests.
- [x] Create `dispatch/events.py`.
- [x] Add emits in the dispatcher's per-action code paths.
- [x] Thread `event_bus` from the dispatch step's caller.
- [x] Run → pass.
- [x] `make check` green; `dispatch/events.py` ≤ 50 LOC.
- [x] Commit: `feat(event-bus): dispatcher emits ItemDispatched after successful transfers`.

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

After `YtdlpDownloader.download(...)` returns a successful download, the orchestrator emits `TrailerDownloaded(media_path=..., trailer_path=..., source_url=...)`.

**`source_url` provenance is LOCKED** (no "verify at impl time"): use the `url` variable already in scope at every download call site in `personalscraper/trailers/orchestrator.py` (the orchestrator passes `youtube_url=url` to its result records — same string, already a `str`, no transformation needed). The yt-dlp `webpage_url` field is an alternative but unnecessary since `url` is already the resolved video URL at the call site. The implementation populates `source_url=url` verbatim.

Pre-flight check (Class A — confirms the lock survives a future orchestrator refactor):

```bash
rg --type py 'youtube_url=url' personalscraper/trailers/orchestrator.py | wc -l
```

MUST return `≥ 4` (the current call-site count per `rg` against HEAD — adjust to actual count in the sub-phase commit body as `trailer_url_callsite_count: <N>`). If a future refactor renames `url`, the test below catches the regression.

**Tests written**:

- `test_trailers_emit_trailer_downloaded_on_success`: monkeypatch yt-dlp; trigger a download; collect; assert one event.
- `test_trailers_do_not_emit_on_failure`: monkeypatch yt-dlp to raise; assert zero events.
- `test_trailer_downloaded_has_factory`.
- `test_trailer_downloaded_envelope_roundtrip`.
- `test_trailers_emit_works_from_pipeline_step_path`: drive the production trailers step `personalscraper.trailers.step::run_trailers_step` (the in-pipeline trailers entry — verified at plan time) inside a stub pipeline that binds `current_correlation_id.set("run-pipeline-abc")` in a try/finally. Monkeypatch the `YtdlpDownloader` to return a successful download stub (no real network). Collect `TrailerDownloaded` via `CollectingSubscriber(bus, TrailerDownloaded)`. Assert: exactly one event, `event.correlation_id == "run-pipeline-abc"` (proves the ContextVar propagates from the pipeline-bound region into the step-emitted event).
- `test_trailers_emit_works_from_standalone_command_path`: invoke `personalscraper trailers download` (CLI) against a fixture media; assert event with the standalone-command's own `run_id` as correlation_id.

**Steps**:

- [x] Write failing tests.
- [x] Create `trailers/events.py`.
- [x] Add emit in `trailers/orchestrator.py` after each successful `YtdlpDownloader.download` call.
- [x] Thread `event_bus` from both call sites (in-pipeline trailers step + the four `trailers/cli.py` standalone Typer commands; the bus is already threaded at the boundaries from Phase 2.5).
- [x] Run → pass.
- [x] `make check` green; `trailers/events.py` ≤ 30 LOC.
- [x] Commit: `feat(event-bus): trailers orchestrator emits TrailerDownloaded after each successful fetch`.

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
- `test_scan_emits_on_partial_failure`: stub a mode where some items error during processing; assert exactly one event with `errors > 0` AND `scanned > 0` (partial = scanner reached items, some failed).
- `test_scan_emits_on_total_exception_before_any_item` (covers the `finally`-block emit path): stub a mode where the scanner raises BEFORE processing any item (e.g. config-loading exception, disk-unavailable). Allow the exception to propagate out of the orchestrator (`pytest.raises(...)`); capture `LibraryScanCompleted` via `CollectingSubscriber`; assert exactly one event with `scanned=0`, `errors=1` (the locked formula's lower bound), `elapsed_s ≥ 0`, AND `mode=<the requested mode>`. **This test guarantees the `finally`-block emit is not silently dropped on the total-exception path** — the asymmetry that earlier drafts of this plan left under-tested.
- `test_scan_emits_on_mid_scan_exception` (covers the `finally`-block emit path when the exception fires after some items): stub a mode that processes 3 items then raises on item 4; let the exception propagate; assert one event with `scanned=3`, `errors=max(3 - 3, 1) = 1` (the locked formula's lower bound). Same exception path, different progress count — verifies the formula behaves correctly on both edges.
- `test_library_scan_completed_has_factory`.
- `test_library_scan_completed_envelope_roundtrip`.
- `test_launchd_scan_event_correlation_id_is_scan_run_id`: invoke the launchd scan entry; collect; assert `event.correlation_id` equals the `run_id` bound by the scan's AppContext bootstrap (Phase 2.5).

**Anti-defer reinforcement**: if the orchestrator's existing exception-handling flow makes the `finally`-block emit awkward (e.g. the orchestrator returns multiple paths through different functions), **do NOT defer the failure-path emit to Phase 5**. Instead, refactor the orchestrator to centralize the emit in a single `finally` block within this same sub-phase. If the refactor is large (> 100 LOC), split this sub-phase into 4.5a (success + partial paths) and 4.5b (total-failure refactor + emit) — both shipped in Phase 4, never punted forward. The acceptance criterion is "every scan mode invocation emits exactly one event regardless of exit path".

**Steps**:

- [x] Write failing tests.
- [x] Add `LibraryScanCompleted` to `indexer/events.py`.
- [x] Add emit at end of each mode's orchestrator path.
- [x] Thread `event_bus` if not already done in Phase 2.5.
- [x] Run → pass.
- [x] `make check` green; `indexer/events.py` ≤ 60 LOC total (DiskFullWarning + LibraryScanCompleted).
- [x] Commit: `feat(event-bus): indexer scan orchestrator emits LibraryScanCompleted per mode`.

---

## Sub-phase 4.6 — Phase 4 gate

**Hard verification gate**:

1. **`make lint`** → zero.
2. **`make test`** → all pass; cumulative test count MUST have grown by **at least 163** new tests since the feature baseline (Phase 1 ≥ 50 raw + Phase 2 ≥ 30 + Phase 3 ≥ 50 raw net ≥ 48 after the two transitional deletions + Phase 4 ≥ 35). The Phase 4 minimum 35 is the floor of the per-sub-phase enumeration (4.1=8, 4.2b=6, 4.3=7, 4.4=6, 4.5=8 = 35); target is ~38–42 with the cassette tests in 4.1/4.2b. Test count CANNOT regress below the floor.
3. **No new skips / xfails** — per Invariant 3 item 3: `rg -c '@pytest\.mark\.(skip|xfail|skipif)' tests/ -g '*.py' | awk -F: '{s+=$2} END{print s}'` MUST equal `<SKIP_BASELINE>` from INDEX Pre-flight #9.
4. **`make check`** → green.
5. **Module sizes**:
   - `core/circuit.py` ≤ 350 LOC.
   - `indexer/events.py` ≤ 60.
   - `dispatch/events.py` ≤ 50.
   - `trailers/events.py` ≤ 30.
   - `subscribers/telegram.py` ≤ 200.
6. **Event catalog completeness**: every concrete event from DESIGN §Event catalog (v1) exists and is registered:
   - `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`, `StepErrored`, `ItemProgressed` (Phase 3).
   - `ItemDispatched` (Phase 4.3).
   - `CircuitBreakerOpened`, `CircuitBreakerClosed`, `CircuitBreakerHalfOpened` (Phase 4.1).
   - `DiskFullWarning` (Phase 4.2b).
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
7. **`test_every_event_has_factory` green**: factories for all 13 in `tests/fixtures/event_samples.py`.
8. **Envelope round-trip parametrized test green for all 13**.
9. **AppContext boundary test green**.
10. **Smoke imports**:
    - `python -c "import personalscraper"`.
    - `python -c "from personalscraper.events import PipelineStarted, ItemDispatched, CircuitBreakerOpened, DiskFullWarning, TrailerDownloaded, LibraryScanCompleted"`.
11. **Telegram subscriptions**: assert at the test level that `TelegramSubscriber.__init__` results in 4 subscription tokens (`PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`, `DiskFullWarning`). The regression test `test_telegram_subscriber_has_four_subscriptions_after_phase4` is shipped in **sub-phase 4.2b** (the last Phase-4 sub-phase that adds a Telegram subscription — `DiskFullWarning`). Sub-phase 4.1 already shipped a 3-subscription analogue; 4.2b extends it to 4.
12. **`event_bus | None` audit — count locked in commit body**: the gate commit MUST include two literal trailer lines (parseable by Phase 5.2 pre-flight via `git log -1 --format=%B`):

    ```
    event_bus_optional_sites_count: <N>
    circuit_breaker_calls_without_event_bus_count: <M>
    ```

    where `<N>` is the integer output of `rg --type py 'event_bus: EventBus \| None' personalscraper/ | wc -l` and `<M>` is the integer output of `rg --type py 'CircuitBreaker\(' personalscraper/ | grep -v 'event_bus=' | wc -l`. Phase 5.2 pre-flight greps these lines: `git log -1 --format=%B <phase-4-gate-sha> | grep -E '^(event_bus_optional_sites_count|circuit_breaker_calls_without_event_bus_count): [0-9]+$' | wc -l` MUST return `2`. Any drift in Phase 5 baseline means an undocumented `| None` site was introduced; 5.2 fails its pre-flight loudly.

**Steps**:

- [x] Re-read each sub-phase 4.1 / 4.2a / 4.2b / 4.3 / 4.4 / 4.5; every checkbox checked. (4.2a may have been a documented no-op if `_disk_guard.py` was already extracted by P3.)
- [x] Run gate items 1–12; resolve red.
- [x] Compute `<N>` and `<M>` for the audit; append the two literal trailer lines to the commit body.
- [x] Commit: `chore(event-bus): phase 4 gate — all cross-cutting events emitting`.

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

- **Case** (A / B / C — circle one when filled): **A**
- **Canonical module path**: `personalscraper/indexer/_disk_guard.py`
- **Canonical function name**: `handle_disk_full`
- **Probe output excerpt** (paste the `rg` line that identified it): `personalscraper/indexer/db.py:def handle_disk_full(conn: sqlite3.Connection, exc: sqlite3.OperationalError) -> None:`

Case A confirmed by the probe at sub-phase 4.2a runtime: `handle_disk_full` lived in `indexer/db.py` and no dedicated extraction module existed under `indexer/`. The mechanical move into `indexer/_disk_guard.py` (zero behavior change) is recorded by the 4.2a commit; sub-phase 4.2b imports from this new canonical location. The post-sweep import surface is pinned by `tests/indexer/test_disk_guard_locator.py`. After 4.2a commits, this block is frozen for the rest of the phase.
