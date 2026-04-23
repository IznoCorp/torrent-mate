# Implementation Progress — ext-staging

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Decouple Staging from Project — external staging path + config-driven dir names (minor)
**Version bump**: 0.3.0 → 0.4.0
**Branch**: feat/ext-staging
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/9
**Design**: docs/features/ext-staging/DESIGN.md
**Master plan**: docs/features/ext-staging/plan/INDEX.md

## Phases

| #   | Phase                              | File                         | Status |
| --- | ---------------------------------- | ---------------------------- | ------ |
| 1   | Config schema (additive)           | phase-01-config-schema.md    | [x]    |
| 2   | Sorter refactor + Settings cleanup | phase-02-sorter-refactor.md  | [x]    |
| 3   | Auto-create staging tree           | phase-03-auto-create.md      | [x]    |
| 4   | Repo cleanup (git rm --cached)     | phase-04-repo-cleanup.md     | [x]    |
| 5   | Docs + E2E + final gate            | phase-05-docs-e2e.md         | [x]    |
| 6   | PR fixes cycle 1                   | phase-06-pr-fixes-cycle-1.md | [ ]    |

## Review cycles

### Cycle 1

- Findings received: 18 (4 critical, 5 major, 5 medium, 4 minor)
- Retained: 12 (4 critical, 4 major, 3 medium, 1 minor)
- Ignored: 6 (out of scope or pre-existing)
- Fix phase created: phase-06-pr-fixes-cycle-1.md (6 sub-phases)
- Status: fix phase dispatched → awaiting /implement:phase

## Next action

All phases complete — run `/implement:feature-pr`.
