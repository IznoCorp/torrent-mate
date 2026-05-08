# Plan — test-coverage

> Implementation plan for the `test-coverage` feature. See [DESIGN.md](../DESIGN.md) for rationale.

## Phase types

- **infra** — scripts, Makefile, CI, hooks. No production-code changes.
- **bootstrap** — first design-contract test + 7th `/implement:check` step. Validates the pipeline end-to-end.
- **cycle** — feature coverage cycle: audit → tests → bump `fail_under`.
- **maintenance** — recurring audits, onboarding doc.

## Phases

| #   | Phase                                                                  | Type        | File                                                                   | Status |
| --- | ---------------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------- | ------ |
| 1   | Foundation — scripts + Makefile + baseline                             | infra       | [phase-01-foundation.md](phase-01-foundation.md)                       | [x]    |
| 2   | CI enforcement (test-cov + design-gaps + ratchet)                      | infra       | [phase-02-ci-enforcement.md](phase-02-ci-enforcement.md)               | [ ]    |
| 3   | Pre-commit hook via `core.hooksPath`                                   | infra       | [phase-03-pre-commit-hook.md](phase-03-pre-commit-hook.md)             | [ ]    |
| 4   | Bootstrap — first contract test + 7th check                            | bootstrap   | [phase-04-bootstrap.md](phase-04-bootstrap.md)                         | [ ]    |
| 5   | api-unify cycle (bootstrap markers, no threshold bump)                 | cycle       | [phase-05-api-unify-cycle.md](phase-05-api-unify-cycle.md)             | [ ]    |
| 6   | scraper cycle → `fail_under = 82`                                      | cycle       | [phase-06-scraper-cycle.md](phase-06-scraper-cycle.md)                 | [ ]    |
| 7   | dispatch + verify cycle → `fail_under = 85`                            | cycle       | [phase-07-dispatch-verify-cycle.md](phase-07-dispatch-verify-cycle.md) | [ ]    |
| 8   | trailers cycle → `fail_under = 87` + promote design-gaps to hard error | cycle       | [phase-08-trailers-cycle.md](phase-08-trailers-cycle.md)               | [ ]    |
| 9   | indexer cycle → `fail_under = 90`                                      | cycle       | [phase-09-indexer-cycle.md](phase-09-indexer-cycle.md)                 | [ ]    |
| 10  | remaining cleanup (stay at `fail_under = 90`, audit + skip_audit)      | cycle       | [phase-10-remaining-cleanup.md](phase-10-remaining-cleanup.md)         | [ ]    |
| 11  | Maintenance — 6-month audit + HOWTO                                    | maintenance | [phase-11-maintenance.md](phase-11-maintenance.md)                     | [ ]    |

## Standard sub-phase scaffolding

Every phase ends with a **gate sub-phase** that:

1. Runs `make check` (lint + test-cov + module-size + typed-api).
2. Runs `python3 scripts/audit_design_coverage.py` (warning-mode through cycle 3, strict from cycle 4).
3. Runs `python3 scripts/update_feature_map.py --check`.
4. Commits a milestone: `chore(test-coverage): phase N gate — <summary>`.

## Branch & commit convention

- **Branch**: `feat/test-coverage`. Created from `main` after `feat/api-unify` is merged.
- **Commits**: Conventional Commits with `(test-coverage)` scope.
- **Bump**: minor (Y+1) — 0.11.0 → 0.12.0 — declared in Phase 1 commit.

## Phase entry/exit criteria

Each phase file declares explicit:

- **Entry**: state of the repo at phase start (commit, prior phase done).
- **Exit**: deliverables, gate output, commits expected.
- **Effort**: rough wall-clock estimate (S < 1 h, M < 4 h, L < 1 day, XL ≥ 1 day).

## Rollback procedure

If a phase introduces a regression that escapes the gate:

1. `git revert` the phase milestone commit.
2. Re-run `make check` locally.
3. Open a follow-up issue describing the failure mode.
4. Resume from the previous phase gate (do not skip ahead).

If `fail_under` was bumped and the cycle retroactively fails (e.g. a flaky test surfaces post-merge), revert the threshold bump first; the `coverage-monotonic` CI step will accept this when the PR carries the `coverage-rollback` label.
