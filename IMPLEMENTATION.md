# Implementation Progress — match-guard

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Scraper match guard for degenerate/truncated titles — directional length-ratio guard + episode-filename fallback (bugfix)
**Version bump**: 0.34.0 → 0.34.1
**Branch**: fix/match-guard
**PR merge**: manual
**PR**: _(created after last phase)_
**Design**: docs/features/match-guard/DESIGN.md
**Master plan**: docs/features/match-guard/plan/INDEX.md

## Phases

| #   | Phase                                                         | File                                  | Status |
| --- | ------------------------------------------------------------- | ------------------------------------- | ------ |
| 1   | Directional length-ratio guard in confidence path (Unit 1)    | phase-01-length-ratio-guard.md        | [ ]    |
| 2   | Episode-filename fallback for degenerate show titles (Unit 2) | phase-02-episode-filename-fallback.md | [ ]    |
| 3   | Phase gate — make check + AC-1..AC-7 re-exercise              | phase-03-gate.md                      | [ ]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

Run `/implement:phase` to start Phase 1.
