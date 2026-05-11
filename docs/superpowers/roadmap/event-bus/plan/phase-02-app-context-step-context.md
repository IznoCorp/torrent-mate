# Phase 2 — AppContext + StepContext slim

**Depends on**: Phase 1 (EventBus + ContextVar landed).
**Commits expected**: **9** (one per sub-phase; sub-phase 2.9 IS the phase-gate commit). Sub-phase 2.2 is intentionally split into three atomic commits (2.2a / 2.2b / 2.2c) to keep each `/implement:sub-phase` cycle below ~300 LOC of change — the StepContext refactor + ~15-file callsite sweep is the highest blast-radius change in the feature.
**Goal**: Introduce `AppContext` at every process boundary, slim `StepContext` to its run-scope role, codify the boundary-only rule via an AST-based test. The pipeline keeps emitting via the legacy `notify_progress(ctx.observers, …)` path; the bus is constructed and threaded but not yet emitted to. Pipeline visual behavior is **unchanged**.

## Scope

**In scope** (DESIGN.md §Architecture / §AppContext (new) — boundary-only rule, §Migration / §Refactored / §StepContext, §Testing strategy / AppContext boundary test):

- `personalscraper/core/app_context.py` — `AppContext` frozen dataclass with `config`, `settings`, `event_bus`.
- `StepContext` gains `app: AppContext` and `run_id: UUID`; drops `config`, `settings`. **KEEPS `observers`** (removed in Phase 3).
- `Pipeline.__init__(app: AppContext)`. Generates `run_id` per run. Binds `current_correlation_id` for the run via try/finally.
- CLI entry, launchd scan entry, trailers commands rewired to build `AppContext` at the boundary.
- `tests/architecture/test_app_context_boundary.py` — AST-based boundary test with per-(module, function) allowlist.

**Out of scope (Phase 3 owns these)**:

- Removing `PipelineObserver`, `notify_progress`, `StepContext.observers` field — Phase 3.
- Pipeline emitting to the bus — Phase 3.
- Subscribers — Phase 3.

---

## Sub-phase 2.1 — Create `core/app_context.py`

**Files**:

- Create: `personalscraper/core/app_context.py`
- Create: `tests/event_bus/test_app_context.py`

**Behavior delivered**:

```python
from dataclasses import dataclass

from personalscraper.conf.models.config import Config
from personalscraper.config import Settings
from personalscraper.core.event_bus import EventBus


@dataclass(frozen=True)
class AppContext:
    """Long-lived process-scoped service bundle.

    Constructed once per process at the boundary (CLI entry, launchd scan
    entry, future Web UI / Watcher boot). Internal components MUST NOT
    receive AppContext "for convenience" — see boundary-only rule in
    DESIGN.md §Architecture.
    """

    config: Config
    settings: Settings
    event_bus: EventBus
```

Module ≤ 80 LOC (DESIGN budget). Future fields (`provider_registry`, `service_container`) are NOT added in v1.

**Tests written**:

- `test_app_context_is_frozen`: instantiate; assert `dataclasses.fields(AppContext)` produces expected names; attempt to mutate `ctx.config = something` and assert `FrozenInstanceError`.
- `test_app_context_carries_provided_services`: build with a mock Config + Settings + a real `EventBus()`; assert each field is the exact object passed.
- `test_app_context_event_bus_is_usable`: subscribe a `CollectingSubscriber`; emit a stub event via `ctx.event_bus.emit(...)`; assert collected.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `AppContext`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): add AppContext frozen dataclass at core/app_context.py`.

---

## Sub-phase 2.2a — Add `app` + `run_id` to `StepContext` (dual-source, legacy fields kept)

**Files**:

- Modify: `personalscraper/pipeline_protocol.py` (StepContext definition)
- Modify: `personalscraper/pipeline.py` (every `StepContext(...)` construction site populates both new fields and legacy fields)
- Modify: `tests/conftest.py` and per-domain conftest fixtures that build `StepContext` directly (populate the new fields too)
- Create: `tests/event_bus/test_step_context_shape.py`

**Behavior delivered** (transitional shape — kept stable for the duration of 2.2a → 2.2c):

```python
@dataclass(frozen=True)
class StepContext:
    app: AppContext                              # NEW — required
    run_id: UUID                                 # NEW — required
    config: Config                               # LEGACY — removed in 2.2c
    settings: Settings                           # LEGACY — removed in 2.2c
    dry_run: bool
    interactive: bool
    verbose: bool
    observers: tuple["PipelineObserver", ...]   # KEPT through Phase 2 — removed in Phase 3
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]
```

**Invariant**: in 2.2a, BOTH `ctx.app.config` and `ctx.config` work — every callsite sees a consistent view because the constructor populates `config = app.config` and `settings = app.settings` on construction. Production callsites are NOT migrated in this sub-phase; they read whichever shape they prefer. This keeps the build green at every step.

**Tests written**:

- `test_step_context_carries_app_and_run_id`: build with mock AppContext + a UUID; assert `ctx.app is the_app` and `ctx.run_id == the_uuid`.
- `test_step_context_legacy_fields_mirror_app_phase2a`: assert `ctx.config is ctx.app.config` and `ctx.settings is ctx.app.settings` (constructor enforces).
- `test_step_context_still_has_observers_phase2`: assert `hasattr(ctx, "observers")` and `isinstance(ctx.observers, tuple)`. **DELETED in Phase 3.10b** — explicit `# TODO(phase 3.10b): delete` comment in the test file.
- `test_step_context_remains_frozen`: attempt mutation; assert `FrozenInstanceError`.

**Steps**:

- [ ] Write failing tests.
- [ ] Add `app` and `run_id` fields to `StepContext` (required).
- [ ] Update every direct `StepContext(...)` construction site in production code AND test fixtures to populate the new fields. Pipeline builds StepContext in `Pipeline.run` — this is the primary site; conftest fixtures are the secondary sites.
- [ ] Verify constructor populates `config = app.config` / `settings = app.settings` (either via `__post_init__` consistency assertion or by removing the legacy fields' independent init — see notes below).
- [ ] Run `pytest` → green.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): add app + run_id to StepContext (dual-source with legacy config/settings)`.

Implementation note: keep `config: Config` / `settings: Settings` as ordinary frozen-dataclass fields populated at construction (NOT via `@property` proxies — properties on frozen dataclasses are awkward, and the goal here is "no callsite change yet", not "callsites silently redirect"). The 2.2b sweep changes the read sites; 2.2c removes the legacy fields.

---

## Sub-phase 2.2b — Sweep callsites: `ctx.config` → `ctx.app.config`, `ctx.settings` → `ctx.app.settings`

**Files**:

- Modify: every consumer of `ctx.config` / `ctx.settings` in `personalscraper/` (mechanical sweep; expected ~10–15 files across `ingest/`, `process/`, `dispatch/`, `scraper/`, `cleanup/`, `verify/`, `enforce/`, `trailers/`, plus any step adapters)
- Modify: tests that read `ctx.config` / `ctx.settings` (lower volume — fixtures dominate)

**Pre-sub-phase grep** to enumerate every callsite:

```bash
rg 'ctx\.config\b' --type py personalscraper/ tests/ -l > /tmp/ctx_config_files.txt
rg 'ctx\.settings\b' --type py personalscraper/ tests/ -l > /tmp/ctx_settings_files.txt
wc -l /tmp/ctx_config_files.txt /tmp/ctx_settings_files.txt
```

The output is the migration list. Every read site becomes `ctx.app.config` / `ctx.app.settings`. **Pure mechanical, no semantics change** — the dual-source from 2.2a guarantees the views are identical at every line.

**Tests written**: none new (2.2a's tests cover both shapes; if any existing test asserted specifically on `ctx.config`, it is updated mechanically to `ctx.app.config` in this sub-phase).

**Steps**:

- [ ] Grep callsites; produce the migration list.
- [ ] Mechanical sweep — `sed`-grade edit per file (manual confirmation per file to avoid false positives like comments / docstrings).
- [ ] Run `pytest` → green (2.2a's tests already cover both shapes, so this sweep is invisible to test outcomes).
- [ ] `make check` green.
- [ ] **Sweep grep gate**: `rg 'ctx\.config\b|ctx\.settings\b' --type py personalscraper/ tests/` → zero matches. The legacy fields still EXIST on StepContext (removed in 2.2c) but NO callsite reads them.
- [ ] Commit: `refactor(event-bus): sweep ctx.config / ctx.settings callsites to ctx.app.config / ctx.app.settings`.

---

## Sub-phase 2.2c — Drop legacy `config` / `settings` fields from `StepContext`

**Files**:

- Modify: `personalscraper/pipeline_protocol.py` (remove the two fields)
- Modify: `personalscraper/pipeline.py` and any conftest fixture that still passes `config=` / `settings=` to the `StepContext(...)` constructor (drop those kwargs)
- Update: `tests/event_bus/test_step_context_shape.py`

**Behavior delivered**: final `StepContext` shape for Phase 2 (matches DESIGN §Migration / Refactored, minus the `observers` field which remains until Phase 3):

```python
@dataclass(frozen=True)
class StepContext:
    app: AppContext
    run_id: UUID
    dry_run: bool
    interactive: bool
    verbose: bool
    observers: tuple["PipelineObserver", ...]
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]
```

**Tests written**:

- `test_step_context_does_not_have_config_attribute`: build; assert `not hasattr(ctx, "config")` (catches accidental re-introduction).
- `test_step_context_does_not_have_settings_attribute`: same for `settings`.
- Update `test_step_context_legacy_fields_mirror_app_phase2a` → DELETE this test (it asserted on the now-removed fields).

**Steps**:

- [ ] Write failing tests (the two new `not hasattr` assertions).
- [ ] Delete the `config: Config` / `settings: Settings` fields from `StepContext`.
- [ ] Drop the `config=` / `settings=` kwargs from every `StepContext(...)` construction site.
- [ ] Delete the obsolete dual-source test.
- [ ] Run `pytest` → green (2.2b already migrated every read; nothing references the legacy fields anymore).
- [ ] `make check` green.
- [ ] **Sweep grep gate**: `rg 'StepContext\(.*config=' --type py personalscraper/ tests/` → zero matches.
- [ ] Commit: `refactor(event-bus): drop legacy config/settings from StepContext (final Phase 2 shape)`.

---

## Sub-phase 2.3 — Refactor `Pipeline.__init__(app: AppContext)` + per-run `run_id` + ContextVar bind

**Files**:

- Modify: `personalscraper/pipeline.py`
- Modify: `tests/pipeline/test_pipeline_*.py` (every test that constructs a Pipeline)

**Behavior delivered**:

```python
class Pipeline:
    def __init__(self, app: AppContext) -> None:
        self._app = app

    def run(self, ...) -> PipelineReport:
        run_id = uuid4()
        token = current_correlation_id.set(str(run_id))
        try:
            # build StepContext with app + run_id + observers (Phase 2 still wires legacy observers here)
            ...
            return report
        finally:
            current_correlation_id.reset(token)
```

- Observers are still constructed and threaded into `StepContext.observers` from the caller (CLI) — Phase 2 does not remove the wiring.
- `Pipeline.__init__` MUST NOT accept `Console`, `observers`, `config`, `settings` parameters — they all come via `AppContext` or are constructed by the CLI bootstrap and handed in as observers.

**Tests written**:

- `test_pipeline_init_takes_app_context_only`: assert `inspect.signature(Pipeline.__init__).parameters` is `{"self", "app"}`.
- `test_pipeline_run_generates_unique_run_id`: run twice; collect `run_id` via a side-channel (e.g., a stub step that captures `ctx.run_id`); assert distinct UUIDs.
- `test_pipeline_run_binds_current_correlation_id_during_run`: install a stub step that reads `current_correlation_id.get()`; assert it returns `str(ctx.run_id)`.
- `test_pipeline_run_resets_correlation_id_after_run`: assert `current_correlation_id.get() is None` after `run()` returns (success path).
- `test_pipeline_run_resets_correlation_id_after_exception`: install a stub step that raises; assert `current_correlation_id.get() is None` after the exception propagates (try/finally path).
- `test_pipeline_run_propagates_run_id_to_step_context`: stub step captures `ctx.run_id`; assert equals the bound ContextVar value.

**Steps**:

- [ ] Write failing tests.
- [ ] Refactor `Pipeline.__init__` and `Pipeline.run` (try/finally around the body).
- [ ] Update every test that previously called `Pipeline(console=…, observers=…, config=…)`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): Pipeline accepts AppContext; generates run_id and binds ContextVar`.

