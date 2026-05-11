# Phase 3 — Pipeline event migration + subscribers rewrite

**Depends on**: Phase 2 (AppContext + slim StepContext + bus available; observers still legacy).
**Commits expected**: **12** (one per sub-phase; sub-phase 3.12 IS the phase-gate commit).
**Goal**: Migrate the pipeline from the legacy `notify_progress(observers, …)` path to bus emit; rewrite `RichConsoleObserver` and `TelegramObserver` as bus subscribers; **delete** the entire Observer infrastructure. This is the most invasive phase — every pipeline step, every observer test, and every documentation reference is touched.

## Scope

**In scope** (DESIGN.md §Migration / Removed, §Refactored, §CLI integration, §Logging convention):

- `personalscraper/events/__init__.py` — package init + re-export registry.
- `personalscraper/pipeline/events.py` — `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`, `StepErrored`, `ItemProgressed`. (Note: `pipeline/` may already exist; if not, create `personalscraper/pipeline/__init__.py` and treat the current `pipeline.py` as `pipeline/pipeline.py`. Verify at impl time per current layout.)
- Pipeline run loop emits `PipelineStarted` / `PipelineEnded` / `StepStarted` / `StepCompleted` / `StepErrored`.
- Each of the 9 pipeline steps emits `ItemProgressed` at every legacy `notify_progress` site.
- `personalscraper/subscribers/__init__.py` package (renamed from `observers/`).
- `subscribers/rich_console.py` — `RichConsoleSubscriber` (rewrite of `RichConsoleObserver`).
- `subscribers/telegram.py` — `TelegramSubscriber` (rewrite of `TelegramObserver`; **no** circuit/disk handlers yet — those land in Phase 4 as the integrations themselves come online).
- Delete `personalscraper/pipeline_observer.py`.
- Remove `StepContext.observers` field.
- Migrate every test referencing the old API.
- Structlog dedup audit at emit sites.

**Out of scope**:

- Circuit/disk/dispatch/trailer/indexer emits — Phase 4.
- `DebugLogSubscriber` — Phase 5.
- `docs/reference/event-bus.md` — Phase 5.

---

## Phase 3 transition strategy (applies to sub-phases 3.4–3.10)

The pipeline currently emits user-visible progress through `notify_progress(ctx.observers, StepEvent(...))`. Phase 3 must migrate every site to `ctx.app.event_bus.emit(ItemProgressed(...))` WITHOUT regressing the visual output captured in the canonical baseline `tests/snapshots/rich_console_canonical.txt` (recorded in INDEX Pre-flight step 7).

**Adopted strategy: ALONGSIDE then DELETE**

- Sub-phases 3.4 / 3.5 / 3.6 / 3.7 add `event_bus.emit(ItemProgressed(...))` **alongside** the existing `notify_progress(...)` call at every site. Both paths execute. The bus emit goes to whatever subscribers exist (initially: nothing in 3.4, then `RichConsoleSubscriber` once 3.8 lands, then `TelegramSubscriber` once 3.9 lands). The legacy `notify_progress` keeps the visual output stable.
- Sub-phase 3.10 deletes EVERY `notify_progress` call, the `pipeline_observer.py` module, the `observers/` package, and the `StepContext.observers` field — in a single sweep. Bus is then the only emit path.

Rationale: the visual regression test (`tests/snapshots/rich_console_canonical.txt`) MUST stay green at every sub-phase boundary. The alongside strategy gives this guarantee because the legacy `notify_progress` → legacy `RichConsoleObserver` chain stays intact until 3.10. The cost is a brief period of "double emit" inside Phase 3 — acceptable because the bus has no console subscriber until 3.8 (no double-print), and 3.10 cleans up.

**Rejected alternative**: deleting `notify_progress` calls in 3.4-3.7 (replacing rather than adding). Rejected because steps that have been migrated would then produce silent runs until 3.8 lands `RichConsoleSubscriber` — breaking the visual regression invariant for every commit between 3.4 and 3.8.

---

## Sub-phase 3.1 — Define `pipeline/events.py` + factories + tests

