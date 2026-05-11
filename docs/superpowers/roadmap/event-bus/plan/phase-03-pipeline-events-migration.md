# Phase 3 — Pipeline event migration + subscribers rewrite

**Depends on**: Phase 2 (AppContext + slim StepContext + bus available; observers still legacy).
**Commits expected**: **11** — sub-phases 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7a, 3.7b, 3.7c, 3.8, 3.9; sub-phase 3.9 IS the phase-gate commit.
**Rebalanced from earlier draft**: the four-way step-emit partitioning (old 3.4 / 3.5 / 3.6 / 3.7) is collapsed into a single mechanical sweep (new 3.4); legacy-deletion (old 3.10) is expanded into three atomic commits (3.7a tests rewrite, 3.7b production deletion, 3.7c docs sweep) so each commit stays below ~300 LOC and is independently revertable. See INDEX `Pre-flight step 8` for the rationale.
**Goal**: Migrate the pipeline from the legacy `notify_progress(observers, …)` path to bus emit; rewrite `RichConsoleObserver` and `TelegramObserver` as bus subscribers; **delete** the entire Observer infrastructure. This is the most invasive phase — every pipeline step, every observer test, and every documentation reference is touched.

## Scope

**In scope** (DESIGN.md §Migration / Removed, §Refactored, §CLI integration, §Logging convention):

- `personalscraper/events/__init__.py` — package init + re-export registry (eager-imports each producer module at import time so `Event.__init_subclass__` populates the registry before consumers call `event_from_envelope`).
- `personalscraper/pipeline_events.py` — flat module next to `pipeline.py`, containing `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`, `StepErrored`, `ItemProgressed`. **Does NOT introduce a `personalscraper/pipeline/` package** — converting the flat `pipeline.py` to a package is out of scope for event-bus (deferred to a future refactor).
- Pipeline run loop emits `PipelineStarted` / `PipelineEnded` / `StepStarted` / `StepCompleted` / `StepErrored`.
- Each of the 9 pipeline steps emits `ItemProgressed` at every legacy `notify_progress` site (single mechanical sweep in 3.4).
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

## Phase 3 transition strategy (applies to sub-phases 3.4–3.7c)

The pipeline currently emits user-visible progress through `notify_progress(ctx.observers, StepEvent(...))`. Phase 3 must migrate every site to `ctx.app.event_bus.emit(ItemProgressed(...))` WITHOUT regressing the visual output captured in the canonical baseline `tests/snapshots/rich_console_canonical.txt` (recorded in INDEX Pre-flight step 7).

**Adopted strategy: ALONGSIDE then DELETE**

- Sub-phase 3.4 adds `event_bus.emit(ItemProgressed(...))` **alongside** the existing `notify_progress(...)` call at every site, in one mechanical sweep across all 9 steps. Both paths execute. The bus emit goes to whatever subscribers exist (initially: nothing in 3.4, then `RichConsoleSubscriber` once 3.5 lands, then `TelegramSubscriber` once 3.6 lands). The legacy `notify_progress` keeps the visual output stable.
- Sub-phases 3.7a / 3.7b / 3.7c collectively delete every `notify_progress` call, the `pipeline_observer.py` module, the `observers/` package, the `StepContext.observers` field, and migrate every test + doc reference. The deletion is split into three commits to keep each below ~300 LOC; build stays green at every commit boundary by deletion-order (tests first → production second → docs third).

Rationale: the visual regression test (`tests/snapshots/rich_console_canonical.txt`) MUST stay green at every sub-phase boundary. The alongside strategy gives this guarantee because the legacy `notify_progress` → legacy `RichConsoleObserver` chain stays intact until 3.7b. The cost is a brief period of "double emit" inside Phase 3 — acceptable because the bus has no console subscriber until 3.5 (no double-print), and 3.7b cleans up.

**Rejected alternative**: deleting `notify_progress` calls in 3.4 (replacing rather than adding). Rejected because steps that have been migrated would then produce silent runs until 3.5 lands `RichConsoleSubscriber` — breaking the visual regression invariant.

---

## Sub-phase 3.1 — Define `pipeline_events.py` + factories + tests + Report JSON-safety pre-investigation

**Files**:

