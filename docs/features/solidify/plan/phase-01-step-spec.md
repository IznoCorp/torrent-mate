# Phase 1 — Pipeline step-spec + shared reporter (T2)

## Gate

```bash
make lint && make test && make check

# Residual-import / dead-symbol greps (zero matches expected)
rg -n "def _to_step_report" -g '*.py' personalscraper/            # 0 — deleted, replaced by record()
rg -n "_to_step_report" -g '*.py' personalscraper/ tests/         # 0 — no callers of the removed helper

# Real per-item lifecycle: 'started' emitted before work on sort/dispatch/enforce (F8)
# (P1.3: the F8 regressions live in tests/event_bus/test_real_started_lifecycle.py)
command python -m pytest tests/event_bus/test_real_started_lifecycle.py -q --no-header | grep -E "passed"

# F2 / F3 regression tests (written test-first this phase)
command python -m pytest tests -k "standalone_dispatch and permit" -q --no-header | grep -E "passed"
command python -m pytest tests -k "full_run and revert and reclean" -q --no-header | grep -E "passed"

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-05 — reports contract load-bearing, >=9 Details populated)
command python3 - <<'EOF' && echo ACC-05-OK
import subprocess
out = subprocess.run(["rg", r"Details\(", "-t", "py", "personalscraper/",
                      "-g", "!api/**", "--count-matches"], capture_output=True, text=True).stdout
assert sum(int(l.rsplit(":",1)[1]) for l in out.strip().splitlines() if l) >= 9, out
EOF
```

## Objective

Give every pipeline step ONE owner of its policy and ONE reporter (DESIGN §5 T2). Add a
declarative `StepSpec` list so `Pipeline.run()` iterates specs (the no-verified-items
dispatch skip becomes a `skip_when` predicate routed through the normal `_run_step`
path); add `StepReport.merge()` + a shared `record(...)` helper that increments counters,
appends details, populates the typed `details_payload`, and emits the `ItemProgressed`
pair with a normalized status enum from **inside** the processing loops. Move
revert-unmatched-recleans and delete-permit resolution into single shared functions used
by both the Pipeline and CLI paths. Conformity fixes: **F8** (real `started`-before-work
lifecycle on sort/dispatch/enforce), **F2** (standalone `dispatch` resolves the same
delete permit as the full run), **F3** (full run reverts unmatched recleans).

## Findings addressed

PIPELINE-CORE-01 (per-step policy duplicated across 3 layers + drift), PIPELINE-CORE-03
(OCP: adding a step touches ≥5 registries; `run()` special-cases inline), PIPELINE-CORE-04
(every `run_*` hand-rolls results→StepReport + ItemProgressed), PIPELINE-CORE-05 (fake
post-hoc `started`), COMMANDS-CLI-01 (policy re-decided in the CLI layer), and
CROSS-CUTTING-01 (the `STEP_REPORT_CONTRACT` validation is not load-bearing until Details
payloads are populated).

## Code anchors (verified)

- `personalscraper/pipeline.py` (839 LOC): `run()` :273; inline no-verified-items dispatch
  skip synthesised at :518-540 (`self._log.warning("dispatch_skipped", ...)` then a hand-built
  `StepReport(name="dispatch", skip_count=1, ...)`); `_run_process_phase` :616 (runs
  clean/scrape/cleanup as three `_run_step` calls and does **NOT** call
  `_revert_unmatched_recleans` — the F3 gap); `_run_step` :682; `_with_details_payload` :667.
- `personalscraper/pipeline_steps.py` (462 LOC): `DEFAULT_STEPS: dict[str, PipelineStep]`
  :416; `DispatchStep` adapter :258 — resolves `acquire.delete_authority` and passes
  `permit=`/`recorder=` to `run_dispatch` (:274-289) — this is the injection the standalone
  CLI omits.