**Files**:

- Create: `personalscraper/events/__init__.py` (package init; re-exports populated as events land).
- Create: `personalscraper/pipeline/events.py` (events module — keeping current `pipeline.py` location, see Scope note).
- Modify: `tests/fixtures/event_samples.py` — add 6 factories.
- Create: `tests/event_bus/test_pipeline_events.py`

**Behavior delivered**:

```python
# personalscraper/pipeline/events.py
@dataclass(frozen=True, kw_only=True)
class PipelineStarted(Event):
    report: PipelineReport

@dataclass(frozen=True, kw_only=True)
class PipelineEnded(Event):
    report: PipelineReport

@dataclass(frozen=True, kw_only=True)
class StepStarted(Event):
    step: str

@dataclass(frozen=True, kw_only=True)
class StepCompleted(Event):
    step: str
    report: StepReport
    elapsed_s: float

@dataclass(frozen=True, kw_only=True)
class StepErrored(Event):
    step: str
    error_class: str
    error_message: str

@dataclass(frozen=True, kw_only=True)
class ItemProgressed(Event):
    step: str
    item: str
    status: str
    details: dict[str, Any] = field(default_factory=dict)
```

**`kw_only=True` is the inherited convention from `Event` base** (DESIGN.md §Event base — base is also `@dataclass(frozen=True, kw_only=True)`). Python's dataclass machinery does NOT transitively enforce `kw_only`, so each subclass must declare it explicitly. With `kw_only=True`, subclasses can freely add required fields after the base's defaulted fields without triggering `TypeError: non-default argument follows default argument`. All Phase 4 events follow the same convention.

All 6 events are auto-registered in `_EVENT_CLASS_REGISTRY` via the mechanism from Sub-phase 1.6.

`tests/fixtures/event_samples.py` additions:

```python
@register_factory(PipelineStarted)
def make_pipeline_started() -> PipelineStarted:
    return PipelineStarted(report=_make_real_pipeline_report())

# ... 5 more factories with REAL data, never MagicMock
```

A small helper `_make_real_pipeline_report()` / `_make_real_step_report()` constructs valid Report instances with realistic field values (filenames that look real, counts > 0, etc.).

**Tests written**:

- `test_pipeline_events_inherit_event_base`: each class `issubclass(X, Event)`.
- `test_pipeline_events_are_frozen`: each instance rejects attribute assignment.
- `test_pipeline_events_auto_registered`: assert each class name is in `_EVENT_CLASS_REGISTRY`.
- `test_pipeline_events_have_factories`: assert each class is in `EVENT_SAMPLE_FACTORIES`.
- `test_pipeline_events_envelope_roundtrip`: for each event, `e1 = make_X()`; `e2 = event_from_envelope(json.loads(json.dumps(event_to_envelope(e1))))`; assert `e2 == e1`. **This is the gate test** that catches non-serializable Report fields.
- `test_every_event_has_factory` (test was vacuous in Phase 1; now becomes a real assertion): iterate over `_EVENT_CLASS_REGISTRY`; assert each is in `EVENT_SAMPLE_FACTORIES`.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement the 6 event classes + 6 factories.
- [ ] Run; expect the envelope round-trip test to FAIL if `PipelineReport`/`StepReport` contain a non-JSON-safe field (e.g. a callable, a Console, an enum without `.value`); FIX `models.py` / `reports/*.py` to keep all Report fields JSON-safe. **Do NOT defer the fix — Phase 3 is responsible.**
- [ ] If a regression is introduced, add a regression test in this same sub-phase (Invariant 5).
- [ ] Run → pass.
- [ ] `make check` green; `pipeline/events.py` ≤ 150 LOC; `events/__init__.py` ≤ 100 LOC (DESIGN budget).
- [ ] Commit: `feat(event-bus): add pipeline event catalog + factories + envelope round-trip`.

---

## Sub-phase 3.2 — Pipeline emits `PipelineStarted` and `PipelineEnded`

**Files**:

- Modify: `personalscraper/pipeline.py` (or `pipeline/pipeline.py` per actual layout).
- Create: `tests/pipeline/test_pipeline_lifecycle_events.py`