---

## Sub-phase 2.4 — Migrate CLI entry (`cli.py`) to build `AppContext`

**Files**:

- Modify: `personalscraper/cli.py` (the `personalscraper run` entry; possibly via `commands/pipeline.py` per current `arch-cleanup` layout — verify at impl time).
- Modify: tests that exercise the CLI entry (e.g. `tests/commands/test_pipeline.py`).

**Behavior delivered**:

- A new helper `_build_app_context(config_path, settings_overrides) -> AppContext` constructs `Config`, `Settings`, a fresh `EventBus()`, and returns the `AppContext`.
- The CLI wires observers (`RichConsoleObserver` always, `TelegramObserver` if creds present — **still legacy observers in Phase 2**) and passes them to the `Pipeline.run(...)` boundary as the `observers` argument that flows into `StepContext.observers`.
- The CLI does NOT yet subscribe anything to the bus (no subscribers exist yet — they land in Phase 3 as the subscriber rewrite).
- Pipeline visual behavior unchanged: console output identical to before Phase 2.

**Tests written**:

- `test_cli_run_builds_app_context_and_passes_to_pipeline`: invoke `cli.run` command via `CliRunner` with a temp config; assert (via a Pipeline monkeypatch) that `Pipeline.__init__` received an `AppContext` whose `config.staging_dir` matches the temp config.
- `test_cli_run_constructs_event_bus`: same flow; assert `app.event_bus` is an `EventBus` instance (no subscribers yet).
- `test_cli_run_console_output_unchanged`: snapshot-compare the console output of a no-op pipeline run against the **pre-Phase-1 baseline** at `tests/snapshots/rich_console_canonical.txt` (recorded during INDEX Pre-flight step 7, BEFORE any refactor). Use the determinism setup `Console(width=120, color_system=None, force_terminal=False, file=StringIO(), record=True)`. **This is the regression lock** — Phase 2 must NOT change the visual output, and the baseline is immutable for the duration of the feature. Same baseline is also referenced by Phase 3 §3.5 and §3.9.

**Steps**:

- [ ] Write failing tests.
- [ ] Refactor `cli.py` to call `_build_app_context` and pass to `Pipeline`.
- [ ] Run tests → pass.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): CLI entry builds AppContext at the process boundary`.

---

## Sub-phase 2.5 — Migrate non-Pipeline boundaries to build `AppContext` (launchd scan + trailers commands)

**Files**:

- Modify: `personalscraper/commands/library/scan.py::library_index` (launchd `library-index` Typer command — single function).
- Modify: `personalscraper/trailers/cli.py` — the four Typer entrypoints `scan`, `download`, `verify`, `purge` (single module, four functions; NOT four separate files).
- Modify: `personalscraper/indexer/commands/scan.py::library_index_command` (orchestrator entry called by `commands/library/scan.py`) — accept `event_bus` if not already threaded.
- Modify: `personalscraper/trailers/orchestrator.py` — accept `event_bus` if not already threaded (no emit yet; Phase 4 adds `TrailerDownloaded`).
- Modify: tests under `tests/commands/library/`, `tests/trailers/`.

**Behavior delivered**:

- Each non-Pipeline boundary builds its own `AppContext` at entry. Each binds its own `run_id` via `current_correlation_id.set(str(uuid4()))` in a try/finally bracketing the command body — these are the **non-pipeline `run_id` bind sites** (the Pipeline bind site lives in `Pipeline.run`, Sub-phase 2.3).
- The downstream orchestrator (`indexer/commands/scan.py::library_index_command`, `trailers/orchestrator.py`) receives `event_bus: EventBus` (NOT `AppContext`) per the boundary-only rule. Sub-phase budget includes refactoring those orchestrator signatures to accept `event_bus` (no emit yet — Phase 4 adds the actual emits).
- One mechanical sweep across both surfaces — they share the bootstrap shape (`_build_app_context` helper from 2.4 is reused).

**Tests written** (one assertion set per boundary):

- `test_library_index_command_builds_app_context`: invoke the launchd command via `CliRunner`; assert AppContext was constructed (monkeypatch capture).
- `test_library_index_command_binds_correlation_id`: stub a helper inside the scan body that reads `current_correlation_id.get()`; assert UUID string during the scan; `None` after the command returns.
- `test_library_index_command_passes_event_bus_to_orchestrator`: assert `library_index_command` received `event_bus` from the AppContext (not the full AppContext).
- `test_trailers_<cmd>_builds_app_context`: parametrized over `["scan", "download", "verify", "purge"]`; assert AppContext built.
- `test_trailers_<cmd>_binds_correlation_id`: parametrized; assert ContextVar UUID-string during body, None after.
- `test_trailers_<cmd>_passes_event_bus_to_orchestrator`: parametrized; assert orchestrator got the bus.

**Steps**:

- [ ] Write failing tests (~12 tests total: 3 for library scan + 9 for the four trailers cmds).
- [ ] Refactor `commands/library/scan.py::library_index` to call `_build_app_context` (from 2.4) and bind the ContextVar.
- [ ] Refactor each of the four functions in `trailers/cli.py` the same way.
- [ ] Update downstream orchestrator signatures to accept `event_bus`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): launchd scan and standalone trailers commands build AppContext`.

---

## Sub-phase 2.6 — AST-based AppContext boundary test

**Files**:

- Create: `tests/architecture/__init__.py` (if not existing).
- Create: `tests/architecture/test_app_context_boundary.py`

**Behavior delivered**:

AST-based test (DESIGN §Testing strategy / AppContext boundary test). The test:

1. Recursively walks every `*.py` file under `personalscraper/`.
2. Parses each via `ast.parse`.
3. Walks `ast.FunctionDef` and `ast.AsyncFunctionDef` nodes.
4. For each function, inspects every parameter's annotation via `ast.unparse(arg.annotation)`.
5. If any parameter's unparsed annotation is exactly `"AppContext"` or `'"AppContext"'` (forward-ref), the (module-path, function-name) tuple is recorded.
6. Asserts the recorded set is a SUBSET of the explicit allowlist:

```python
APP_CONTEXT_ALLOWLIST: set[tuple[str, str]] = {
    ("personalscraper/cli.py", "main"),
    ("personalscraper/cli.py", "_build_app_context"),
    ("personalscraper/commands/library/scan.py", "library_index"),
    ("personalscraper/trailers/cli.py", "scan"),
    ("personalscraper/trailers/cli.py", "download"),
    ("personalscraper/trailers/cli.py", "verify"),
    ("personalscraper/trailers/cli.py", "purge"),
    ("personalscraper/pipeline.py", "Pipeline.__init__"),
    ("personalscraper/core/app_context.py", "*"),                  # all factories here
}
```

(Exact entries adjusted to match real module paths at implementation time. Each entry MUST point to a real function that exists in the codebase; the test fails if the allowlist contains stale entries — see `test_allowlist_entries_are_live`.)

The test also asserts:

- `tests/fixtures/**/*.py` may take `AppContext` freely — those paths are skipped by the walker (allowed by default).
- `personalscraper/core/app_context.py` itself is allowed (factories/constructors).

**Tests written**:

- `test_no_internal_module_takes_app_context`: the main assertion.
- `test_allowlist_entries_are_live`: for every `(module_path, function_name)` in `APP_CONTEXT_ALLOWLIST`, assert the file exists AND the function (parsed via AST) exists with that name. Catches stale allowlist after refactors.
- `test_test_fixtures_may_take_app_context`: positive smoke — a fixture under `tests/fixtures/` taking AppContext is allowed.
- `test_boundary_test_module_size`: assert `tests/architecture/test_app_context_boundary.py` ≤ 80 LOC (DESIGN budget).