- `personalscraper/pipeline_protocol.py` (75 LOC): `StepContext` :16.
- `personalscraper/models.py`: `class StepReport` :63; `details_payload: dict[str, Any] | None = None` :112 (no `merge()` method today — added here).
- `personalscraper/pipeline_events.py`: `class ItemProgressed(Event)` :107; `status: str` :125.
- `personalscraper/reports/__init__.py`: `STEP_REPORT_CONTRACT: dict[str, type]` with 9 keys (ingest, sort, clean, scrape, cleanup, enforce, verify, trailers, dispatch) → payload classes in `personalscraper/reports/*.py`.
- Reference real-lifecycle emission (the pattern to generalise): `personalscraper/scraper/run.py:231` `event_bus.emit(ItemProgressed(step="scrape", item=item_name, status="started"))`. The fake post-hoc emitters are on sort/dispatch/enforce.
- `_to_step_report` (to delete, PIPELINE-CORE-04): present in `personalscraper/scraper/run.py`, `personalscraper/verify/run.py`, `personalscraper/dispatch/run.py`.
- Revert seam: `personalscraper/process/run.py::_revert_unmatched_recleans` :30, called by `run_process` at :331; the reclean rename record is produced in `personalscraper/process/reclean.py`.
- Permit gap: `personalscraper/commands/pipeline.py::dispatch` :345 calls `run_dispatch(settings, config=config, dry_run=dry_run, event_bus=app_context.event_bus)` at :370 — **no** `permit=`/`recorder=`, so `run_dispatch`'s defaults (`AllowAllPermit`, `personalscraper/dispatch/run.py:84-85`) apply. The full run injects them via `DispatchStep`.
- Sorter/Dispatcher process seams for in-loop emission: `personalscraper/dispatch/dispatcher.py::process` :200; sorter emission today at `personalscraper/sorter/run.py:23,56`; enforce entry `personalscraper/enforce/run.py::run_enforce` :24.

Constraint reminder: `run_dispatch` already receives `config` + `event_bus` but **not**
`AppContext` — do not pass AppContext into `dispatch/`/`sorter/`/`enforce/` (EventBus/AppContext
boundary rule). `event_bus` stays a REQUIRED parameter everywhere it flows.

## Tasks