**Behavior delivered**:

- `Pipeline.run()` emits `PipelineStarted(report=initial_report)` immediately after binding the ContextVar.
- After all steps complete (success path), emits `PipelineEnded(report=final_report)`.
- On exception path, also emits `PipelineEnded` (with `report.has_errors() == True`) before propagating the exception. The ContextVar reset must remain in the outermost finally; the `PipelineEnded` emit is inside a separate try/except that ensures the emit runs even if a step exception propagates.

**Tests written**:

- `test_pipeline_emits_started_before_first_step`: subscribe `CollectingSubscriber(bus, PipelineStarted)`; run a no-op pipeline; assert exactly one `PipelineStarted` recorded.
- `test_pipeline_emits_ended_after_last_step`: subscribe `CollectingSubscriber(bus, PipelineEnded)`; run no-op pipeline; assert exactly one `PipelineEnded` recorded; assert `started_at <= ended.report.finished_at`.
- `test_pipeline_emits_ended_even_when_step_raises`: install a stub step that raises; expect the exception to propagate; subscribe to `PipelineEnded`; assert exactly one event recorded with `report.has_errors() == True`.
- `test_pipeline_started_carries_correlation_id`: subscribe to `PipelineStarted`; run; assert `event.correlation_id == str(pipeline.last_run_id)`.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement emits in `Pipeline.run`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): Pipeline.run emits PipelineStarted and PipelineEnded`.

---

## Sub-phase 3.3 — Pipeline emits `StepStarted`, `StepCompleted`, `StepErrored` around each step

**Files**:

- Modify: `personalscraper/pipeline.py` step loop.
- Modify: `tests/pipeline/test_pipeline_lifecycle_events.py` (add the per-step lifecycle tests).

**Behavior delivered**:

In the step loop:

```python
for step in self._steps:
    self._app.event_bus.emit(StepStarted(step=step.name))
    start = time.monotonic()
    try:
        report, extras = self._run_step(step, ctx)
    except Exception as exc:
        self._app.event_bus.emit(StepErrored(
            step=step.name,
            error_class=type(exc).__name__,
            error_message=str(exc),
        ))
        # log traceback with structlog WITH exc_info — emit carries class+message,
        # log carries the traceback. NOT duplicated info.
        log.error("pipeline_step_failed", step=step.name, exc_info=True)
        raise
    elapsed = time.monotonic() - start
    self._app.event_bus.emit(StepCompleted(
        step=step.name, report=report, elapsed_s=elapsed,
    ))
```

The legacy `notify_progress(ctx.observers, …)` for lifecycle is still wired (Phase 2 kept it). Phase 3 thus emits via BOTH paths transitionally for ONE sub-phase only: 3.5 (RichConsoleSubscriber rewrite) cuts the legacy console path; 3.6 (Telegram rewrite) cuts the legacy Telegram path; 3.9 deletes `pipeline_observer.py`. Inside this sub-phase, double-emit is acceptable to keep the visual regression test green; it is paid off within Phase 3.

**Tests written**:

- `test_pipeline_emits_step_started_before_each_step`: subscribe `CollectingSubscriber(bus, StepStarted)`; run with N steps; assert exactly N events in step order.
- `test_pipeline_emits_step_completed_after_each_successful_step`: same with `StepCompleted`; assert N events; assert `elapsed_s > 0`; assert `report` field is the step's actual `StepReport`.
- `test_pipeline_emits_step_errored_on_step_exception`: stub step raises `ValueError("boom")`; expect propagation; subscribe to `StepErrored`; assert one event with `error_class="ValueError"`, `error_message="boom"`.
- `test_pipeline_step_lifecycle_ordering`: subscribe to `Event` (base); run no-op pipeline; assert ordered: `PipelineStarted`, then for each step `StepStarted, StepCompleted`, then `PipelineEnded`.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement step lifecycle emits.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): Pipeline emits StepStarted/Completed/Errored around each step`.

---

## Sub-phase 3.4 — Step emit migration, group A: ingest + sort

