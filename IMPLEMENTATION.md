# Implementation Progress — rescrape-target

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Targeted + incremental library re-scrape (minor)
**Version bump**: 0.35.1 → 0.36.0
**Branch**: feat/rescrape-target
**PR merge**: auto
**PR**: _(created after last phase)_
**Design**: docs/features/rescrape-target/DESIGN.md
**Master plan**: docs/features/rescrape-target/plan/INDEX.md

## Phases

| #   | Phase                     | File                       | Status |
| --- | ------------------------- | -------------------------- | ------ |
| 1   | item-id targeting         | phase-01-item-id.md        | [x]    |
| 2   | date-refreshed population | phase-02-date-refreshed.md | [x]    |
| 3   | gate                      | phase-03-gate.md           | [x]    |

## Review cycles

_(filled by implement:pr-review — max 5 cycles)_

## Next action

All phases complete — run `/implement:feature-pr` (push + PR + CI + auto-merge).

> Gate: AC-1/2/4 live-verified (targeting/bypass/mutual-exclusion), AC-5 unit-tested, AC-7 `make check` green (6948 passed). AC-3 (real La Linea re-scrape) + AC-6 (no-filter incremental, needs a live scan) deferred to post-merge validation. Scan cron stays OFF until validated.
