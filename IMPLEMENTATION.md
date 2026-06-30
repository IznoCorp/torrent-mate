# Implementation Progress — index-sync

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Post-dispatch index maintenance hook
**Type**: feat
**Version bump**: 0.37.0 → 0.38.0 (minor)
**Branch**: feat/index-sync
**PR merge**: auto
**PR**: https://github.com/IznoCorp/personal-scraper/pull/211
**Design**: docs/features/index-sync/DESIGN.md
**Master plan**: docs/features/index-sync/plan/INDEX.md

## Phases

| #   | Phase                                        | File                          | Status |
| --- | -------------------------------------------- | ----------------------------- | ------ |
| 1   | Core function + config + flag + unit tests   | phase-01-core-function.md     | [x]    |
| 2   | Wiring + integration + regression + ACC gate | phase-02-wiring-acceptance.md | [x]    |

## Review cycles

### Cycle 1 (PR #211) — 3-reviewer pass (code-reviewer + silent-failure-hunter + pr-test-analyzer)

Findings retained + fixed (commits 40806588..f380bae4):

- **CRITICAL** — `dispatch --dry-run` mutated the DB (touched_disks non-empty under dry-run, no guard) → gated both call sites on `not dry_run` (A).
- **MAJOR** — auto full-scan fallback fired on every dispatch (counted release_id IS NULL before relink + 744 standing orphans → library-wide full scan ~12min each time) → **removed the auto fallback** per operator decision 2026-06-30; rely on incremental scan + logged manual fallback (C; DESIGN Risk §1 updated).
- **MAJOR** — total relink/fix failure never surfaced the manual fallback (gate keyed only on per-file errors) → added relink_failed/fix_failed flags to the gate (D).
- **MAJOR** — touched-disks collection + flag>config resolution untested → extracted `collect_touched_disks` helper (DRY, B) + added wiring/dry-run/flag tests (F).
- **MEDIUM** — circular-import fragility in scan import → warm `personalscraper.indexer.cli` first (E); inconsistent isolation_level → autocommit symmetry (E); config_path not threaded → `resolve_config_path()` (E).
- Divergence check (relink/fix vs originals): clean. Regression assert strengthened to `release_id == 1` (F).

Verification: make lint green, 17 post_maintenance + e2e wiring tests pass, robust cold import confirmed, scope clean (8 files). Full gate re-run pre-push + CI.

## Next action

All phases complete — run /implement:feature-pr (push + PR + CI + squash merge auto).
