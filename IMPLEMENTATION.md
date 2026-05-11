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
| 2   | AppContext + StepContext slim          | core    | [phase-02-app-context-step-context.md](docs/features/event-bus/plan/phase-02-app-context-step-context.md)   | [ ]    |
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

### Phase 2 — AppContext + StepContext slim (IN PROGRESS — 4 of 9 sub-phases)

| Sub-phase | SHA                | Description                                                          |
| --------- | ------------------ | -------------------------------------------------------------------- |
| 2.1       | `343001f`          | AppContext frozen dataclass at core/app_context.py (3 tests)         |
| 2.2a      | `fcc68dd`          | StepContext gains app + run_id, legacy mirrors via **post_init** (6) |
| 2.2b      | `4b90106`          | Sweep ctx.config/settings → ctx.app.config/settings (27 sites)       |
| 2.2c      | `be8a52e`          | Drop legacy mirrors from StepContext; final 2.2 shape                |
| 2.3       | _(pending)_        | Pipeline.**init**(app), per-run run_id, ContextVar bind (~39 sites)  |
| 2.4       | _(pending)_        | CLI entry builds AppContext (commands/pipeline.py)                   |
| 2.5       | _(pending)_        | launchd scan + trailers commands rewired                             |
| 2.6       | _(pending)_        | tests/architecture/test_app_context_boundary.py (AST allowlist)      |
| 2.7       | _(pending — gate)_ | Phase 2 gate (10 verification items)                                 |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Phase 1 complete (all 8 production sub-phases + gate green). Next:

1. **Pre-flight #7** — record the canonical Rich Console snapshot baseline
   (deferred from initial Pre-flight only because its consumers live in
   Phase 2.4 / 3.5 / 3.9; MUST land before Phase 2 sub-phase 2.4 commits).
2. **Phase 2 — AppContext + StepContext slim** — see
   `docs/features/event-bus/plan/phase-02-app-context-step-context.md`.
3. Continue with `/implement:phase` (chained automatically).
