# Implementation Progress — event-bus

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `event-bus`
**Feature**: Event Bus (minor)
**Version bump**: 0.13.0 → 0.14.0
**Branch**: feat/event-bus
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/event-bus/DESIGN.md
**Master plan**: docs/features/event-bus/plan/INDEX.md

## NO DEFERRAL — ABSOLUTE PRIORITY (user-imposed)

**Every step is adapted. Every test is written. Nothing is skipped, nothing is
deferred, nothing is left for "later". Nothing is considered out of scope.**

This applies to every phase, every sub-phase, every commit. At each `/implement:check`
verification, design and plan compliance MUST be re-validated. Any drift from
DESIGN.md or any plan file is a gate failure to be fixed in place.

Banned tokens in any commit body, code comment, or doc edit produced during this
feature: `TODO`, `deferred`, `follow-up`, `next phase`, `next sub-phase`, `TBD`,
`to be done`, `to be implemented`, `parked`, `revisit`, `will be done`,
`forthcoming`, `pending`, `out of scope`, `later`. The exhaustive list and the
gate-time grep live in INDEX.md Invariant 3 §10. Paraphrasing the deferral is
also a violation; new evasive vocabulary discovered in review extends the list
in the same fix commit.

Reference: INDEX.md Invariant 1 (NO DEFERRAL — absolute) and DESIGN.md §"NO
DEFERRAL — MANDATORY".

## Phases

| #   | Phase                                  | Type    | File                                                                                                        | Status |
| --- | -------------------------------------- | ------- | ----------------------------------------------------------------------------------------------------------- | ------ |
| 1   | Foundation (standalone)                | core    | [phase-01-foundation.md](docs/features/event-bus/plan/phase-01-foundation.md)                               | [x]    |
| 2   | AppContext + StepContext slim          | core    | [phase-02-app-context-step-context.md](docs/features/event-bus/plan/phase-02-app-context-step-context.md)   | [x]    |
| 3   | Pipeline event migration + subscribers | migrate | [phase-03-pipeline-events-migration.md](docs/features/event-bus/plan/phase-03-pipeline-events-migration.md) | [ ]    |
| 4   | Cross-cutting events                   | core    | [phase-04-cross-cutting-events.md](docs/features/event-bus/plan/phase-04-cross-cutting-events.md)           | [ ]    |
| 5   | Required-bus tightening + CLI polish   | polish  | [phase-05-required-bus-cli-polish.md](docs/features/event-bus/plan/phase-05-required-bus-cli-polish.md)     | [ ]    |

