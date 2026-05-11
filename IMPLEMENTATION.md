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
| 1   | Foundation (standalone)                | core    | [phase-01-foundation.md](docs/features/event-bus/plan/phase-01-foundation.md)                               | [ ]    |
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

_(filled by /implement:phase as sub-phases land)_

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 1 (Foundation). Pre-flight checks in
`docs/features/event-bus/plan/INDEX.md` (#1–#10) MUST be executed first —
record `<N_CALLS>`, `<N_FILES>`, `<SKIP_BASELINE>`, and the canonical Rich
Console snapshot baseline before any sub-phase commits.
