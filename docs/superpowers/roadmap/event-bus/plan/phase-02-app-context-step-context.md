# Phase 2 — AppContext + StepContext slim

**Depends on**: Phase 1 (EventBus + ContextVar landed).
**Commits expected**: **9** (one per sub-phase: 2.1, 2.2a, 2.2b, 2.2c, 2.3, 2.4, 2.5, 2.6, 2.7 — where sub-phase 2.7 IS the phase-gate commit). Sub-phase 2.2 is intentionally split into three atomic commits (2.2a / 2.2b / 2.2c) to keep each `/implement:sub-phase` cycle below ~300 LOC of change — the StepContext refactor + ~15-file callsite sweep is the highest blast-radius change in the feature.
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
    dry_run: bool
    interactive: bool
    verbose: bool
    observers: tuple["PipelineObserver", ...]    # KEPT through Phase 2 — removed in Phase 3.7b
    upstream: Mapping[str, "StepReport"]
    extras: MutableMapping[str, Any]
    # LEGACY mirrors — populated by __post_init__, NEVER settable by caller.
    # Removed in 2.2c once all callsites read via ctx.app.config / ctx.app.settings.
    config: Config = field(init=False)
    settings: Settings = field(init=False)

    def __post_init__(self) -> None:
        # Frozen dataclass — use object.__setattr__ to populate the
        # auto-derived legacy fields. init=False on the fields removes
        # them from the constructor signature, so callers cannot pass
        # a mismatched value (no consistency assert needed).
        object.__setattr__(self, "config", self.app.config)
        object.__setattr__(self, "settings", self.app.settings)
```

**Locked mechanism** (resolves the dual-source ambiguity):

- `config` and `settings` are declared with `field(init=False)`. They are NOT part of the constructor signature, so callers cannot pass them at all. The dual-source invariant `ctx.config is ctx.app.config` is enforced **structurally** by the dataclass — not by a runtime assertion that could be bypassed or skipped.
- `__post_init__` uses `object.__setattr__` to bypass the frozen-dataclass guard (the standard pattern for derived fields on frozen dataclasses; this is also how the `Event` base auto-derives `source` in Phase 1.1).
- No `@property` proxies (the implementation note from the earlier draft was correct on that point).
- Identity holds: `ctx.config is ctx.app.config` is `True` by construction because both names point to the same object (`self.app.config`).

**Invariant**: in 2.2a, BOTH `ctx.app.config` and `ctx.config` work — every callsite sees a consistent view structurally. Production callsites are NOT migrated in this sub-phase; they read whichever shape they prefer. This keeps the build green at every step.

**Tests written**:

- `test_step_context_carries_app_and_run_id`: build with mock AppContext + a UUID; assert `ctx.app is the_app` and `ctx.run_id == the_uuid`.
- `test_step_context_legacy_fields_mirror_app_phase2a`: assert `ctx.config is ctx.app.config` AND `ctx.settings is ctx.app.settings` (identity, not just equality — the `__post_init__` guarantees same-object).
- `test_step_context_constructor_does_not_accept_config_kwarg`: attempt `StepContext(app=..., run_id=..., config=other_config, ...)`; assert `TypeError: __init__() got an unexpected keyword argument 'config'` (because `field(init=False)` removes it from the signature). Same assertion for `settings`. This locks the no-mismatch property.
- `test_step_context_still_has_observers_phase2`: assert `hasattr(ctx, "observers")` and `isinstance(ctx.observers, tuple)`. **DELETED in Phase 3.7a** (the test-migration sub-phase that scrubs every legacy-Observer reference from `tests/`) — explicit `# TODO(3.7a): delete this test when StepContext.observers is removed` comment in the test file.
- `test_step_context_remains_frozen`: attempt mutation of `ctx.app`; assert `FrozenInstanceError`.

**Steps**:

- [ ] Write failing tests.
- [ ] Add `app` and `run_id` fields to `StepContext` (required, before the existing fields).
- [ ] Add `config: Config = field(init=False)` and `settings: Settings = field(init=False)` AFTER all other fields.
- [ ] Add `__post_init__` populating them via `object.__setattr__`.
- [ ] Update every direct `StepContext(...)` construction site in production code AND test fixtures to populate the new `app` + `run_id` fields and to **stop passing `config=...` / `settings=...`** (those kwargs no longer exist). Pipeline builds StepContext in `Pipeline.run` — primary site; conftest fixtures are secondary sites.
- [ ] Run `pytest` → green.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): add app + run_id to StepContext with structural dual-source (config/settings derived in __post_init__)`.

Implementation note: `field(init=False)` is the cleanest mechanism for derived fields on frozen dataclasses. The 2.2b sweep changes the READ sites (`ctx.config` → `ctx.app.config`); 2.2c removes the legacy `field(init=False)` declarations and the `__post_init__` writes for them.

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

    def run(
        self,
        *,
        dry_run: bool = False,
        interactive: bool = False,
        verbose: bool = False,
        observers: tuple["PipelineObserver", ...] = (),
    ) -> PipelineReport:
        run_id = uuid4()
        token = current_correlation_id.set(str(run_id))
        try:
            # Build StepContext with app + run_id + run-scope flags + the
            # CLI-supplied observers tuple. Observers continue to drive the
            # console/Telegram output via notify_progress(ctx.observers, ...)
            # — Phase 3.7b removes this last bridge.
            ctx = StepContext(
                app=self._app,
                run_id=run_id,
                dry_run=dry_run,
                interactive=interactive,
                verbose=verbose,
                observers=observers,
                upstream={},
                extras={},
            )
            ...
            return report
        finally:
            current_correlation_id.reset(token)
```

**Observers parameter flow** (Phase 2 transitional wiring):

- `Pipeline.__init__` accepts ONLY `app: AppContext`. It MUST NOT accept `Console`, `observers`, `config`, or `settings` parameters.
- `Pipeline.run` accepts `observers: tuple[PipelineObserver, ...] = ()` as a keyword-only parameter (default empty). The CLI bootstrap constructs the tuple — `(RichConsoleObserver(console), TelegramObserver(creds))` when creds present — and passes it to `run(observers=...)`.
- `Pipeline.run` propagates the tuple into `StepContext.observers`. Each step then calls `notify_progress(ctx.observers, StepEvent(...))` as today; visual behavior unchanged.
- Phase 3.7b removes the `observers` parameter from `Pipeline.run` (and removes `StepContext.observers`); from then on, the CLI registers `RichConsoleSubscriber` / `TelegramSubscriber` directly on `app.event_bus` and no observers flow through `Pipeline.run`.

**Tests written**:

- `test_pipeline_init_takes_app_context_only`: assert `set(inspect.signature(Pipeline.__init__).parameters)` is `{"self", "app"}`. (Pipeline.**init** MUST NOT have `console`, `observers`, `config`, or `settings` kwargs.)
- `test_pipeline_run_accepts_observers_kwarg`: assert `"observers"` in `inspect.signature(Pipeline.run).parameters` AND its default is `()` (empty tuple). Phase 3.7b removes this kwarg.
- `test_pipeline_run_propagates_observers_to_step_context`: install a stub step that captures `ctx.observers`; pass `observers=(stub_observer_a, stub_observer_b)` to `Pipeline.run(...)`; assert `ctx.observers == (stub_observer_a, stub_observer_b)`.
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

## Sub-phase 2.4 — Migrate CLI entry to build `AppContext`

**Repo layout** (verified at plan time, branch `feat/event-bus`, HEAD `dd4a055`):

- `personalscraper/cli.py` (106 LOC) — top-level Typer app + entry function.
- `personalscraper/commands/pipeline.py` (379 LOC) — contains the actual `Pipeline(...)` construction at line 335. This is the result of the `arch-cleanup` decomposition.

