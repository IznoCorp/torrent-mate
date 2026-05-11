# Phase 5 — Required-bus tightening + CLI polish

**Depends on**: Phase 4 (every cross-cutting component emits; `event_bus: EventBus | None` is the temporary migration contract).
**Commits expected**: **6** — 5.1, 5.2, 5.3, 5.4, 5.5, 5.6 (phase gate); the earlier draft's audit-only "5.6" is folded into the 5.6 gate to avoid a sub-phase that may produce zero commits (which confuses `/implement:sub-phase` orchestration).
**Goal**: Tighten the bus contract (remove every `| None`), ship the `DebugLogSubscriber` for `--verbose`, and document the whole system. After Phase 5, the feature is **mergeable**: every acceptance criterion from DESIGN.md is satisfied.

## Scope

**In scope** (DESIGN.md §Phase outline / Phase 5, §Acceptance criteria, §CLI integration):

- Remove `event_bus: EventBus | None = None` from `CircuitBreaker.__init__`; make it required.
- Remove `| None` from any other Phase 4 site that adopted the optional contract.
- Audit: every call site passes `event_bus=...` explicitly.
- Create `personalscraper/subscribers/debug_log.py` — `DebugLogSubscriber`.
- Wire `personalscraper run --verbose` to register `DebugLogSubscriber`.
- Write `docs/reference/event-bus.md` — full reference documentation.
- Final sweep: every acceptance criterion from DESIGN.md `## Acceptance criteria` checked.

**Out of scope**: nothing — Phase 5 is the closing phase.

---

## Sub-phase 5.1 — Make `CircuitBreaker.event_bus` required

**Files**:

- Modify: `personalscraper/core/circuit.py` — `event_bus: EventBus` (no `| None`).
- Modify: every test that constructs `CircuitBreaker` without a bus (mainly old tests preserved through Phase 4).
- Modify: any production call site discovered in the Phase 4 gate audit that did not yet pass `event_bus=`.

**Behavior delivered**:

```python
class CircuitBreaker:
    def __init__(
        self,
        *,
        event_bus: EventBus,        # required
        name: str = "anonymous",
        ...
    ) -> None:
        ...
```

Removing the `| None`:

- All production call sites already pass `event_bus=app.event_bus` (Phase 4 ensured this).
- All test sites that constructed a breaker for unit-testing a non-emit feature must now pass a fresh `EventBus()` (cheap to construct; ≤ 10 LOC change per test).

**Pre-sub-phase grep**:

```bash
rg 'CircuitBreaker\(' --type py personalscraper/ tests/ | grep -v 'event_bus='
```

The output is the work list. Every line must be either:

- (a) updated to pass `event_bus=...`, OR
- (b) explained in a comment if it's intentionally testing the absence (unlikely — the `| None` was a migration aid, not a permanent feature).

**Tests written**:

- `test_circuit_breaker_requires_event_bus`: assert `inspect.signature(CircuitBreaker.__init__).parameters["event_bus"].default is inspect.Parameter.empty` (no default).
- `test_circuit_breaker_event_bus_annotation_excludes_none`: parse the annotation; assert `"None"` not in the annotation string.
- All existing CircuitBreaker tests continue passing (with their constructor calls updated).

**Steps**:

- [ ] Write failing tests for the new signature.
- [ ] Grep call sites; produce the work list.
- [ ] Update each call site to pass `event_bus=`.
- [ ] Remove `| None` and the default from the signature.
- [ ] Update CircuitBreaker emit code to drop the `if event_bus is not None:` guard (always emit).
- [ ] Run tests → pass.
- [ ] **Audit grep** (gate item, must return zero):
  ```bash
  rg 'CircuitBreaker\(' --type py personalscraper/ tests/ | grep -v 'event_bus='
  ```
  Expected: zero matches.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): make CircuitBreaker.event_bus required`.

---

## Sub-phase 5.2 — Tighten other Phase 4 `| None` sites

**Files**: any other module from Phase 4 (DiskGuard, dispatcher, trailers service, indexer orchestrator) that adopted the `| None` migration contract.

**Behavior delivered**: same as 5.1 for each site. The Phase 4 gate audit (item 11) produced the full list. Each is tightened individually with its own gate audit.

**Pre-sub-phase grep + cross-check vs Phase 4.6 audit count**:

```bash
# Step 1: enumerate the current | None sites
rg 'event_bus: EventBus \| None' --type py personalscraper/ | tee /tmp/event_bus_none_sites.txt
wc -l /tmp/event_bus_none_sites.txt    # current count

