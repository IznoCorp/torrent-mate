# Implementation Progress — follow-detect

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Follow D2: calendar-first detection → wanted enqueue + cadence backoff (minor)
**Version bump**: 0.31.0 → 0.32.0
**Branch**: feat/follow-detect
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/follow-detect/DESIGN.md
**Master plan**: docs/features/follow-detect/plan/INDEX.md

## Phases

| #   | Phase                              | File                                    | Status |
| --- | ---------------------------------- | --------------------------------------- | ------ |
| 1   | Cadence module + config + codec    | phase-01-cadence-module-config-codec.md | [x]    |
| 2   | Wanted dedup (`find`)              | phase-02-wanted-dedup.md                | [ ]    |
| 3   | DETECT logic + `follow detect` CLI | phase-03-detect-cli.md                  | [ ]    |
| 4   | Cadence-aware run loop             | phase-04-cadence-aware-run-loop.md      | [ ]    |
| 5   | Docs + ACCEPTANCE + gate           | phase-05-docs-acceptance-gate.md        | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Run `/implement:phase` to start Phase 2 (Wanted dedup `find`).