**Files**:

- Modify: `personalscraper/ingest/*.py` (or `personalscraper/pipeline_steps.py` for the step adapter; verify which file holds the `notify_progress` calls for each step).
- Modify: `personalscraper/sort/*.py` (or equivalent).
- Modify: tests under `tests/ingest/`, `tests/sort/`.

**Behavior delivered** (per Phase 3 transition strategy — see top of this file):

At every `notify_progress(ctx.observers, StepEvent(step="ingest", item=…, status=…, details=…))` call site, **ADD** `ctx.app.event_bus.emit(ItemProgressed(step="ingest", item=…, status=…, details=…))` alongside. The legacy `notify_progress` call stays in place — it is removed in 3.10 along with the rest of the legacy API.

This keeps the visual regression baseline (`tests/snapshots/rich_console_canonical.txt`) green at every sub-phase boundary: the legacy `notify_progress` → `RichConsoleObserver` chain remains intact until 3.10. The bus emit goes to no console subscriber until 3.8 lands `RichConsoleSubscriber`, so no double-print risk.

**Tests written**:

- `test_ingest_emits_item_progressed_per_item`: run ingest against a fixture with 3 items; collect `ItemProgressed`; assert 3 events for `step="ingest"` with the expected `status` values.
- `test_sort_emits_item_progressed_per_item`: same for sort.
- `test_ingest_item_progressed_details_payload_is_json_safe`: collect an `ItemProgressed` from ingest; call `event_to_dict(event)`; assert no `TypeError`. (Forces ingest to only put JSON-safe values in `details`.)
- `test_sort_item_progressed_details_payload_is_json_safe`: same for sort.

**Steps**:

- [ ] Write failing tests.
- [ ] Grep ingest + sort for `notify_progress`; produce the migration list.
- [ ] At each site, ADD `ctx.app.event_bus.emit(ItemProgressed(...))` alongside the existing `notify_progress` call per the Phase 3 transition strategy at the top of this file. Do NOT delete the legacy call — 3.10 handles that.
- [ ] Run tests → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): ingest + sort emit ItemProgressed via bus`.

---

## Sub-phase 3.5 — Step emit migration, group B: clean + scrape

**Files**:

- Modify: `personalscraper/process/*.py` (clean step) — verify layout.
- Modify: `personalscraper/scraper/*.py` (scrape step).
- Modify: tests under `tests/process/`, `tests/scraper/`.

**Behavior delivered** (per Phase 3 transition strategy — see top of this file): ADD `ctx.app.event_bus.emit(ItemProgressed(...))` alongside every `notify_progress(ctx.observers, StepEvent(step="clean"|"scrape", ...))` call for clean + scrape. Tests written follow the same template as 3.4, expanded for the larger detail payloads of `scrape` (provider, confidence, fallback flag — all must be JSON-safe).

**Tests written**:

- `test_clean_emits_item_progressed_per_item`.
- `test_scrape_emits_item_progressed_per_item`.
- `test_scrape_item_progressed_includes_provider_and_confidence_in_details`: collect scrape events; assert `details` contains `"provider"` and `"confidence"` keys with str / float values.
- `test_clean_item_progressed_details_json_safe`.
- `test_scrape_item_progressed_details_json_safe`.

**Steps**:

- [ ] Write failing tests.
- [ ] Migrate the call sites alongside-style — ADD bus emit, keep `notify_progress` intact (per Phase 3 transition strategy).
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): clean + scrape emit ItemProgressed via bus`.

---

## Sub-phase 3.6 — Step emit migration, group C: cleanup + enforce + verify

**Files**: cleanup, enforce, verify step modules + tests.

**Behavior delivered** (per Phase 3 transition strategy — see top of this file): ADD `ctx.app.event_bus.emit(ItemProgressed(...))` alongside every `notify_progress(...)` call for cleanup + enforce + verify. Verify step emits per-check events; this aligns with the future P2 Verify Checker Plugin System but does NOT pre-implement plugins (each existing check group emits one `ItemProgressed` per item it processes — DESIGN catalog covers this with the existing payload shape).

**Tests written**:

- `test_cleanup_emits_item_progressed_per_item`.
- `test_enforce_emits_item_progressed_per_item`.
- `test_verify_emits_item_progressed_per_item`.
- `test_verify_item_progressed_details_includes_check_category`: collect verify events; assert `details["check_category"]` exists.
- JSON-safe assertions for each.

**Steps**:

- [ ] Write failing tests.
- [ ] Migrate call sites.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): cleanup + enforce + verify emit ItemProgressed via bus`.

---

## Sub-phase 3.7 — Step emit migration, group D: trailers + dispatch

**Files**: trailers step (within pipeline), dispatch step + tests.

**Behavior delivered** (per Phase 3 transition strategy — see top of this file): ADD `ctx.app.event_bus.emit(ItemProgressed(...))` alongside every `notify_progress(...)` call for trailers + dispatch. Trailers step emits `ItemProgressed` per trailer attempt; dispatch emits `ItemProgressed` per dispatched item. Note: `ItemDispatched` (the dispatch outcome event from `dispatch/events.py`) is **Phase 4** — Phase 3 only adds the `ItemProgressed` emit at the existing `notify_progress` sites.

**Tests written**:

- `test_trailers_step_emits_item_progressed`.
- `test_dispatch_step_emits_item_progressed`.
- JSON-safe assertions.

**Steps**:

- [ ] Write failing tests.
- [ ] Migrate call sites.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Sweep grep: `rg 'notify_progress\(' --type py personalscraper/` — must still show every original call site (kept alongside bus emit per the Phase 3 transition strategy at the top of this file). Document the count in the commit message for Phase 3 gate audit reference; 3.10 will verify this count drops to zero.
- [ ] Commit: `feat(event-bus): trailers + dispatch steps emit ItemProgressed via bus`.

---

## Sub-phase 3.8 — Rewrite `RichConsoleObserver` → `RichConsoleSubscriber`

**Files**:

- Rename: `personalscraper/observers/rich_console.py` → `personalscraper/subscribers/rich_console.py` (note: this rename happens once, here, for this file; the `observers/` → `subscribers/` package-level rename is Sub-phase 3.10 once all observers have been rewritten).
- Create: `personalscraper/subscribers/__init__.py` (new package).
- Modify: `personalscraper/cli.py` to import `RichConsoleSubscriber` from new location AND register it on the bus instead of passing as an observer.
- Modify: tests for the Rich console output.

**Behavior delivered**:

- `RichConsoleSubscriber(bus: EventBus, console: Console)`:
  - In `__init__`, subscribes itself to `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`, `StepErrored`, `ItemProgressed`. Stores tokens.
  - Each `on_<event>` handler reproduces the visual behavior of the legacy `RichConsoleObserver`'s corresponding callback (bytes-identical rendering for the canonical snapshot test).
  - `close()` unsubscribes all tokens (clean teardown for tests).
- CLI bootstrap (`cli.py`): instead of `observers = (RichConsoleObserver(console), …)` + `Pipeline(..., observers=observers)`, do `RichConsoleSubscriber(app.event_bus, console)` (constructor self-subscribes). The legacy `RichConsoleObserver` is still imported and threaded via `StepContext.observers` until 3.9 deletes the legacy path entirely.

**Tests written**:

- `test_rich_console_subscriber_subscribes_on_init`: instantiate; assert 6 subscription tokens stored.
- `test_rich_console_subscriber_close_unsubscribes_all`: instantiate; close; assert bus dispatches an `ItemProgressed` to zero subscribers afterwards.
- `test_rich_console_subscriber_snapshot_matches_baseline`: **the visual regression lock**. Use the determinism setup `Console(width=120, color_system=None, force_terminal=False, file=StringIO(), record=True)`. Run the canonical pipeline against `RichConsoleSubscriber` wrapping this console; capture `console.export_text()`; compare against the **immutable baseline** at `tests/snapshots/rich_console_canonical.txt` (recorded once in INDEX Pre-flight step 7 by running the LEGACY `RichConsoleObserver` against the same canonical pipeline, pre-Phase-1). The baseline is byte-identical to what the legacy observer produced; this test asserts the new subscriber matches that bytes-identical output. **Never re-record the baseline inside Phase 3** — if it needs adjustment, the entire feature is invalid.
- `test_rich_console_subscriber_outputs_match_legacy_observer_for_canonical_run`: same as the snapshot, but performed in-process by running BOTH the legacy `RichConsoleObserver` and the new `RichConsoleSubscriber` against the same emit sequence and comparing their recorded outputs directly. **This test is DELETED in Sub-phase 3.10** when the legacy observer is removed. Mark with a `# TODO(3.10): delete this test when RichConsoleObserver is removed` comment.

**Steps**:

- [ ] Write failing tests including the legacy/new comparison test.
- [ ] Implement `RichConsoleSubscriber` mirroring `RichConsoleObserver`'s rendering logic.
- [ ] Assert against the pre-existing baseline at `tests/snapshots/rich_console_canonical.txt` (recorded during INDEX Pre-flight step 7). **Do NOT re-record** — the baseline is immutable.
- [ ] **Smoke import check** (catches circular import during the transition where `observers/` and `subscribers/` coexist): `python -c "import personalscraper.observers; import personalscraper.subscribers; print('ok')"` → prints `ok`.
- [ ] Run → pass.
- [ ] `make check` green; `subscribers/rich_console.py` ≈ 180 LOC (DESIGN budget).
- [ ] Commit: `refactor(event-bus): rewrite RichConsoleObserver as RichConsoleSubscriber on the bus`.

---

## Sub-phase 3.9 — Rewrite `TelegramObserver` → `TelegramSubscriber`

**Files**:

- Move: `personalscraper/observers/telegram.py` → `personalscraper/subscribers/telegram.py`.
- Modify: CLI bootstrap to instantiate `TelegramSubscriber(app.event_bus, creds)` when creds present.
- Modify: tests for Telegram alerting.

**Behavior delivered**:

- `TelegramSubscriber(bus, creds)`:
  - In `__init__`, subscribes to `PipelineEnded` and `StepErrored`. **NOT yet** `CircuitBreakerOpened` / `DiskFullWarning` — Phase 4 adds the subscriptions in the same sub-phase that introduces those events.
  - `on_pipeline_ended` formats and sends the HTML summary (reuses `PipelineReport.to_html()`).
  - `on_step_errored` sends an alert mentioning the step name + error class + error message.
- Phase 4 will REVISIT this subscriber to add the cross-cutting subscriptions; that is Phase 4's job, not Phase 3's.

**Tests written**:

- `test_telegram_subscriber_subscribes_to_pipeline_ended_and_step_errored`: assert 2 tokens.
- `test_telegram_subscriber_sends_html_on_pipeline_ended`: monkeypatch the HTTP send function; emit a `PipelineEnded` event; assert one send call with `parse_mode="HTML"` and the rendered body.
- `test_telegram_subscriber_alerts_on_step_errored`: emit a `StepErrored(step="scrape", error_class="ValueError", error_message="boom")`; assert one send call with body containing `"scrape"` and `"ValueError"` and `"boom"`.
- `test_telegram_subscriber_close_unsubscribes`: as in 3.8.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `TelegramSubscriber`.
- [ ] **Smoke import check** (same rationale as 3.8): `python -c "import personalscraper.observers; import personalscraper.subscribers; print('ok')"` → prints `ok`.
- [ ] Run → pass.
- [ ] `make check` green; `subscribers/telegram.py` at this point holds 2 handlers (≈ 100 LOC); the 200 LOC cap is the END-of-Phase-4 budget after circuit + disk handlers are added in 4.1 and 4.2.
- [ ] Commit: `refactor(event-bus): rewrite TelegramObserver as TelegramSubscriber`.

---

## Sub-phase 3.10 — Delete legacy Observer infrastructure + remove `StepContext.observers`

**Files**:

- Delete: `personalscraper/pipeline_observer.py`.
- Delete: `personalscraper/observers/__init__.py` and any remaining files in `personalscraper/observers/` (rich_console.py and telegram.py were moved in 3.8/3.9).
- Modify: `personalscraper/pipeline_protocol.py` — remove `observers: tuple[...]` field from `StepContext`.
- Modify: `personalscraper/pipeline.py` — remove the `observers` argument from `StepContext` construction.
- Modify: every `notify_progress(ctx.observers, …)` call site in `personalscraper/` — DELETE the legacy call entirely (the bus emit added in 3.4–3.7 takes over).
- Modify: every test that references `PipelineObserver`, `CollectorObserver`, `notify_progress`, `StepEvent`, or `from personalscraper.observers` — migrate to `EventBus` + `CollectingSubscriber`.
- Delete: the `test_step_context_still_has_observers_phase2` test from Phase 2.2.
- Delete: the `test_rich_console_subscriber_outputs_match_legacy_observer_for_canonical_run` test (legacy is gone).

**Behavior delivered**: the legacy API ceases to exist. The bus is the only emit path.

**Tests written**:

- `test_step_context_does_not_have_observers_attribute`: build `StepContext`; assert `not hasattr(ctx, "observers")`. (This replaces the Phase 2 test that asserted the opposite.)
- All migrated tests previously asserting on `CollectorObserver` now assert on `CollectingSubscriber[E]`.

**Steps**:

- [ ] List every test file that imports from `personalscraper.observers` or `personalscraper.pipeline_observer`:
  ```bash
  rg -l 'personalscraper\.(observers|pipeline_observer)' --type py tests/
  ```
- [ ] For each file: rewrite imports to `personalscraper.subscribers` and `personalscraper.core.event_bus`; rewrite `CollectorObserver(...)` to `CollectingSubscriber(bus, EventType)`; rewrite `StepEvent(...)` to `ItemProgressed(...)`.
- [ ] Delete `pipeline_observer.py`.
- [ ] Delete `observers/__init__.py`.
- [ ] Remove `StepContext.observers` field.
- [ ] Remove every `notify_progress(ctx.observers, …)` call in production code.
- [ ] Update `docs/reference/pipeline-internals.md` and any other docs that mention the legacy API.
- [ ] Run tests → all green.
- [ ] **Sweep greps** (must ALL return zero):
  - `rg 'from personalscraper\.observers' --type py personalscraper/ tests/` → 0.
  - `rg 'from personalscraper\.pipeline_observer' --type py personalscraper/ tests/` → 0.
  - `rg 'PipelineObserver\b' --type py personalscraper/ tests/` → 0.
  - `rg 'PipelineObserverBase\b' --type py personalscraper/ tests/` → 0.
  - `rg 'CollectorObserver\b' --type py personalscraper/ tests/` → 0.
  - `rg 'notify_progress\(' --type py personalscraper/ tests/` → 0.
  - `rg '\bStepEvent\b' --type py personalscraper/ tests/` → 0.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): delete pipeline_observer.py and StepContext.observers; bus is the only emit path`.

---

## Sub-phase 3.11 — Structlog dedup audit at emit sites

**Files**:

- Modify: any emit site found to also call `structlog` with duplicate information.
- Modify: tests if behavior changes (no test removal — structlog calls that are deleted lose nothing the tests asserted, since tests assert on events, not on log lines).

**Behavior delivered**:

Per DESIGN §Logging convention (Phase 3 sweep): **emitters emit only — no structlog inside emit sites**. The only legitimate structlog call at an emit site is one carrying information DISTINCT from the event payload (e.g., `exc_info=True` for the traceback while the event carries `error_class` + `error_message`).

**Audit process**:

1. List every emit site:
   ```bash
   rg 'event_bus\.emit\(' --type py personalscraper/ -l
   ```
2. For each file in the list, inspect the lines surrounding each `emit(`. If a `log.info(...)` / `log.debug(...)` immediately precedes or follows the emit and carries the SAME information, DELETE the log call.
3. If a log call carries DIFFERENT information (e.g., exception traceback alongside an `error_class`+`error_message` event), KEEP it but ensure it does not duplicate.
4. Document the audit result in the commit message: "Removed N structlog calls; kept M for distinct info (mostly `exc_info=True` traceback alongside `StepErrored`)".

**Tests written**:

- `test_structlog_emit_dedup_audit`: a regression test that asserts a specific known-good emit site has exactly one `log.*` call (or zero) within a small range around the emit. Pick one canonical site (e.g., `Pipeline._run_step`) and lock it in. (Architecture tests of this style are brittle; keep the assertion narrow.)

**Steps**:

- [ ] Run the audit grep + manual inspection.
- [ ] Delete duplicate `log.*` calls.
- [ ] Run tests → green (no test should rely on a deleted log line; if one does, it was over-asserting on logs vs events — rewrite the test to assert on the event).
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): structlog dedup audit — emit sites do not double-log`.

---

## Sub-phase 3.12 — Phase 3 gate

**Hard verification gate**:

1. **`make lint`** → zero.
2. **`make test`** → all pass; baseline + Phase 1+2 + Phase 3 new tests (~50+). The TOTAL test count must equal baseline + (Phase 1 + Phase 2 + Phase 3 deltas) minus the deleted Phase-2 / Phase-3 transitional tests.
3. **`make check`** → green.
4. **Module size**: every module ≤ DESIGN budget table; `subscribers/rich_console.py` ≈ 180; `subscribers/telegram.py` ≈ 200 (still cap, Phase 4 will fit cross-cutting handlers within).
5. **Sweep greps — all must return ZERO**:
   - `rg 'from personalscraper\.observers' --type py personalscraper/ tests/` → 0.
   - `rg 'from personalscraper\.pipeline_observer' --type py personalscraper/ tests/` → 0.
   - `rg 'PipelineObserver\b' --type py personalscraper/ tests/` → 0.
   - `rg 'CollectorObserver\b' --type py personalscraper/ tests/` → 0.
   - `rg 'notify_progress\(' --type py personalscraper/ tests/` → 0.
   - `rg '\bStepEvent\b' --type py personalscraper/ tests/` → 0.
   - `ls personalscraper/pipeline_observer.py 2>&1 | grep -c 'No such'` → 1 (file deleted).
   - `ls personalscraper/observers 2>&1 | grep -c 'No such'` → 1 (dir deleted).
6. **`test_every_event_has_factory` green** (now non-vacuous — asserts on the 6 pipeline events).
7. **AppContext boundary test green**.
8. **Visual regression**: run a canonical pipeline against a fixture; capture Rich Console output via the determinism setup; compare against the immutable baseline at `tests/snapshots/rich_console_canonical.txt` (recorded in INDEX Pre-flight step 7, untouched since). **Byte-for-byte match required** — the entire Observer-to-Subscriber rewrite must be visually transparent.
9. **Smoke import**: `python -c "import personalscraper"` succeeds.
10. **Per-event envelope round-trip**: parametrized test passes for all 6 pipeline events.

**Steps**:

- [ ] Re-read each sub-phase 3.1–3.11; every checkbox checked.
- [ ] Run gate items 1–10; resolve red.
- [ ] Commit: `chore(event-bus): phase 3 gate — pipeline events migration complete`.

---

## Roll-back plan

Phase 3 is the **least reversible phase** because it deletes the Observer API. To roll back:

- `git revert <phase-3-commit-range>` — restores `pipeline_observer.py`, `observers/`, `StepContext.observers`, and every `notify_progress` call.
- The bus is left in place but unused (Phases 1+2 are intact).
- Single PR per phase, atomic commits → revert is a single operation per sub-phase if needed.

Once Phase 3 is merged to main and a subsequent feature is built on top, roll-back becomes harder. Treat Phase 3 merge as the **point of no return** for the Observer API.

## Open questions left for this phase

DESIGN §Open Questions:

- **#1 (\_disk_guard.py extraction location)**: not relevant to Phase 3 — that's Phase 4's call.
- **#2 (run_id propagation)**: resolved in Phase 2.
- **#3 (WebSocketSubscriber prototype)**: out of scope.

No new open questions introduced by Phase 3.