# Step 2: extract Phase 4.6 gate commit count (documented in the gate commit body per
# Phase 4 §4.6 step 11):
git log --grep='phase 4 gate' --format='%H' | head -1 | xargs git show --format=%B
# Look for the line: "event_bus | None sites at Phase 4 gate: <N>"
```

**Cross-check assertion**: the count from Step 1 MUST equal the `<N>` documented in the Phase 4.6 gate commit body. If higher, a new `| None` site was introduced between the Phase 4 gate and the start of 5.1 — identify the new site (`diff /tmp/event_bus_none_sites.txt` against the gate-commit-time list) and tighten it as part of 5.2 too, without skipping the original list. If lower, 5.1 already tightened some sites — fine; the gate count is the upper bound.

Each match in the current list becomes a tightening target. If any module declares NO option (already required from Phase 4 or 5.1), it does not appear in the grep and is already done.

**Tests written**: one per tightened site, analogous to `test_circuit_breaker_requires_event_bus` (assert signature, assert annotation).

**Steps**:

- [ ] Grep; produce the list.
- [ ] For each site:
  - Write failing signature test.
  - Update signature to drop `| None`.
  - Update callers if any still pass nothing (rare — Phase 4 already threaded).
  - Update internal emit guards (`if event_bus is not None:` → unconditional emit).
- [ ] Run → pass.
- [ ] **Audit grep** must return zero matches.
- [ ] `make check` green.
- [ ] Commit: `refactor(event-bus): make event_bus required across all emit sites`.

---

## Sub-phase 5.3 — `DebugLogSubscriber` implementation

**Files**:

- Create: `personalscraper/subscribers/debug_log.py`
- Create: `tests/subscribers/test_debug_log.py`
- Modify: `tests/fixtures/event_samples.py` — no new factories, but the tests use the existing 13.

**Behavior delivered**:

```python
# personalscraper/subscribers/debug_log.py
class DebugLogSubscriber:
    """Subscribes to every event on the bus and logs them at DEBUG.

    Used by `personalscraper run --verbose` to expose the full event stream
    for operator debugging. Logs via structlog so the output integrates
    with the project's logging convention.
    """

    name = "debug_log"

    def __init__(self, bus: EventBus) -> None:
        self._token = bus.subscribe(Event, self.on_event)

    def on_event(self, event: Event) -> None:
        _log.debug(
            "event_emitted",
            event_type=type(event).__name__,
            event_id=str(event.event_id),
            correlation_id=event.correlation_id,
            source=event.source,
            payload=event_to_dict(event),
        )

    def close(self) -> None:
        # Caller stores the subscriber if it needs lifecycle management;
        # otherwise the subscriber lives for the duration of the process.
        ...
```

Module ≤ 40 LOC (DESIGN budget).

**Tests written**:

- `test_debug_log_subscriber_subscribes_to_event_base`: instantiate; assert the bus has one subscription for `Event`.
- `test_debug_log_subscriber_logs_at_debug_for_any_event`: instantiate; emit `PipelineStarted(report=...)`; capture structlog; assert one `event_emitted` log at DEBUG with `event_type="PipelineStarted"`, `event_id`, `payload` (a dict with `report` nested).
- `test_debug_log_subscriber_logs_for_every_event_type`: parametrized over all 13 event factories; emit each; assert one log per event with the right `event_type`.
- `test_debug_log_subscriber_close_unsubscribes`: instantiate, close, emit, assert no log.

**Steps**:

- [ ] Write failing tests.
- [ ] Implement `DebugLogSubscriber`.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): add DebugLogSubscriber for verbose event log streaming`.

