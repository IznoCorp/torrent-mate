# Implementation Progress — registry

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Provider Registry (Scraper Orchestrator Decoupling) (minor)
**Version bump**: 0.15.1 → 0.16.0
**Branch**: feat/registry
**PR merge**: manual
**PR**: https://github.com/LounisBou/personal-scraper/pull/27
**Design**: docs/features/registry/DESIGN.md
**Master plan**: docs/features/registry/plan/INDEX.md

## Phases

| #   | Phase                                     | File                                      | Status |
| --- | ----------------------------------------- | ----------------------------------------- | ------ |
| 0   | New types, shells, characterization tests | phase-00-types-shells-characterization.md | [x]    |
| 1   | Boot wiring + chain migration             | phase-01-boot-wiring-chain.md             | [x]    |
| 2   | Scraper locked migration                  | phase-02-scraper-locked.md                | [x]    |
| 3   | Out-of-scraper consumers                  | phase-03-out-of-scraper.md                | [x]    |
| 4   | Cleanup, observability, docs              | phase-04-cleanup-obs-docs.md              | [x]    |

## Baseline measurements (Phase 0 sub-phase 0.6)

Pinned values for ACC criteria in `docs/features/registry/ACCEPTANCE.md`:

- `REGISTRY_UNIT_TEST_COUNT` = **40** (registry unit-test count via `pytest tests/unit/api/metadata/registry/ --collect-only`)
- `BASELINE_PASS_COUNT` = **315** (full `pytest tests/e2e/ tests/integration/` baseline pass count before Phase 1 migration)
- `TMDB_TVDB_TEST_FILE_COUNT` = **30** (number of test files referencing `TMDBClient | TVDBClient | self._tmdb | self._tvdb`; informs Phase 1+3 migration scope)

These integers MUST replace the `${...}` placeholders in `ACCEPTANCE.md` (SH-16 deterministic-output rule). Re-measure if Phase 1 migration changes the unit-test count.

## Review cycles

_(filled by /implement:pr-review — max 3 cycles)_

## Next action

All phases complete — run `/implement:feature-pr` to create the pull request.