The `personalscraper run` CLI command delegates to `commands/pipeline.py`. **The Pipeline construction site is in `commands/pipeline.py`, not `cli.py`.** This sub-phase therefore modifies `commands/pipeline.py` primarily and `cli.py` only minimally (if at all). No "verify at implementation time" — the layout is locked.

**Files**:

- Modify: `personalscraper/commands/pipeline.py` — add the `_build_app_context` helper near the top; replace the `Pipeline(...)` construction at line ~335 with `Pipeline(app=_build_app_context(...))`; modify the `run(...)` invocation to pass `observers=...` and run-scope flags.
- Modify: `personalscraper/cli.py` — touch only if the Pre-flight probe below returns "TOUCH-CLI". The vast majority of the change is in `commands/pipeline.py`.

**Pre-flight probe (Class A — decide deterministically, no "verify at impl time" hedging)**:

```bash
# Does cli.py currently pass Config or Settings positionally / via kwarg to
# any Typer command function it delegates to? If yes → "TOUCH-CLI";
# if no → "SKIP-CLI" (the whole Config/Settings handling already lives in
# commands/pipeline.py and cli.py merely wires Typer).
if rg --type py 'config=|settings=|Config\(|Settings\(' personalscraper/cli.py | grep -q -v '^[^:]*:\s*#'; then
  echo "TOUCH-CLI"
else
  echo "SKIP-CLI"
fi
```

Record the result in the sub-phase commit body as a literal `cli_probe_result: TOUCH-CLI` or `cli_probe_result: SKIP-CLI` trailer line. The sub-phase implementation MUST follow whichever branch the probe returned — no agent improvisation.

- Modify: `tests/commands/test_pipeline.py` (and any sibling tests that exercise the CLI entry).

**Behavior delivered**:

- A new helper `_build_app_context(config_path: Path, settings_overrides: dict) -> AppContext` in `commands/pipeline.py` constructs `Config`, `Settings`, a fresh `EventBus()`, and returns the `AppContext`.
- The pipeline command wires legacy observers (`RichConsoleObserver` always, `TelegramObserver` if creds present — **still legacy observers in Phase 2**) and passes them to `Pipeline.run(observers=...)` per the signature locked in 2.3.
- The pipeline command does NOT yet subscribe anything to `app.event_bus` (no subscribers exist yet — they land in Phase 3.5 / 3.6).
- Pipeline visual behavior unchanged: console output identical to before Phase 2.

**Tests written**:

- `test_pipeline_command_builds_app_context_and_passes_to_pipeline`: invoke the pipeline command via `CliRunner` with a temp config; assert (via a `Pipeline` monkeypatch capturing `__init__` args) that `Pipeline.__init__` received an `AppContext` whose `config.staging_dir` matches the temp config.
- `test_pipeline_command_constructs_event_bus`: same flow; assert `app.event_bus` is an `EventBus` instance with zero subscribers (`len(app.event_bus._subscribers) == 0`).
- `test_pipeline_command_console_output_unchanged`: replay the `CANONICAL_SEQUENCE` (from `tests/snapshots/_canonical_sequence.py`, recorded in INDEX Pre-flight #7) through the legacy `RichConsoleObserver` wired by this sub-phase's CLI bootstrap; capture via the determinism setup `Console(width=120, color_system=None, force_terminal=False, file=StringIO(), record=True)`; compare against the immutable baseline at `tests/snapshots/rich_console_canonical.txt`. **This is the Phase 2 regression lock** — Phase 2 must NOT change the visual output. Same baseline is also referenced by Phase 3 §3.5 (RichConsoleSubscriber matches it) and Phase 3 §3.9 gate.

**Steps**:

- [ ] Write failing tests.
- [ ] Refactor `commands/pipeline.py` to call `_build_app_context` and pass `app=...` to `Pipeline.__init__`, and `observers=(RichConsoleObserver(...), ...)` to `Pipeline.run(...)`.
- [ ] If `cli.py` constructs Config/Settings before delegating to the command function: refactor it to pass a config path / overrides dict instead, and let `_build_app_context` do the construction. Otherwise: leave `cli.py` untouched.
- [ ] Update any test that previously constructed `Pipeline(...)` directly.
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
3. Walks `ast.ClassDef` AND `ast.FunctionDef` AND `ast.AsyncFunctionDef` nodes, **building a qualified name** for nested defs: a top-level function `foo` is keyed as `"foo"`, a method `Bar.__init__` (a `FunctionDef` named `"__init__"` nested inside `ClassDef("Bar")`) is keyed as `"Bar.__init__"`. Use `ast.NodeVisitor` with an internal class-name stack.
4. For each function/method, inspect every parameter's annotation via `ast.unparse(arg.annotation)`.
5. If any parameter's unparsed annotation is exactly `"AppContext"` or `'"AppContext"'` (forward-ref string), record the `(module_path, qualified_name)` tuple.
6. Compare the recorded set against the explicit allowlist using TWO data structures:

```python
# tests/architecture/test_app_context_boundary.py

# (1) Module-level allowlist: every function in these modules is allowed
# to take AppContext, regardless of name. Used for core/app_context.py
# (the home of AppContext itself + its factories) and for tests/fixtures/**.
APP_CONTEXT_ALLOWED_MODULES: set[str] = {
    "personalscraper/core/app_context.py",
    # tests/fixtures/** is skipped by the walker (it doesn't descend
    # into tests/) — listed here for documentation only.
}

# (2) Per-(module, qualified_name) allowlist: specific entrypoints
# that are authorised boundary sites.
APP_CONTEXT_ALLOWED_FUNCS: set[tuple[str, str]] = {
    ("personalscraper/cli.py", "main"),
    ("personalscraper/commands/pipeline.py", "_build_app_context"),
    ("personalscraper/commands/pipeline.py", "run_command"),       # Typer command function — name verified via `rg --type py '@app\.command' personalscraper/commands/pipeline.py -A2` at Pre-flight; if the actual function name differs, fix BOTH this allowlist entry AND the AST allowlist test in the same commit
    ("personalscraper/commands/library/scan.py", "library_index"),
    ("personalscraper/trailers/cli.py", "scan"),
    ("personalscraper/trailers/cli.py", "download"),
    ("personalscraper/trailers/cli.py", "verify"),
    ("personalscraper/trailers/cli.py", "purge"),
    ("personalscraper/pipeline.py", "Pipeline.__init__"),
}

def is_allowed(module_path: str, qualified_name: str) -> bool:
    if module_path in APP_CONTEXT_ALLOWED_MODULES:
        return True
    return (module_path, qualified_name) in APP_CONTEXT_ALLOWED_FUNCS
```

7. Assert: every recorded `(module_path, qualified_name)` is allowed. The error message lists violations with module:line for fast triage.

The walker:

- Skips `tests/` entirely (test fixtures may take AppContext freely).
- Descends through `personalscraper/` recursively.
- Uses `ast.NodeVisitor` with a `_class_stack: list[str]` updated on `visit_ClassDef` to build qualified names.

**Tests written** (in `tests/architecture/test_app_context_boundary.py`):

- `test_no_internal_module_takes_app_context`: the main assertion — every recorded site is allowed.
- `test_allowlist_funcs_are_live`: for every `(module_path, qualified_name)` in `APP_CONTEXT_ALLOWED_FUNCS`, parse the module, walk it, assert a function with that qualified name exists. Catches stale allowlist after refactors.
- `test_allowlist_modules_exist`: for every module in `APP_CONTEXT_ALLOWED_MODULES`, assert the file exists.
- `test_app_context_module_factories_take_app_context`: positive smoke — assert that at least one function in `personalscraper/core/app_context.py` takes `AppContext` in its signature (sanity check that the walker actually finds it; without this, a typo in the walker could silently pass).
- `test_boundary_test_module_size`: assert `tests/architecture/test_app_context_boundary.py` ≤ 100 LOC (DESIGN budget — uplifted from 80 to accommodate the qualified-name walker; document in commit).

**Steps**:

- [ ] Write the AST walker with qualified-name building.
- [ ] Populate the initial allowlists with the boundaries introduced in 2.3 / 2.4 / 2.5 / 2.1.
- [ ] Run → expect first iteration to FAIL with a list of non-allowlist sites; **investigate each**: either the site is a true boundary (add to `APP_CONTEXT_ALLOWED_FUNCS`) or it is an over-broad signature (refactor to take a narrower service like `event_bus: EventBus`).
- [ ] Run → all green.
- [ ] `make check` green.
- [ ] Commit: `test(event-bus): add AST-based AppContext boundary test + initial allowlists`.

---

## Sub-phase 2.7 — Phase 2 gate

**Files**: none new.

**Hard verification gate** (all must pass):

1. **`make lint`** → zero errors.
2. **`make test`** → all tests pass; cumulative test count MUST have grown by **at least 80** new tests since the feature baseline (Phase 1 minimum 50 + Phase 2 minimum 30). A lower count means a test was silently skipped or deleted — investigate and restore. Test count CANNOT regress.
3. **No new skips / xfails** — per Invariant 3 item 3: `rg -c '@pytest\.mark\.(skip|xfail|skipif)' tests/ -g '*.py' | awk -F: '{s+=$2} END{print s}'` MUST equal `<SKIP_BASELINE>` from INDEX Pre-flight #9.
4. **`make check`** → green.
5. **Module size**:
   - `personalscraper/core/event_bus.py` ≤ 400 (DESIGN uplift — Phase 2 does NOT touch this file, so the cap is inherited from Phase 1.9 unchanged).
   - `personalscraper/core/app_context.py` ≤ 80.
   - `personalscraper/pipeline_protocol.py` — verify still under its current ceiling.
   - `tests/architecture/test_app_context_boundary.py` ≤ 100 (DESIGN-aligned uplift for the qualified-name walker; see Phase 2.6 implementation note).
6. **AppContext boundary test green**: `pytest tests/architecture/test_app_context_boundary.py -v`.
7. **Visual regression smoke**: run `personalscraper run --dry-run` against a recorded fixture; visual diff vs baseline ≤ zero changes (Phase 2 MUST NOT change pipeline output).
8. **Targeted greps**:
   - `rg 'ctx\.config\b|ctx\.settings\b' --type py personalscraper/ tests/` → zero matches (2.2b swept reads; 2.2c removed the fields).
   - `rg 'StepContext\(.*config=' --type py personalscraper/ tests/` → zero matches (2.2c removed the constructor kwarg).
   - `rg 'Pipeline\((console=|observers=|config=|settings=)' --type py personalscraper/ tests/` → zero matches (Pipeline no longer accepts these kwargs; 2.3).
   - `rg 'from personalscraper\.observers' --type py personalscraper/ tests/` → still has matches (legacy observers still imported in Phase 2 — Phase 3 removes them).
   - `rg 'notify_progress\(' --type py personalscraper/ tests/` → still has matches (legacy emit path still active — Phase 3 removes).
9. **Smoke imports**:
   - `python -c "import personalscraper"` succeeds.
   - `python -c "from personalscraper.core.app_context import AppContext; print(AppContext.__dataclass_fields__.keys())"` prints `dict_keys(['config', 'settings', 'event_bus'])`.
10. **No emit sites in production code** (still no `bus.emit` outside event_bus.py — Phase 3 adds them):
    ```bash
    rg '\.event_bus\.emit\(|app\.event_bus\.emit\(' --type py personalscraper/
    ```
    Expected: zero matches.

**Steps**:

- [ ] Re-read each sub-phase 2.1 / 2.2a / 2.2b / 2.2c / 2.3 / 2.4 / 2.5 / 2.6; confirm every checkbox checked.
- [ ] Run gate items 1–10 above; resolve any red.
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