1. **P1.1 — `StepReport.merge()` + normalized status enum.** In `personalscraper/models.py`, add `StepReport.merge(other) -> StepReport` (sum counters, concat details, combine `details_payload` dicts) and a `StepStatus` enum (or `Literal`) capturing the `ItemProgressed` status vocabulary (`started`, `scraped`/`sorted`/`dispatched`/`enforced`, `skipped`, `failed`). Unit test the merge algebra (identity, associativity on counters). Verify: `pytest tests -k "step_report_merge" -q`.
2. **P1.2 — Shared `record(...)` reporter.** Add `record(report, bus, *, step, item, status, detail=None, warning=None)` to `personalscraper/pipeline_protocol.py` (bus is a REQUIRED param): increments the right counter on `report`, appends `detail`/`warning`, and emits the `ItemProgressed` pair with the normalized status. Unit test emission order and counter effects with a fake bus. Verify: `pytest tests -k "record_reporter" -q`.
3. **P1.3 — F8 test-first: real `started` lifecycle.** Write failing tests asserting sort, dispatch and enforce each emit `ItemProgressed(status="started")` **before** the item's work (assert event ordering vs a side-effect marker). Prove they fail against current post-hoc emission. Then rewire `Sorter.process` / `Dispatcher.process` (:200) / the enforce sub-components to call `record(...)` inside the per-item loop, `started` first. Delete `_to_step_report` in `scraper/run.py`, `verify/run.py`, `dispatch/run.py` and route those through `record()`/finalizers. Verify: the F8 tests pass; `rg -n "_to_step_report" -g '*.py' personalscraper/ tests/` == 0.
4. **P1.4 — Populate typed Details payloads (ACC-05 / CROSS-CUTTING-01).** Make `record()`/step finalizers populate `StepReport.details_payload` with the `STEP_REPORT_CONTRACT` dataclass for each of the 9 steps, and make `Pipeline._with_details_payload` validation load-bearing (fail if a step returns without its typed payload where one is declared). Verify: the ACC-05 snippet above returns ≥9; add a test that a step with a missing/ mismatched payload type raises.
5. **P1.5 — Declarative `StepSpec` + spec-driven `run()`.** Add a `StepSpec` dataclass `(name, adapter, critical: bool, extras_key: str | None, skip_when: Callable[..., bool] | None, payload_type: type | None)` colocated with `DEFAULT_STEPS` in `personalscraper/pipeline_steps.py`, validated at import against the web stage catalog (catalog stays the single source of truth — assert every spec name is in the catalog). Rewrite `Pipeline.run()` to iterate the spec list; replace the inline dispatch-skip synthesis (:518-540) with a `skip_when` predicate that returns a skip report through the normal `_run_step` path (symmetric `StepStarted`/`StepCompleted` preserved). Verify: `pytest tests -k "pipeline_run or step_spec or stage_catalog" -q`; existing pipeline event-symmetry tests stay green.

   **P1.5-fix (post-gate):** Catalog agreement (spec names ⊆ STEP_TO_STAGE) is enforced at test tier, not at import time — the engine must never import ``personalscraper.web`` (layering rule DESIGN §9 wins over the DESIGN parenthetical). The import-time validator keeps only engine-internal checks (DEFAULT_STEPS + STEP_REPORT_CONTRACT). The test-tier guard ``tests/pipeline/test_step_spec.py::TestStepSpecStageCatalogAgreement`` and the extended web-layering guard in ``tests/architecture/test_layering.py`` (now also scans top-level ``personalscraper/*.py``) close the gap.
6. **P1.6 — F3 test-first: full run reverts unmatched recleans.** Write a failing test that a **full** `Pipeline.run` reverts a reclean rename that scrape failed to match (parity with the CLI `run_process` path). Prove it fails. Then extract ONE shared process-phase function (in `personalscraper/process/run.py`, e.g. `run_process_phase(...)`) that runs clean→scrape→cleanup and reverts unmatched recleans, called by BOTH `run_process` and `Pipeline._run_process_phase` (:616). Thread the reclean rename record across the clean→scrape boundary. Verify: F3 test passes; the CLI `run_process` behaviour is unchanged (characterization from P0 still green).
7. **P1.7 — F2 test-first: standalone dispatch resolves the delete permit.** Write a failing test that `personalscraper dispatch` (the CLI command) resolves and passes the same `permit`/`recorder` (from `acquire.delete_authority`) that the full-run `DispatchStep` injects. Prove it fails (current default `AllowAllPermit`). Then move permit/recorder resolution into a single owner (`run_dispatch` resolving from the acquire context it can already reach, or a shared resolver called by both `DispatchStep` and the CLI command at `commands/pipeline.py:370`). Verify: F2 test passes; the full-run permit behaviour is byte-identical.
8. **P1.8 — Post-dispatch maintenance single-owner (PIPELINE-CORE-01).** Move the post-dispatch maintenance triggering (currently duplicated in `commands/pipeline.py:387-395` and the full-run path) behind one function invoked by both; the CLI command and `DispatchStep` become thin callers. Verify: `pytest tests -k "post_dispatch_maintenance" -q`; no behaviour change to touched-disk collection.
9. **P1.9 — Green + module-size check.** Confirm `personalscraper/pipeline.py` and `pipeline_steps.py` stay ≤800 non-blank LOC after extraction (both are under 800 today; keep them there). Run the full gate. Verify: `python3 scripts/check-module-size.py` reports no NEW finding for these files.

## Non-goals

- Do not touch dispatch_movie/dispatch_tvshow *body* dedup or the destructive journal — that
  is P2 (F1). P1 only routes the standalone permit (F2) and adds the shared reporter.
- Do not decompose `run_ingest` (PIPELINE-CORE-06) — deferred to its owning batch; P1 stays
  within step-spec/reporter/policy scope.
- Do not change the CLI boundary scaffold (lock/journal/staging) — that is P3.
- Do not alter the stage catalog contents (single source of truth); only validate against it.

## Commit

```
test(solidify): failing regressions for F2 (standalone permit), F3 (full-run revert), F8 (real started)
refactor(solidify): StepReport.merge + record() reporter; in-loop ItemProgressed
refactor(solidify): declarative StepSpec drives Pipeline.run; skip via predicate
```

Phase-gate commit:

```
chore(solidify): phase 1 gate — step-spec + shared reporter + single-owner step policy (F2/F3/F8)
```