- Create: `personalscraper/events/__init__.py` (package init; re-exports populated as events land; **eagerly imports `personalscraper.pipeline_events` and every other producer module** so `Event.__init_subclass__` populates `_EVENT_CLASS_REGISTRY` at import time — DESIGN §Event catalog).
- Create: `personalscraper/pipeline_events.py` (flat module next to `personalscraper/pipeline.py`; the project's `pipeline.py` is a single flat module today, NOT a package — verified via `ls personalscraper/pipeline*`).
- Modify: `tests/fixtures/event_samples.py` — add 6 factories.
- Create: `tests/event_bus/test_pipeline_events.py`
- **If Report JSON-safety investigation reveals a problem**: modify `personalscraper/models.py` and/or `personalscraper/reports/*.py` to coerce the offending field(s) to JSON-safe types (see Pre-3.1 investigation below).

**Pre-3.1 investigation (run BEFORE writing the round-trip tests)**: enumerate every field of `PipelineReport` and `StepReport`:

```bash
rg --type py "class (Pipeline|Step)Report" personalscraper/ -A 60 | sed -n '/^@dataclass/,/^class\|^def\|^---/p'
```

For each field, classify its type as JSON-safe (str / int / float / bool / None / list / dict / datetime / UUID / Path / Enum / nested dataclass-of-safe-fields) or NOT JSON-safe (Console / Callable / file handle / generic Any-with-runtime-shape). If any field is NOT JSON-safe:

- Document the offending fields in the sub-phase commit message.
- Refactor `models.py` / `reports/*.py` to coerce them (e.g. drop a `console: Console` field, serialize a callable as a string identifier, etc.).
- Add a regression test that asserts the offending field is now JSON-safe.

This pre-investigation is bounded — it scopes a potentially-unknown refactor BEFORE the event-bus tests are written. If the investigation shows clean JSON-safe Reports today, this part is a no-op and the sub-phase reduces to event-class definition + tests.

**Behavior delivered**:

```python
# personalscraper/pipeline_events.py
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

- [ ] Run the Pre-3.1 investigation above; document Report field classification.
- [ ] If any Report field is NOT JSON-safe, refactor `models.py` / `reports/*.py` + add a regression test BEFORE proceeding.
- [ ] Write failing tests (event classes + factories + envelope round-trip).
- [ ] Implement the 6 event classes + 6 factories.
- [ ] Run; expect the envelope round-trip test to pass cleanly (Report JSON-safety was resolved in the pre-investigation step). If it still fails, that is an unexpected discovery — investigate inline; do NOT defer.
- [ ] If any regression is introduced, add a regression test in this same sub-phase (Invariant 5).
- [ ] Run → pass.
- [ ] `make check` green; `pipeline_events.py` ≤ 150 LOC; `events/__init__.py` ≤ 100 LOC (DESIGN budget).
- [ ] Commit: `feat(event-bus): add pipeline event catalog + factories + envelope round-trip`.

---

## Sub-phase 3.2 — Pipeline emits `PipelineStarted` and `PipelineEnded`

**Files**:

- Modify: `personalscraper/pipeline.py` (flat module today — DO NOT convert to a package).
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

The legacy `notify_progress(ctx.observers, …)` for lifecycle is still wired (Phase 2 kept it). Phase 3 thus emits via BOTH paths transitionally: 3.5 (RichConsoleSubscriber rewrite) lands the new console path alongside; 3.6 (Telegram rewrite) lands the new Telegram path alongside; 3.7b deletes `pipeline_observer.py` and every `notify_progress` call. Inside this sub-phase, double-emit is acceptable to keep the visual regression test green; it is paid off in 3.7b.

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

## Sub-phase 3.4 — Step emit migration (all 9 steps, one mechanical sweep)

**Files**:

- Modify: every step module that holds a `notify_progress(...)` call. Pre-flight grep (INDEX step 8) enumerates the exact list. Expected coverage across `personalscraper/ingest/`, `personalscraper/sort/`, `personalscraper/process/` (clean), `personalscraper/scraper/`, `personalscraper/cleanup/`, `personalscraper/enforce/`, `personalscraper/verify/`, `personalscraper/trailers/` (the in-pipeline trailers step), and `personalscraper/dispatch/`. Verify exact module layout at impl time.
- Modify: tests under `tests/ingest/`, `tests/sort/`, `tests/process/`, `tests/scraper/`, `tests/cleanup/`, `tests/enforce/`, `tests/verify/`, `tests/trailers/`, `tests/dispatch/` — one event-emit assertion per migrated site.

**Behavior delivered** (per Phase 3 transition strategy — see top of this file):

At **every** `notify_progress(ctx.observers, StepEvent(step=..., item=..., status=..., details=...))` call site across all 9 pipeline steps, **ADD** `ctx.app.event_bus.emit(ItemProgressed(step=..., item=..., status=..., details=...))` alongside. The legacy `notify_progress` call stays in place — it is removed in 3.7b along with the rest of the legacy API.

This keeps the visual regression baseline (`tests/snapshots/rich_console_canonical.txt`) green at every sub-phase boundary: the legacy `notify_progress` → `RichConsoleObserver` chain remains intact until 3.7b. The bus emit goes to no console subscriber until 3.5 lands `RichConsoleSubscriber`, so no double-print risk.

**Why single sweep, not per-step partitioning**: each per-step migration is ~5–20 LOC of production change + 3–4 trivial tests — far below the threshold where a separate `/implement:sub-phase` cycle is justified. Earlier draft of this plan split the work into groups A/B/C/D (old 3.4–3.7); rebalanced here to a single mechanical commit per Phase 3 review feedback (Phase 3 was overstuffed at 12 sub-phases; collapsing 3.4–3.7 into one halves the per-step ceremony cost without losing atomicity, since the change is genuinely uniform across steps).

**`ItemDispatched` boundary**: the dispatch step emits an `ItemProgressed` per item in this sub-phase. The `ItemDispatched` outcome event (from `dispatch/events.py`) is **Phase 4** — 3.4 only adds `ItemProgressed`.

**Tests written** (one set per step — ~25 tests total):

- `test_<step>_emits_item_progressed_per_item` × 9 (ingest, sort, clean, scrape, cleanup, enforce, verify, trailers, dispatch): run the step against a fixture with N items; collect `ItemProgressed`; assert N events with `step=<name>` and expected `status` values.
- `test_<step>_item_progressed_details_json_safe` × 9: collect an `ItemProgressed` from the step; call `event_to_dict(event)`; assert no `TypeError`. Forces the step to only put JSON-safe values in `details`.
- `test_scrape_item_progressed_includes_provider_and_confidence_in_details`: scrape-specific detail-keyset assertion.
- `test_verify_item_progressed_details_includes_check_category`: verify-specific detail-keyset assertion.

**Steps**:

- [ ] Pre-flight: re-run `rg 'notify_progress\(' --type py personalscraper/ -l` to enumerate the current site list (matches INDEX Pre-flight step 8).
- [ ] Write failing tests for every step.
- [ ] At each `notify_progress` site, ADD `ctx.app.event_bus.emit(ItemProgressed(...))` alongside. Mechanical — same payload shape, same callsite location.
- [ ] Run tests → pass.
- [ ] `make check` green.
- [ ] Sweep grep: `rg 'notify_progress\(' --type py personalscraper/ | wc -l` — must still show every original call site (kept alongside per the transition strategy). Document the count in the commit message; 3.7b will verify it drops to zero.
- [ ] Sweep grep: `rg 'event_bus\.emit\(ItemProgressed' --type py personalscraper/ | wc -l` — must equal the original `notify_progress` count.
- [ ] Commit: `feat(event-bus): all 9 pipeline steps emit ItemProgressed alongside legacy notify_progress`.

---

## Sub-phase 3.5 — Rewrite `RichConsoleObserver` → `RichConsoleSubscriber`

**Files**:

- Rename: `personalscraper/observers/rich_console.py` → `personalscraper/subscribers/rich_console.py` (note: this rename happens once, here, for this file; the `observers/` → `subscribers/` package-level rename is Sub-phase 3.7b once all observers have been rewritten).
- Create: `personalscraper/subscribers/__init__.py` (new package).
- Modify: `personalscraper/cli.py` to import `RichConsoleSubscriber` from new location AND register it on the bus instead of passing as an observer.
- Modify: tests for the Rich console output.

**Behavior delivered**:

- `RichConsoleSubscriber(bus: EventBus, console: Console)`:
  - In `__init__`, subscribes itself to `PipelineStarted`, `PipelineEnded`, `StepStarted`, `StepCompleted`, `StepErrored`, `ItemProgressed`. Stores tokens.
  - Each `on_<event>` handler reproduces the visual behavior of the legacy `RichConsoleObserver`'s corresponding callback (bytes-identical rendering for the canonical snapshot test).
  - `close()` unsubscribes all tokens (clean teardown for tests).
- CLI bootstrap (`cli.py`): instead of `observers = (RichConsoleObserver(console), …)` + `Pipeline(..., observers=observers)`, do `RichConsoleSubscriber(app.event_bus, console)` (constructor self-subscribes). The legacy `RichConsoleObserver` is still imported and threaded via `StepContext.observers` until 3.7b deletes the legacy path entirely.

**Tests written**:

- `test_rich_console_subscriber_subscribes_on_init`: instantiate; assert 6 subscription tokens stored.
- `test_rich_console_subscriber_close_unsubscribes_all`: instantiate; close; assert bus dispatches an `ItemProgressed` to zero subscribers afterwards.
- `test_rich_console_subscriber_snapshot_matches_baseline`: **the visual regression lock**. Use the determinism setup `Console(width=120, color_system=None, force_terminal=False, file=StringIO(), record=True)`. Run the canonical pipeline against `RichConsoleSubscriber` wrapping this console; capture `console.export_text()`; compare against the **immutable baseline** at `tests/snapshots/rich_console_canonical.txt` (recorded once in INDEX Pre-flight step 7 by running the LEGACY `RichConsoleObserver` against the same canonical pipeline, pre-Phase-1). The baseline is byte-identical to what the legacy observer produced; this test asserts the new subscriber matches that bytes-identical output. **Never re-record the baseline inside Phase 3** — if it needs adjustment, the entire feature is invalid.
- `test_rich_console_subscriber_outputs_match_legacy_observer_for_canonical_run`: same as the snapshot, but performed in-process by running BOTH the legacy `RichConsoleObserver` and the new `RichConsoleSubscriber` against the same emit sequence and comparing their recorded outputs directly. **This test is DELETED in Sub-phase 3.7a** when the legacy observer is removed. Mark with a `# TODO(3.7a): delete this test when RichConsoleObserver is removed` comment.

**Steps**:

- [ ] Write failing tests including the legacy/new comparison test.
- [ ] Implement `RichConsoleSubscriber` mirroring `RichConsoleObserver`'s rendering logic.
- [ ] Assert against the pre-existing baseline at `tests/snapshots/rich_console_canonical.txt` (recorded during INDEX Pre-flight step 7). **Do NOT re-record** — the baseline is immutable.
- [ ] **Smoke import check** (catches circular import during the transition where `observers/` and `subscribers/` coexist): `python -c "import personalscraper.observers; import personalscraper.subscribers; print('ok')"` → prints `ok`.
- [ ] Run → pass.
- [ ] `make check` green; `subscribers/rich_console.py` ≈ 180 LOC (DESIGN budget).
- [ ] Commit: `refactor(event-bus): rewrite RichConsoleObserver as RichConsoleSubscriber on the bus`.

---

## Sub-phase 3.6 — Rewrite `TelegramObserver` → `TelegramSubscriber`

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
- `test_telegram_subscriber_close_unsubscribes`: as in 3.5.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `TelegramSubscriber`.
- [ ] **Smoke import check** (same rationale as 3.5): `python -c "import personalscraper.observers; import personalscraper.subscribers; print('ok')"` → prints `ok`.
- [ ] Run → pass.
- [ ] `make check` green; `subscribers/telegram.py` at this point holds 2 handlers (≈ 100 LOC up from today's 54 LOC; the 200 LOC cap is the END-of-Phase-4 budget after circuit + disk handlers).
- [ ] Commit: `refactor(event-bus): rewrite TelegramObserver as TelegramSubscriber`.

---

## Sub-phase 3.7a — Migrate every test off the legacy Observer API

**Files**:

- Modify: every test file that imports from `personalscraper.observers` or `personalscraper.pipeline_observer`. Production code is NOT touched in this sub-phase — only test files.
- Delete: `tests/event_bus/test_step_context_shape.py::test_step_context_still_has_observers_phase2` (the temporary assertion landed in Phase 2.2a, marked for deletion).
- Delete: the Sub-phase 3.5 transitional test `test_rich_console_subscriber_outputs_match_legacy_observer_for_canonical_run` (legacy observer about to disappear).

**Behavior delivered**: every test rewritten to use `EventBus` + `CollectingSubscriber`. The production tree still has `pipeline_observer.py`, `observers/`, `StepContext.observers`, and every `notify_progress(...)` call — they remain functional through 3.7a. Tests stop reading them; the build stays green because production keeps both paths active.

**Pre-sub-phase grep**:

```bash
rg -l 'personalscraper\.(observers|pipeline_observer)' --type py tests/
rg -l 'CollectorObserver|PipelineObserver|StepEvent\b|notify_progress\(' --type py tests/
```

These are the files to migrate. Mechanical pattern: `CollectorObserver(...)` → `CollectingSubscriber(bus, EventType)`; `StepEvent(...)` → `ItemProgressed(...)`; imports retargeted to `personalscraper.subscribers` and `personalscraper.core.event_bus`.

**Tests written**: rewritten in place; the assertion shape evolves (e.g. `collector.events` becomes `subscriber.received`, but the test name and intent are preserved).

**Steps**:

- [ ] Grep the file list.
- [ ] For each file, rewrite imports + symbols mechanically.
- [ ] Delete the two transitional tests (Phase 2.2a + Phase 3.5).
- [ ] Run `pytest` → all green (production unchanged; tests on new API alongside).
- [ ] `make check` green.
- [ ] **Sweep grep gate** (tests only): `rg 'from personalscraper\.observers|from personalscraper\.pipeline_observer|CollectorObserver|PipelineObserver\b|StepEvent\b' --type py tests/` → zero matches.
- [ ] Commit: `test(event-bus): migrate every test off the legacy Observer API`.

---

## Sub-phase 3.7b — Delete legacy Observer infrastructure + remove `StepContext.observers` (production)

**Files**:

- Delete: `personalscraper/pipeline_observer.py`.
- Delete: `personalscraper/observers/__init__.py` and any remaining files in `personalscraper/observers/` (rich_console.py and telegram.py were moved in 3.5 / 3.6).
- Modify: `personalscraper/pipeline_protocol.py` — remove `observers: tuple[...]` field from `StepContext`.
- Modify: `personalscraper/pipeline.py` — remove the `observers` argument from `StepContext` construction; remove any remaining wiring that built the observer tuple.
- Modify: every `notify_progress(ctx.observers, …)` call site in `personalscraper/` — DELETE the legacy call entirely (the bus emit added in 3.4 takes over).
- Modify: `personalscraper/cli.py` and any non-Pipeline entrypoint that still constructed legacy observers (drop those construction calls).

**Behavior delivered**: the legacy API ceases to exist in production. The bus is the only emit path. Tests are already on the bus API (3.7a) so the build stays green at this commit boundary.

**Tests written**:

- `test_step_context_does_not_have_observers_attribute`: build `StepContext`; assert `not hasattr(ctx, "observers")`. (Replaces the Phase 2 test that asserted the opposite; that one was deleted in 3.7a.)

**Steps**:

- [ ] Write the new `not hasattr` test.
- [ ] Delete `pipeline_observer.py`.
- [ ] Delete `observers/__init__.py`.
- [ ] Remove `StepContext.observers` field from `pipeline_protocol.py`.
- [ ] Drop the `observers` kwarg from every `StepContext(...)` constructor call.
- [ ] Remove every `notify_progress(ctx.observers, …)` call in production code.
- [ ] Drop the observer-construction wiring from CLI / non-Pipeline entrypoints.
- [ ] Run tests → all green (3.7a migrated every test; nothing references the legacy API).
- [ ] **Sweep greps over `personalscraper/` only** (must ALL return zero):
  - `rg 'from personalscraper\.observers' --type py personalscraper/` → 0.
  - `rg 'from personalscraper\.pipeline_observer' --type py personalscraper/` → 0.
  - `rg 'PipelineObserver\b' --type py personalscraper/` → 0.
  - `rg 'PipelineObserverBase\b' --type py personalscraper/` → 0.
  - `rg 'CollectorObserver\b' --type py personalscraper/` → 0.
  - `rg 'notify_progress\(' --type py personalscraper/` → 0.
  - `rg '\bStepEvent\b' --type py personalscraper/` → 0.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): delete pipeline_observer.py and StepContext.observers; bus is the only emit path`.

---

## Sub-phase 3.7c — Docs sweep: remove every reference to the legacy Observer API

**Files**:

- Modify: `docs/reference/pipeline-internals.md` and any other reference doc that mentions `PipelineObserver`, `StepEvent`, `notify_progress`, `observers/`. Replace with bus equivalents.
- Modify: legacy archived docs are NOT touched (`docs/archive/legacy-alpha/`, `docs/archive/features/`) — archives are immutable historical record.

**Behavior delivered**: documentation reflects the new bus-only API. Search results for the deleted symbols return only archived material.

**Tests written**: none — docs-only sub-phase.

**Steps**:

- [ ] Grep `docs/` (excluding `docs/archive/`): `rg 'PipelineObserver|notify_progress|StepEvent|from personalscraper\.observers' docs/ -g '!docs/archive/**'` — produce the file list.
- [ ] For each file, rewrite the affected paragraphs to describe the bus API.
- [ ] Add `git add -f` for new doc files if any (global `~/.gitignore` blocks `docs/`).
- [ ] Sweep grep: `rg 'PipelineObserver|notify_progress|StepEvent|from personalscraper\.observers' docs/ -g '!docs/archive/**'` → zero matches.
- [ ] `make check` green (docs do not affect lint/test outcomes but the gate must remain green).
- [ ] Commit: `docs(event-bus): sweep references to legacy Observer API`.

---

## Sub-phase 3.8 — Structlog dedup audit at emit sites

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

## Sub-phase 3.9 — Phase 3 gate

**Hard verification gate**:

1. **`make lint`** → zero.
2. **`make test`** → all pass; baseline + Phase 1+2 + Phase 3 new tests (~50+). The TOTAL test count must equal baseline + (Phase 1 + Phase 2 + Phase 3 deltas) minus the deleted Phase-2 / Phase-3 transitional tests.
3. **`make check`** → green.
4. **Module size**: every module ≤ DESIGN budget table; `subscribers/rich_console.py` ≈ 180; `subscribers/telegram.py` ≈ 100 at end of Phase 3 (cap is 200 — circuit + disk handlers in Phase 4 grow it toward the cap).
5. **Sweep greps — all must return ZERO**:
   - `rg 'from personalscraper\.observers' --type py personalscraper/ tests/` → 0.
   - `rg 'from personalscraper\.pipeline_observer' --type py personalscraper/ tests/` → 0.
   - `rg 'PipelineObserver\b' --type py personalscraper/ tests/` → 0.
   - `rg 'CollectorObserver\b' --type py personalscraper/ tests/` → 0.
   - `rg 'notify_progress\(' --type py personalscraper/ tests/` → 0.
   - `rg '\bStepEvent\b' --type py personalscraper/ tests/` → 0.
   - `rg 'PipelineObserver|notify_progress|StepEvent|from personalscraper\.observers' docs/ -g '!docs/archive/**'` → 0.
   - `ls personalscraper/pipeline_observer.py 2>&1 | grep -c 'No such'` → 1 (file deleted).
   - `ls personalscraper/observers 2>&1 | grep -c 'No such'` → 1 (dir deleted).
6. **`test_every_event_has_factory` green** (now non-vacuous — asserts on the 6 pipeline events).
7. **AppContext boundary test green**.
8. **Visual regression**: run a canonical pipeline against a fixture; capture Rich Console output via the determinism setup; compare against the immutable baseline at `tests/snapshots/rich_console_canonical.txt` (recorded in INDEX Pre-flight step 7, untouched since). **Byte-for-byte match required** — the entire Observer-to-Subscriber rewrite must be visually transparent.
9. **Smoke import**: `python -c "import personalscraper"` succeeds.
10. **Per-event envelope round-trip**: parametrized test passes for all 6 pipeline events.

**Steps**:

- [ ] Re-read each sub-phase 3.1 / 3.2 / 3.3 / 3.4 / 3.5 / 3.6 / 3.7a / 3.7b / 3.7c / 3.8; every checkbox checked.
- [ ] Run gate items 1–10; resolve red.
- [ ] Commit: `chore(event-bus): phase 3 gate — pipeline events migration complete`.

---

## Roll-back plan

Phase 3 is the **least reversible phase** because it deletes the Observer API. To roll back:

- `git revert <phase-3-commit-range>` — restores `pipeline_observer.py`, `observers/`, `StepContext.observers`, and every `notify_progress` call.
- The atomic split (3.7a tests / 3.7b production / 3.7c docs) means each piece is independently revertable in reverse order: revert 3.7c (docs) first, then 3.7b (production restored, alongside dual-path resumes), then 3.7a (tests back on legacy).
- The bus is left in place but unused (Phases 1+2 are intact).

Once Phase 3 is merged to main and a subsequent feature is built on top, roll-back becomes the **fix-forward only** policy (DESIGN §Rollback policy). Treat Phase 3 merge as the **point of no return** for the Observer API.

## Open questions left for this phase

DESIGN §Open Questions:

- **#1 (\_disk_guard.py extraction location)**: not relevant to Phase 3 — that's Phase 4's call.
- **#2 (run_id propagation)**: resolved in Phase 2.
- **#3 (WebSocketSubscriber prototype)**: out of scope.

No new open questions introduced by Phase 3.