---

## Sub-phase 5.4 — Wire `personalscraper run --verbose` to register `DebugLogSubscriber`

**Files**:

- Modify: `personalscraper/cli.py` (or `commands/pipeline.py` — verify) — when `--verbose` flag is set, instantiate `DebugLogSubscriber(app.event_bus)` after bus construction.
- Modify: any ad-hoc verbose handling that already exists — replace with this subscriber if it duplicates.
- Modify: tests for the verbose flag.

**Behavior delivered**:

When `--verbose` is on:

- Structlog log level is set to DEBUG (existing behavior; verify).
- `DebugLogSubscriber` is registered.
- Output stream is the structured event log + the structlog DEBUG output, separated by structlog's existing logger configuration.

**Tests written**:

- `test_cli_run_verbose_registers_debug_log_subscriber`: invoke `run --verbose` via `CliRunner` against a stub pipeline; monkeypatch the subscriber's `on_event` to count calls; assert ≥ 2 events received (at minimum `PipelineStarted` + `PipelineEnded`).
- `test_cli_run_without_verbose_does_not_register_debug_log_subscriber`: invoke without `--verbose`; assert no `DebugLogSubscriber` registered (a side-channel sentinel set by the subscriber's `__init__` can be checked, or check the bus's subscriber count for `Event` base).

**Steps**:

- [ ] Write failing tests.
- [ ] Wire `--verbose` to register `DebugLogSubscriber`.
- [ ] Remove any obsolete ad-hoc verbose handling.
- [ ] Run → pass.
- [ ] `make check` green.
- [ ] Commit: `feat(event-bus): --verbose registers DebugLogSubscriber on the bus`.

---

## Sub-phase 5.5 — Write `docs/reference/event-bus.md`

**Files**:

- Create: `docs/reference/event-bus.md`
- Modify: `CLAUDE.md` — add an entry to the Reference Index table pointing at the new doc.

**Behavior delivered**:

`docs/reference/event-bus.md` — comprehensive reference (target: ~400-600 LOC).

**Required sections** (per DESIGN §Acceptance criteria):

1. **Purpose & high-level architecture** — link to DESIGN.md for the why; this doc is the how.
2. **API reference**:
   - `EventBus.subscribe(event_type, callback) -> SubscriptionToken`
   - `EventBus.unsubscribe(token)`
   - `EventBus.emit(event)`
   - `Event` base class fields (timestamp, source, event_id, correlation_id) + auto-derivation rules.
   - `event_to_dict`, `event_to_envelope`, `event_from_envelope` — when to use which.
   - `current_correlation_id: ContextVar` — bind/reset pattern.
3. **Event catalog (v1)** — table replicating DESIGN §Event catalog; each event listed with its module, payload fields, and producer.
4. **Boundary-only `AppContext` rule** — what counts as a boundary, how the AST test enforces it, how to add a new boundary to the allowlist.
5. **JSON serialization contract** — encoding rules table, examples (one per encoding case), `event_to_dict` vs `event_to_envelope` decision guide.
6. **`current_correlation_id` ContextVar convention** — bind/reset pattern with code samples for: CLI bootstrap, launchd scan bootstrap, trailers standalone bootstrap, long-lived emitter scenario.
7. **Writing a new event** — step-by-step recipe: define the dataclass, register via the import-time mechanism, add a factory in `tests/fixtures/event_samples.py`, write the round-trip test.
8. **Writing a new subscriber** — step-by-step recipe: subscribe in `__init__`, handle event types, optional `close()` for lifecycle.
9. **Testing patterns** — `CollectingSubscriber[E]`, factories registry, AST boundary test.
10. **Performance notes** — MRO cache, COW tuples, fast path, when to worry (hint: not for `ItemProgressed` even at 1000×/run).
11. **Future evolution** (non-engaging) — link to DESIGN §Roadmap Alignment.

`CLAUDE.md` Reference Index update — add row:

```markdown
| EventBus internals, event catalog, subscriber recipes, AppContext boundary rule, ContextVar pattern | `docs/reference/event-bus.md` |
```

