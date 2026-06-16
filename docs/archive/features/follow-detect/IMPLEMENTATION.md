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
| 6   | PR fixes cycle 1                   | phase-06-pr-fixes-cycle-1.md            | [x]    |
| 7   | PR fixes cycle 2                   | phase-07-pr-fixes-cycle-2.md            | [x]    |

## Review cycles

### Cycle 1

- Toolkit: 5 lenses on PR #200 (CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer, comment-analyzer.
- Findings received: ~20. Retained: 6 medium + minor doc touch-ups (all DESIGN-coherent; cadence subsystem is net-new). Ignored: 4.
- **Convergent top finding (4 lenses) — cadence dead-band:** the `CadenceConfig` validator allows `cutoff_days*24 >= last_tier` (`>=`, not `==`); a custom config with cutoff **beyond** the last tier opens a window `[last_tier_max, cutoff)` where an item matches no tier → `is_due_by_cadence` False **and** `is_past_cutoff` False → frozen forever (DEBUG-only). Canonical config (cutoff == last tier) is unaffected, but it is config-reachable. → F-A clamp to the last tier in that window.
- Retained: **F-A** dead-band fix · **F-B** `Cadence.__post_init__` invariant guard (illegal states unrepresentable) · **F-C** `cadence_from_json` defensive decode (latent unvalidated boundary, wired into service.py) · **F-D** not-due test pins `set_status` not-called · **F-E** validator rejection completeness (empty/non-positive) · **F-F** per-series cadence override exercised through the service · **F-G..K** doc accuracy (LOC figure, follow docstring, criteria_json note, architecture alignment) + cadence purity test.
- Ignored (documented): systemic-poll "no-coverage" signal (out of scope — needs an RP9 `poll_aired` contract change; per-series warnings already logged; DESIGN §10 chose per-series fail-soft) · redundant `store.follow.get` in `_resolve_profile` (pre-existing perf) · `--series` numeric-title shadowing (documented UX) · `db_path` WAL validator untested (pre-existing).
- Decision: **Case B**. Fix phase 6 created (6.1 cadence dead-band + VO guard, 6.2 defensive decode + branch pins, 6.3 docs + purity test).

### Cycle 2

- Toolkit: 4 lenses on the cycle-1 delta (PR #200, CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer.
- Cycle-1 fixes verdict: **correct + complete**. code-reviewer CLEAN (F-A/F-B/F-C empirically verified, canonical config unaffected); type-design **FD-01/FD-02 RESOLVED**, enforcement re-rated 4/10 → 9/10; silent-failure fail-soft "correct and complete" (28 adversarial blobs all → None, no AttributeError path since decode uses subscript not attribute). All cycle-1 tests mutation-proven (dead-band + per-series override fail against their bugs).
- Findings retained: **F-L** (medium — dropped per-series cadence override logs only the exception string, no series identity; unactionable when a producer ships → log `followed_id`/`title` at the service call site) · **F-M** (CadenceTier leaf guard → 10/10) · **F-N** (untested `TypeError` decode branch + misleading test docstring) · **F-O** (`match=` on guard tests) · **F-P** (strengthen the weak dead-band negative control).
- Ignored (documented): float-vs-int strictness on durations (pre-existing leniency; Pydantic coerces too; reviewers said don't gate) · single-tier dead-band (informational, no missed code path).
- Decision: **Case B**. Fix phase 7 created (7.1 observability + leaf guard, 7.2 test completeness).

### Cycle 3

- Toolkit: 3 lenses on the cycle-2 delta (PR #200, CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter.
- Verdict: **CONVERGED**. code-reviewer CLEAN (F-L fail-soft + identity log correct, no double-decode, no behavior change on the common cadence_json-None path; F-M leaf guard correct, cadence.py pure, no construction site breaks). pr-test: all 5 cycle-2 fixes sound + complete — both mutation claims empirically re-verified (removing the call-site log fails F-L; Cold→Hot fallback fails the strengthened dead-band control); `match=` strings aligned to real messages; TypeError branch + corrected docstring accurate. silent-failure: **FINDING 1 RESOLVED** (operator now gets `followed_id`+`title` on a dropped override), no new hidden failure, None-vs-rejected distinction exact.
- Findings: **0** critical / 0 major / 0 medium. Two MINOR advisories, both reviewers non-blocking: (1) the now-redundant non-positive tier checks inside `Cadence.__post_init__` are dead (the `CadenceTier` leaf guard fires first) — kept as intentional defense-in-depth; (2) the F-L caplog test asserts the event name, not the `title` kwarg — optional test-strength polish. Neither blocks merge.
- Decision: **Case A** — review clean. Loop exits.
- Status: clean — handed off for manual squash merge (merge_mode = manual).

## Next action

Review clean — **operator performs the manual squash merge** of PR #200, then run `/implement:archive`. (The assistant does not merge in manual mode.)
