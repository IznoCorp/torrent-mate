# Implementation Progress — follow-detect

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Follow D2: calendar-first detection → wanted enqueue + cadence backoff (minor)
**Version bump**: 0.31.0 → 0.32.0
**Branch**: feat/follow-detect
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/200
**Design**: docs/features/follow-detect/DESIGN.md
**Master plan**: docs/features/follow-detect/plan/INDEX.md

## Phases

| #   | Phase                              | File                                    | Status |
| --- | ---------------------------------- | --------------------------------------- | ------ |
| 1   | Cadence module + config + codec    | phase-01-cadence-module-config-codec.md | [x]    |
| 2   | Wanted dedup (`find`)              | phase-02-wanted-dedup.md                | [x]    |
| 3   | DETECT logic + `follow detect` CLI | phase-03-detect-cli.md                  | [x]    |
| 4   | Cadence-aware run loop             | phase-04-cadence-aware-run-loop.md      | [x]    |
| 5   | Docs + ACCEPTANCE + gate           | phase-05-docs-acceptance-gate.md        | [x]    |
| 6   | PR fixes cycle 1                   | phase-06-pr-fixes-cycle-1.md            | [ ]    |

## Review cycles

### Cycle 1

- Toolkit: 5 lenses on PR #200 (CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer, comment-analyzer.
- Findings received: ~20. Retained: 6 medium + minor doc touch-ups (all DESIGN-coherent; cadence subsystem is net-new). Ignored: 4.
- **Convergent top finding (4 lenses) — cadence dead-band:** the `CadenceConfig` validator allows `cutoff_days*24 >= last_tier` (`>=`, not `==`); a custom config with cutoff **beyond** the last tier opens a window `[last_tier_max, cutoff)` where an item matches no tier → `is_due_by_cadence` False **and** `is_past_cutoff` False → frozen forever (DEBUG-only). Canonical config (cutoff == last tier) is unaffected, but it is config-reachable. → F-A clamp to the last tier in that window.
- Retained: **F-A** dead-band fix · **F-B** `Cadence.__post_init__` invariant guard (illegal states unrepresentable) · **F-C** `cadence_from_json` defensive decode (latent unvalidated boundary, wired into service.py) · **F-D** not-due test pins `set_status` not-called · **F-E** validator rejection completeness (empty/non-positive) · **F-F** per-series cadence override exercised through the service · **F-G..K** doc accuracy (LOC figure, follow docstring, criteria_json note, architecture alignment) + cadence purity test.
- Ignored (documented): systemic-poll "no-coverage" signal (out of scope — needs an RP9 `poll_aired` contract change; per-series warnings already logged; DESIGN §10 chose per-series fail-soft) · redundant `store.follow.get` in `_resolve_profile` (pre-existing perf) · `--series` numeric-title shadowing (documented UX) · `db_path` WAL validator untested (pre-existing).
- Decision: **Case B**. Fix phase 6 created (6.1 cadence dead-band + VO guard, 6.2 defensive decode + branch pins, 6.3 docs + purity test).

## Next action

Execute phase 6 (`/implement:phase`), then re-poll CI + cycle-2 re-review.