**Tests written**:

- None (it's a docs file).
- **However**, a one-time link-check is run:
  ```bash
  rg 'docs/reference/event-bus\.md' --type md docs/ CLAUDE.md
  ```
  Must show at least the `CLAUDE.md` entry + the link from `docs/superpowers/roadmap/event-bus/specs/DESIGN.md` (which references it in §Acceptance criteria).

**Steps**:

- [ ] Write the reference doc.
- [ ] Update `CLAUDE.md` Reference Index.
- [ ] Run the link grep.
- [ ] **`git add -f docs/reference/event-bus.md`** — the global `~/.gitignore` blocks `docs/` (see CLAUDE.md §Gotchas: "Global `~/.gitignore` has a `docs/` rule — use `git add -f` for files in `docs/`"). Without `-f`, the new doc is silently absent from the commit and the link-check would fail in CI.
- [ ] Verify staging: `git status --short docs/reference/event-bus.md` shows `A` (added), not blank.
- [ ] `make check` green (docs files don't affect lint/tests but the gate must still pass).
- [ ] Commit: `docs(event-bus): add reference documentation for EventBus API + event catalog`.

---

## Sub-phase 5.6 — Phase 5 gate + acceptance-criteria audit (feature merge gate)

This sub-phase combines what earlier drafts split into 5.6 (audit-only, potentially zero commits) and 5.7 (phase gate). Combining them avoids a sub-phase that may produce zero commits (which breaks `/implement:sub-phase`'s 1-sub-phase = 1-commit assumption) and keeps the acceptance-criteria audit on the same commit as the gate verification.

**Hard verification gate** (this is the **feature merge gate**, not just a phase gate):

1. **`make lint`** → zero errors.
2. **`make test`** → all tests pass. Final tally: baseline + **~177 new tests** (sum of explicit per-phase deltas: Phase 1 ~57 + Phase 2 ~30 + Phase 3 ~50 + Phase 4 ~30 + Phase 5 ~10). Verify by `make test 2>&1 | tail -5 | grep passed` and comparing against the baseline recorded in INDEX Pre-flight #3.
3. **`make check`** → green.
4. **Module size budget** (DESIGN table) — every module within its cap:
   - `core/event_bus.py` ≤ 400.
   - `core/app_context.py` ≤ 80.
   - `pipeline_events.py` ≤ 150.
   - `dispatch/events.py` ≤ 50.
   - `core/circuit.py` ≤ 350 (with events embedded).
   - `indexer/events.py` ≤ 60.
   - `trailers/events.py` ≤ 30.
   - `events/__init__.py` ≤ 100.
   - `subscribers/rich_console.py` ≈ 180.
   - `subscribers/telegram.py` ≤ 200.
   - `subscribers/debug_log.py` ≤ 40.
   - `tests/fixtures/event_bus.py` ≤ 80.
   - `tests/fixtures/event_samples.py` ≤ 150.
   - `tests/architecture/test_app_context_boundary.py` ≤ 80.
5. **Sweep greps — all zero** (use `rg --type py` always, never bare `grep -r`):
   - Phase 3 grep set (already zero).
   - `rg 'event_bus: EventBus \| None' --type py personalscraper/` → 0.
   - `rg --type py 'CircuitBreaker\(' personalscraper/ tests/ | grep -v 'event_bus='` → 0.
6. **Event catalog: exactly the 13 v1 events, no missing, no extra, `Event` NOT in registry**:
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
   assert 'Event' not in actual, 'Event base must not register itself (Invariant 9)'
   print('OK 13 events:', sorted(actual))
   "
   ```
   (Identical command to Phase 4.6 §5; re-run here as a feature-merge gate.)
7. **Factories complete**: `pytest tests/fixtures/test_factories_registry.py::test_every_event_has_factory -v` green. (`test_every_event_has_factory` iterates the production-module-filtered registry per Invariant 9 / Phase 1.6, so pytest-collected test stubs do NOT pollute the assertion — the iteration sees exactly 13 entries regardless of collection order.)
8. **Envelope round-trip**: parametrized test green for all 13.
9. **AST boundary test green**.
10. **AppContext allowlist live**: `pytest tests/architecture/test_app_context_boundary.py::test_allowlist_entries_are_live -v` green.
11. **Smoke imports**: `python -c "import personalscraper; from personalscraper.events import *"` succeeds.
12. **Visual regression**: RichConsoleSubscriber snapshot test green.
13. **DESIGN §Acceptance criteria audit** — walk the full checklist (replaces the earlier audit-only sub-phase):
    - [ ] All five phases gate-green: re-run `make check` from the top; all green.
    - [ ] Legacy API removed (full grep — must return zero): `rg --type py 'PipelineObserver|notify_progress|StepEvent|from personalscraper\.observers' personalscraper/ tests/` → 0. (Use `rg --type py`, NOT bare `grep -r` — the latter scans the 14 GB fixture dir.)
    - [ ] Factories complete + round-trip green: `pytest tests/event_bus/test_pipeline_events.py::test_pipeline_events_envelope_roundtrip tests/core/test_circuit_events.py tests/indexer/test_disk_guard_events.py tests/indexer/test_scan_completed_events.py tests/dispatch/test_dispatch_events.py tests/trailers/test_trailer_events.py -v`.
    - [ ] AST boundary test green: `pytest tests/architecture/test_app_context_boundary.py -v`.
    - [ ] RichConsoleSubscriber snapshot matches the immutable baseline at `tests/snapshots/rich_console_canonical.txt` (the Sub-phase 3.5 test).
    - [ ] **Manual Telegram smoke test**: with a staging Telegram channel in `.env`, run `personalscraper run --dry-run` against a fixture triggering `PipelineEnded`, `StepErrored`, `CircuitBreakerOpened`, `DiskFullWarning` (use stubs). Verify all four alerts arrive. Document the result in the PR description.
    - [ ] `--verbose` produces structured event log: run `personalscraper run --verbose --dry-run` against a no-op fixture; assert `event_emitted` log lines appear for at least `PipelineStarted` and `PipelineEnded`.
    - [ ] Reference doc complete: re-read `docs/reference/event-bus.md`; every section listed in 5.5 present and non-empty.
    - [ ] Any audit failure is fixed IN this sub-phase + a regression test landed if relevant (Invariant 5). NEVER defer.
14. **Reference documentation present**: `ls docs/reference/event-bus.md` exists; entry in `CLAUDE.md` Reference Index present.
15. **No deferred work in `IMPLEMENTATION.md`** for the event-bus feature: read `IMPLEMENTATION.md`; ensure no "tests deferred", no "follow-up", no "TODO Phase N+1". The no-deferral invariant must be honoured.

**Steps**:

- [ ] Re-read each sub-phase 5.1–5.5; every checkbox checked.
- [ ] Run gate items 1–15; resolve any red (fix inline; never defer).
- [ ] Commit: `chore(event-bus): phase 5 gate — feature complete, mergeable`.

The PR is now ready for the `/implement:feature-pr` orchestration (push + create PR + CI poll) followed by `/implement:pr-review`.

---

## Roll-back plan

Phase 5 is **reversible** like Phases 1, 2, 4 — additive (DebugLogSubscriber + docs) and tightening (`| None` removal). A single revert of the Phase 5 commit range:

- Re-introduces `| None` defaults (production still works because every caller passes `event_bus=` already).
- Removes `DebugLogSubscriber` (the `--verbose` flag's pre-Phase-5 behavior is restored).
- Removes `docs/reference/event-bus.md` (no functional impact).

Phase 3 remains the point of no return. After merge to `main`, the project policy is **fix-forward only** (DESIGN §Rollback policy).

## Open questions left for this phase

DESIGN §Open Questions:

- **#1, #2**: resolved earlier.
- **#3 (WebSocketSubscriber prototype)**: marked NOT in committed plan. **Not done in this PR.** Postponed to the P2 Web UI feature. Document this explicitly in the PR description so reviewers don't ask for it.

No new open questions.