Total sub-phases: **42** (per INDEX.md). Estimated commits: **42–49**.

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
python3 scripts/check-typed-api.py
```

Every milestone commit (`chore(event-bus): phase N gate — <summary>`) must pass:

1. `make lint` — ruff + mypy clean.
2. `make test` — all tests pass.
3. `make check` — composite gate.
4. Skip / xfail baseline unchanged (see INDEX.md Pre-flight #9).
5. Per-phase targeted greps (see each phase file).
6. Module size budget respected (per DESIGN.md).
7. Smoke import: `python -c "import personalscraper"`.

See CLAUDE.md "Phase Gate Checklist (MANDATORY)" and INDEX.md Invariant 3 for the full protocol.

## Sub-phase → SHA mapping

### Phase 1 — Foundation

| Sub-phase | SHA       | Description                                                           |
| --------- | --------- | --------------------------------------------------------------------- |
| pre-1.1   | `505596c` | Pre-flight baselines (tests=3738, skip=6, notify_progress=46/8 files) |
| 1.1       | `08616a3` | Event base + current_correlation_id ContextVar (10 tests)             |
| 1.2       | `28e4121` | EventBus.subscribe/unsubscribe + SubscriptionToken (COW) (7 tests)    |
| 1.3       | `f694070` | EventBus.emit + MRO cache + zero-alloc fast path (10 tests)           |
| 1.4       | `492ac24` | Error isolation + re-entrant emit safety (6 tests)                    |
| 1.5       | `6acfa18` | event_to_dict pure-payload JSON encoder (12 tests)                    |
| 1.6       | `92fad12` | event_to_envelope/from_envelope + class registry (12 tests)           |
| 1.7       | `a1e7d4c` | correlation_id ContextVar capture semantics (8 tests)                 |
| 1.8       | `026fda6` | CollectingSubscriber + factories registry mechanism (9 tests)         |
| 1.9       | `aae849e` | Phase 1 gate (no new code, all 10 verification items green)           |

### Phase 2 — AppContext + StepContext slim (DONE — all 9 sub-phases)

| Sub-phase | SHA             | Description                                                              |
| --------- | --------------- | ------------------------------------------------------------------------ |
| 2.1       | `343001f`       | AppContext frozen dataclass at core/app_context.py (3 tests)             |
| 2.2a      | `fcc68dd`       | StepContext gains app + run_id, legacy mirrors via **post_init** (6)     |
| 2.2b      | `4b90106`       | Sweep ctx.config/settings → ctx.app.config/settings (27 sites)           |
| 2.2c      | `be8a52e`       | Drop legacy mirrors from StepContext; final 2.2 shape                    |
| pre-2.4   | `248f29d`       | Pre-flight #7 — canonical Rich Console snapshot baseline                 |
| 2.3       | `879cda8`       | Pipeline.\_\_init\_\_(app), per-run run_id, ContextVar bind (9 tests)    |
| 2.4       | `e1b4a17`       | CLI entry builds AppContext via `_build_app_context` (3 tests)           |
| 2.5       | `5969555`       | launchd scan + 4 trailers commands rewired; bus to orchestrators (12 t.) |
| 2.6       | `28d4d9a`       | tests/architecture/test_app_context_boundary.py (AST allowlist, 5 t.)    |
| 2.7       | _(this commit)_ | Phase 2 gate (10 verification items)                                     |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Resumption snapshot — read FIRST when resuming

**HEAD SHA**: `eea8a5a` — `docs(event-bus): record sub-phase progress 2.1-2.2c`
**Branch**: `feat/event-bus` — fully synced with `origin/feat/event-bus` (0 ahead, 0 behind).
**Working tree**: clean (`git status --porcelain` returns empty).
**Last successful gate**: full `make check` green (3816 passed, 3 skipped, coverage 91.24%).

**Captured baselines (locked at feature start, see INDEX Pre-flight):**

- `make test` baseline: **3738 passed, 3 skipped** at commit `55f758a` (feature activation).
- Current `make test`: **3816 passed, 3 skipped** (= **+78 new event-bus tests**, well above the +50 floor for Phase 1.9 gate; Phase 2 has added 9 tests so far across 2.1 + 2.2a + 2.2c).
- `make check` exit 0 (1 pre-existing soft-warn on `personalscraper/scraper/tv_service.py: 819 LOC`, threshold 800/1000 — not a blocker).
- Skip / xfail decorator count: **6** (unchanged — Invariant 3 §3 baseline).
- `notify_progress` call sites in production: **46** across **8** files (Phase 3.4 / 3.7b gate target — see INDEX Pre-flight #8 for the file list).
- Module size: `personalscraper/core/event_bus.py` 366 LOC (budget 400),
  `personalscraper/core/app_context.py` 43 LOC (budget 80),
  `tests/fixtures/event_bus.py` 66 LOC (budget 80).

**Where we stopped:** end of Phase 2 sub-phase 2.2c. Phase 2 row is still `[ ]`
in the Phases table because sub-phases 2.3 → 2.7 remain. Re-invoking
`/implement:phase` will detect Phase 2 as the next `[ ]` row and resume from
sub-phase 2.3 (the first pending sub-phase per the Sub-phase → SHA mapping
above — every prior sub-phase has a real SHA).

## Next action — concrete resumption protocol

When `/implement:phase` is re-invoked after `/clear`, execute in this order:

### Step A — Pre-flight #7 (BEFORE any Phase 2.4 commit)

The canonical Rich Console snapshot baseline (INDEX.md Pre-flight #7) was NOT
recorded in the original Phase 1 pre-flight. Its consumers are sub-phases
**2.4** (visual smoke after Pipeline refactor), **3.5** (RichConsoleSubscriber
visual match), and **3.9** (Phase 3 gate visual regression). It must land
**before** any code change that touches `personalscraper/observers/rich_console.py`
or the CLI bootstrap that builds it (i.e. before sub-phase 2.4).

Procedure (per INDEX.md Pre-flight #7 — verbatim):

1. Create `tests/snapshots/_canonical_sequence.py` — a hand-crafted
   `CANONICAL_SEQUENCE: list[tuple[str, tuple]]` covering every code path of
   `RichConsoleObserver` (9 step icons + 1 unknown step for the icon-default
   branch, all 10 status values for `on_progress`, mixed-count `StepReport`s,
   `on_step_error`, `on_pipeline_end` with both OK + ERRORS variants and
   both seconds-only + minutes+seconds durations). Use deterministic
   `Console(width=120, color_system=None, force_terminal=False, file=StringIO(), record=True)`.
2. Create `tests/snapshots/test_record_baseline.py` — one-shot recorder.
3. Run once → write `tests/snapshots/rich_console_canonical.txt` (the
   immutable baseline). Verify `coverage report --include='.../rich_console.py'`
   shows **100% line coverage** of `personalscraper/observers/rich_console.py`.
4. Delete `test_record_baseline.py` in the same commit; KEEP `_canonical_sequence.py`
   (Phase 2.4 + 3.5 + 3.9 replay it).
5. Commit: `chore(event-bus): record canonical Rich Console snapshot baseline (Pre-flight #7)`.

### Step B — Sub-phase 2.3 (Pipeline.**init**(app))

Plan: `docs/features/event-bus/plan/phase-02-app-context-step-context.md`
(read sub-phase 2.3 starting around line 215).

**Refactor target**: `Pipeline.__init__(app: AppContext)` (single positional
arg). All run-scope flags (`dry_run`, `interactive`, `verbose`) and the
legacy `observers` tuple move to `Pipeline.run(*, dry_run=…, interactive=…,
verbose=…, observers: tuple[PipelineObserver, ...] = ())` as keyword-only
parameters. `Pipeline.run` generates a fresh `run_id = uuid4()` per call,
binds `current_correlation_id.set(str(run_id))` in a try/finally, and
threads both into `StepContext`.

**Construction sites to migrate (39 total — verified at HEAD `eea8a5a`):**

```bash
rg 'Pipeline\(' --type py personalscraper/ tests/
```

Files affected (one-time scripted sweep recommended — most call-sites follow
the pattern `Pipeline(pipeline_config, pipeline_settings, observers=[...])`
which becomes
`Pipeline(app=AppContext(config=pipeline_config, settings=pipeline_settings, event_bus=EventBus()))`

- moves run-scope kwargs into the `.run(...)` call):

* `personalscraper/commands/pipeline.py` (1 site at line ~335 — production CLI)
* `tests/test_pipeline.py` (~8 sites)
* `tests/test_pipeline_orchestration.py`
* `tests/test_pipeline.py`
* `tests/integration/test_full_pipeline.py`
* `tests/resilience/test_pipeline_double_run.py`
* `tests/unit/test_pipeline_headless.py`
* `tests/unit/test_pipeline_with_observer.py`

**8 plan-mandated tests** to add (per phase-02-…md sub-phase 2.3):
`test_pipeline_init_takes_app_context_only`,
`test_pipeline_run_accepts_observers_kwarg`,
`test_pipeline_run_propagates_observers_to_step_context`,
`test_pipeline_run_generates_unique_run_id`,
`test_pipeline_run_binds_current_correlation_id_during_run`,
`test_pipeline_run_resets_correlation_id_after_run`,
`test_pipeline_run_resets_correlation_id_after_exception`,
`test_pipeline_run_propagates_run_id_to_step_context`.

Commit: `refactor(event-bus): Pipeline accepts AppContext; generates run_id and binds ContextVar`.

### Step C — Continue Phase 2 sub-phases 2.4 → 2.7

Then 2.4 (CLI entry — see Pre-flight probe inside the plan to decide
SKIP-CLI vs TOUCH-CLI), 2.5 (launchd + trailers), 2.6 (AST boundary test),
2.7 (Phase 2 gate). After 2.7 commit + `git push` (per the user-imposed
push-between-phases rule, see `~/.claude/projects/.../memory/feedback_event_bus_no_deferral.md`).

### Step D — Phases 3 → 5

Continue `/implement:phase` until all phases marked `[x]`. The skill chains
into `/implement:feature-pr` automatically at the last phase (CI poll +
PR creation), then `/implement:pr-review` for the review/fix loop. The PR
will be merged squash via the `manual` strategy chosen at feature activation.

## Push convention (user-imposed)

`git push` to `origin/feat/event-bus` after **each phase-gate commit**
(`chore(event-bus): phase N gate — …`). Do NOT push between sub-phases.
The pre-push hook runs ruff + format + logging audit + mypy + pytest before
allowing the push — keep all 5 green at every phase gate. (Mid-phase pushes
are allowed only as a backup measure when ending a session, as was done at
`eea8a5a` to preserve the in-progress Phase 2 work.)
