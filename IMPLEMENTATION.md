# Implementation Progress — test-coverage

> For Claude: read this file at session start. Current feature tracker.

**Codename**: `test-coverage`
**Feature**: Test Coverage & Design-Contract Testing (minor)
**Bump**: 0.11.0 → 0.12.0
**Branch**: feat/test-coverage
**Design**: docs/features/test-coverage/DESIGN.md
**Master plan**: docs/features/test-coverage/plan/INDEX.md
**PR**: _(created after last phase)_
**PR merge**: manual

## Phases

| #   | Phase                                                  | Type        | File                                                                                                    | Status |
| --- | ------------------------------------------------------ | ----------- | ------------------------------------------------------------------------------------------------------- | ------ |
| 1   | Foundation — scripts + Makefile + baseline             | infra       | [phase-01-foundation.md](docs/features/test-coverage/plan/phase-01-foundation.md)                       | [x]    |
| 2   | CI enforcement (test-cov + design-gaps + monotonic)    | infra       | [phase-02-ci-enforcement.md](docs/features/test-coverage/plan/phase-02-ci-enforcement.md)               | [x]    |
| 3   | Pre-commit hook via core.hooksPath                     | infra       | [phase-03-pre-commit-hook.md](docs/features/test-coverage/plan/phase-03-pre-commit-hook.md)             | [x]    |
| 4   | Bootstrap — first contract test + 7th check            | bootstrap   | [phase-04-bootstrap.md](docs/features/test-coverage/plan/phase-04-bootstrap.md)                         | [x]    |
| 5   | api-unify cycle (bootstrap markers, no bump)           | cycle       | [phase-05-api-unify-cycle.md](docs/features/test-coverage/plan/phase-05-api-unify-cycle.md)             | [x]    |
| 6   | scraper cycle → fail_under = 82 (bump deferred)        | cycle       | [phase-06-scraper-cycle.md](docs/features/test-coverage/plan/phase-06-scraper-cycle.md)                 | [x]    |
| 7   | dispatch + verify cycle → fail_under = 85              | cycle       | [phase-07-dispatch-verify-cycle.md](docs/features/test-coverage/plan/phase-07-dispatch-verify-cycle.md) | [ ]    |
| 8   | trailers cycle → fail_under = 87 + promote design-gaps | cycle       | [phase-08-trailers-cycle.md](docs/features/test-coverage/plan/phase-08-trailers-cycle.md)               | [ ]    |
| 9   | indexer cycle → fail_under = 90                        | cycle       | [phase-09-indexer-cycle.md](docs/features/test-coverage/plan/phase-09-indexer-cycle.md)                 | [ ]    |
| 10  | remaining cleanup (stay at fail_under = 90)            | cycle       | [phase-10-remaining-cleanup.md](docs/features/test-coverage/plan/phase-10-remaining-cleanup.md)         | [ ]    |
| 11  | Maintenance — 6-month audit + HOWTO                    | maintenance | [phase-11-maintenance.md](docs/features/test-coverage/plan/phase-11-maintenance.md)                     | [ ]    |

## Quality gate (every commit)

```bash
make check
python3 scripts/check-module-size.py
python3 scripts/check-typed-api.py
```

Every milestone commit (`chore(test-coverage): phase N gate — <summary>`) must pass:

1. `make lint` — ruff + mypy clean.
2. `make test-cov` — all tests pass at the current `fail_under`.
3. `make check` — composite gate.
4. Residual import grep (per phase plan, where applicable).
5. Smoke import: `python -c "import personalscraper"`.

See CLAUDE.md "Phase Gate Checklist (MANDATORY)" for the full protocol.

## Sub-phase → SHA mapping

### Phase 1 — Foundation

| Sub-phase | SHA       | Description                                                    |
| --------- | --------- | -------------------------------------------------------------- |
| 1.1       | `106114c` | rebaseline pyproject.toml with branch coverage (fail_under=80) |
| 1.2       | `a39e07d` | get_coverage_threshold.py helper                               |
| 1.3       | `11ac556` | \_codename_overrides.py table + resolve_codename()             |
| 1.4       | `42e5d6d` | update_feature_map.py + 23 unit tests                          |
| 1.5       | `bb9d2d8` | audit_design_coverage.py + 28 unit tests                       |
| 1.6       | `1179849` | Makefile test-unit/test-integration/test-cov targets           |

**Note**: actual branch-coverage baseline measured at 80.48 % (not the 44 % the
plan assumed). Phase 1 set `fail_under = 80`. Plan rescaled in commit `1dc7eac`
to `80 → 82 → 85 → 87 → 90` distributed over Phases 6/7/8/9.

### Phase 2 — CI enforcement

| Sub-phase | SHA       | Description                                                  |
| --------- | --------- | ------------------------------------------------------------ |
| 2.1       | `d83a45e` | wire `test` job to `make test-cov` + fork-aware codecov flag |
| 2.2       | `652f31d` | add `coverage-monotonic` job with `coverage-rollback` label  |
| 2.3       | `652ee32` | add `design-gaps` job (warning-mode, continue-on-error)      |

### Phase 3 — Pre-commit hook

| Sub-phase | SHA       | Description                                                  |
| --------- | --------- | ------------------------------------------------------------ |
| 3.1       | `a09c16b` | hooks/pre-commit feature-map regenerator                     |
| 3.2       | `6f1bdbc` | hooks/install.sh (idempotent core.hooksPath setup)           |
| 3.3       | `910a45b` | document install in CLAUDE.md + README.md                    |
| 3.4       | (smoke)   | hook regenerates and stages map for staged test*design*\*.py |

### Phase 4 — Bootstrap

| Sub-phase | SHA                 | Description                                                                      |
| --------- | ------------------- | -------------------------------------------------------------------------------- |
| 4.1       | `f5d6608`           | capture phase-4 baseline of orphan design sections                               |
| 4.2/4.3   | `7abbd81`           | first design-contract test (api-unify circuit breaker) + auto-staged map by hook |
| 4.4       | `dcd7ff5` (.claude) | 7th `/implement:check` step — design-contract coverage                           |
| 4.5       | `063e311`           | HOWTO — 3-step contract-test guide                                               |

## Notes

- DESIGN + plan were prepared in advance (PR #19 final commit) per `/implement:prepare-feature`. `/implement:feature` skipped brainstorm + plan generation.
- Previous feature `api-unify` (PR #19, merged 2026-05-08) archived to `docs/archive/features/api-unify/` in the same commit that bumps version to 0.12.0.
