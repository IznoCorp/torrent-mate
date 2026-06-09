# Implementation Progress — acquire-lobe

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP5c — acquire/ lobe + single injection handle (minor)
**Version bump**: 0.24.0 → 0.25.0
**Branch**: feat/acquire-lobe
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/acquire-lobe/DESIGN.md
**Master plan**: docs/features/acquire-lobe/plan/INDEX.md

## Phases

| #   | Phase                                                             | File                             | Status |
| --- | ----------------------------------------------------------------- | -------------------------------- | ------ |
| 1   | acquire/ skeleton + AcquireStore + AcquireContext + close() tests | phase-01-package-skeleton.md     | [ ]    |
| 2   | build_acquire_context factory + tests                             | phase-02-factory.md              | [ ]    |
| 3   | AppContext swap + cli_helpers wiring + wiring tests               | phase-03-appcontext-wiring.md    | [ ]    |
| 4   | Layering guard extension (acquire/ → never triage)                | phase-04-layering-guard.md       | [ ]    |
| 5   | ACCEPTANCE.md + architecture.md update + make check gate          | phase-05-acceptance-docs-gate.md | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 3 cycles)_

## Next action

Run `/implement:phase` to start Phase 1.
