# Implementation Progress — grab-core

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP5b — shared grab core (download orchestrator + acquisition service) + RP3a fold-in (minor)
**Version bump**: 0.27.0 → 0.28.0
**Branch**: feat/grab-core
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/grab-core/DESIGN.md (hardened by adversarial review — see DESIGN §15)
**Master plan**: docs/features/grab-core/plan/INDEX.md

## Phases

| #   | Phase                                                              | File                      | Status |
| --- | ------------------------------------------------------------------ | ------------------------- | ------ |
| 1   | RP3a vocab (Resolution + QualityProfile + SourceCriteria)          | phase-01-vocab.md         | [x]    |
| 2   | Cross-tracker dedup (search_candidates + keys + -QTZ golden)       | phase-02-dedup.md         | [x]    |
| 3   | Hard-filters (resolution ordinal + anchored audio regex)          | phase-03-filters.md       | [x]    |
| 4   | Orchestrator (GrabOrchestrator chain + failure taxonomy + events) | phase-04a-orchestrator.md | [x]    |
| 5   | Service + state machine + wiring (claim/mark_grabbed + GrabCore)   | phase-04b-service.md      | [x]    |
| 6   | CLI (personalscraper grab + --dry-run + --limit)                  | phase-05-cli.md           | [x]    |
| 7   | Docs + ACCEPTANCE + gate                                           | phase-06-gate.md          | [x]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

All phases complete — run `/implement:feature-pr` (local gate + push + PR + CI).
