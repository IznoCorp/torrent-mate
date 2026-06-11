# Implementation Progress — grab-core

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP5b — shared grab core (download orchestrator + acquisition service) + RP3a fold-in (minor)
**Version bump**: 0.27.0 → 0.28.0
**Branch**: feat/grab-core
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/196
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
| 8   | PR review fixes — cycle 1                                          | phase-08-pr-fixes-cycle-1.md | [x]    |

## Review cycles

### Cycle 1

- Toolkit: 3 lenses (pr-test-analyzer, code-reviewer, silent-failure-hunter) on PR #196. The algos (dedup -QTZ, atomic claim, hard-filters, taxonomy) confirmed genuinely non-vacuous + mutation-sensitive; the §15 review-hardened decisions held (stage order, CircuitOpenError-separate, permissive defaults, seed-separation structural). Retained findings (all design-conformant — code doesn't match DESIGN §7/§6.2 intent; NO design contradiction):
  - **C1 (major)** hash-guard CONSULTATION missing — `grabbed_hash` is persisted (store) + read into the VO but NEVER consulted to short-circuit (verified: 0 reads in service/orchestrator/grab). DESIGN §7/§11(d): a re-run after the add→mark_grabbed crash window must not re-grab/re-emit. Untested crash path.
  - **C2 (major)** service batch loop has ZERO error isolation (verified: no try/except) — a mid-batch OperationalError (db-lock, DESIGN §6.2 = RETRYABLE) or JSONDecodeError (corrupt criteria_json) aborts the WHOLE run, leaves the item stuck 'searching', and suppresses the run_complete summary.
  - **M1 (medium)** the `followed_id` series-profile overlay branch (`_resolve_profile` follow-lookup + handoff) is never exercised end-to-end (every service test uses followed_id=None) — the per-series policy-enforcement seam is untested.
  - m1 (minor) orchestrator NEGATIVE test has 3 vacuous `seed_spy.*` assertions on an unwired mock (theatre; the real guarantee is the dep-scan + structural no-dep) → trim. m2 (minor) dedup silverleech provenance tier untested. m3 (minor) `info_hash or ""` masks a success-without-hash contract violation → log.
- Decision: **Case B**. Fix phase 8 executed (3 commits `c3cf2018`/`ef0a6d08`/`5db83c64`): **C1** emit-after-persist (the PREFERRED correct design — orchestrator no longer emits GrabSucceeded; service emits AFTER mark_grabbed → §11(d) crash window CLOSED: a mark_grabbed crash = no emit, stale-recovery re-grabs once via idempotent add) + hash-guard short-circuit; **C2** per-item try/except (OperationalError→retryable/skip+log, JSONDecodeError→abandon+log, batch never aborts, run_complete always fires); **M1** follow-overlay test (live lookup passes the 1080p floor to the orchestrator); m1 trimmed vacuous seed_spy asserts; m3 success-without-hash log. make check 6660 green. Independently verified emit-after-persist structure + C2 isolation. Merge = manual.

## Next action

All phases complete — run `/implement:feature-pr` (local gate + push + PR + CI).