**Steps**:

- [ ] Write the AST walker logic.
- [ ] Populate the initial allowlist with the boundaries introduced in 2.4 / 2.5.
- [ ] Run → expect first iteration to FAIL with a list of non-allowlist sites; **investigate each**: either the site is a true boundary (add to allowlist) or it is an over-broad signature (refactor to take a narrower service).
- [ ] Run → all green.
- [ ] `make check` green.
- [ ] Commit: `test(event-bus): add AST-based AppContext boundary test + initial allowlist`.

---

## Sub-phase 2.7 — Phase 2 gate

**Files**: none new.

**Hard verification gate** (all must pass):

1. **`make lint`** → zero errors.
2. **`make test`** → all tests pass; baseline + Phase 1 (~57) + Phase 2 (~30) ≈ baseline + 87 new tests. (Adjust per actual count.)
3. **`make check`** → green.
4. **Module size**:
   - `personalscraper/core/event_bus.py` ≤ 350.
   - `personalscraper/core/app_context.py` ≤ 80.
   - `personalscraper/pipeline_protocol.py` — verify still under its current ceiling.
5. **AppContext boundary test green**: `pytest tests/architecture/test_app_context_boundary.py -v`.
6. **Visual regression smoke**: run `personalscraper run --dry-run` against a recorded fixture; visual diff vs baseline ≤ zero changes (Phase 2 MUST NOT change pipeline output).
7. **Targeted greps**:
   - `rg 'ctx\.config\b|ctx\.settings\b' --type py personalscraper/ tests/` → zero matches (2.2b swept reads; 2.2c removed the fields).
   - `rg 'StepContext\(.*config=' --type py personalscraper/ tests/` → zero matches (2.2c removed the constructor kwarg).
   - `rg 'Pipeline\((console=|observers=|config=|settings=)' --type py personalscraper/ tests/` → zero matches (Pipeline no longer accepts these kwargs; 2.3).
   - `rg 'from personalscraper\.observers' --type py personalscraper/ tests/` → still has matches (legacy observers still imported in Phase 2 — Phase 3 removes them).
   - `rg 'notify_progress\(' --type py personalscraper/ tests/` → still has matches (legacy emit path still active — Phase 3 removes).
8. **Smoke imports**:
   - `python -c "import personalscraper"` succeeds.
   - `python -c "from personalscraper.core.app_context import AppContext; print(AppContext.__dataclass_fields__.keys())"` prints `dict_keys(['config', 'settings', 'event_bus'])`.
9. **No emit sites in production code** (still no `bus.emit` outside event_bus.py — Phase 3 adds them):
   ```bash
   rg '\.event_bus\.emit\(|app\.event_bus\.emit\(' --type py personalscraper/
   ```
   Expected: zero matches.

**Steps**:

- [ ] Re-read each sub-phase 2.1 / 2.2a / 2.2b / 2.2c / 2.3 / 2.4 / 2.5 / 2.6; confirm every checkbox checked.
- [ ] Run gate items 1–9 above; resolve any red.
- [ ] Commit: `chore(event-bus): phase 2 gate — AppContext + StepContext slim`.

---

## Roll-back plan

- Phase 2 is **reversible** because the legacy observer path is intact: `Pipeline.run` still threads `observers` into `StepContext.observers`, and steps still call `notify_progress(ctx.observers, …)`. The visual regression test locks this in.
- Single-revert: `git revert <phase-2-commit-range>` brings back `ctx.config` / `ctx.settings` direct access.
- No schema/storage migration.

## Open questions left for this phase

DESIGN §Open Questions:

- **#2 (run_id propagation across launchd / standalone commands)**: resolved in 2.5 — each non-Pipeline AppContext build site (launchd library scan + the four trailers Typer entrypoints) generates its own `run_id`. Cross-process correlation remains a Watcher Service v2 concern. **No action needed in Phase 2 beyond what 2.5 already does.**

No new open questions introduced by Phase 2.
