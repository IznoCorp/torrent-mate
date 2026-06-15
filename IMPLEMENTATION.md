# Implementation Progress — airing

> For Claude: read this file at session start. Current feature tracker.

**Feature**: RP9 — air-date set-poll (which followed episodes have aired) (minor)
**Version bump**: 0.30.0 → 0.31.0
**Branch**: feat/airing
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/199
**Design**: docs/features/airing/DESIGN.md
**Master plan**: docs/features/airing/plan/INDEX.md

## Phases

| #   | Phase                             | File                             | Status |
| --- | --------------------------------- | -------------------------------- | ------ |
| 1   | AiredEpisode VO + aired predicate | phase-01-aired-episode-vo.md     | [x]    |
| 2   | Set-poll service                  | phase-02-set-poll-service.md     | [x]    |
| 3   | Negative-boundary tests + wiring  | phase-03-negative-boundary.md    | [x]    |
| 4   | Docs + ACCEPTANCE + gate          | phase-04-docs-acceptance-gate.md | [x]    |
| 5   | PR fixes cycle 1                  | phase-05-pr-fixes-cycle-1.md     | [x]    |
| 6   | PR fixes cycle 2                  | phase-06-pr-fixes-cycle-2.md     | [x]    |

## Review cycles

### Cycle 1

- Toolkit: 5 lenses on PR #199 (CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter, type-design-analyzer, comment-analyzer.
- Findings received: ~20. Retained: 8 (0 critical, 0 major, 8 medium). Ignored: ~6 (out of scope/cosmetic).
- Retained (all DESIGN-coherent, no contradiction):
  - **F-A** `AiredEpisode.season` used provider-reported `ep.season_number` (defaults to 0) instead of the authoritative requested `season_num` — latent Decision-C/D2 routing bug (flagged by 3 lenses).
  - **F-B** double-parse + `# type: ignore[arg-type]` → parse-once, narrow, drop the ignore (mypy proves `air_date` non-None).
  - **F-C** per-season `season_provider_error` logged at `debug` w/o `exc_info` → bump to `warning` + `exc_info` on bare-Exception arms (kept DESIGN event names).
  - **F-D** module docstring wrongly listed `core.identity` import + omitted `api._contracts`.
  - **F-E** GAP-1 chain fall-through untested (mutation-survived). **F-F** GAP-2 per-season fail-soft untested. **F-G** GAP-4 no-tvdb_id skip untested. **F-H** GAP-5 multi-season aggregation untested (pins F-A).
- Ignored: `__post_init__` validation (F-A removes the smuggle at source), event rename (DESIGN names `poll_failed`), empty-fall-through log, `__all__` re-export, store-wanted tautology (layering test covers it).
- Decision: **Case B**. Fix phase 5 created (5.1 code, 5.2 tests).
- Status: fix phase complete — `1c1a5320` (code: season-source + parse-once + observability + docstring), `220a0bed` (5 tests). All 8 retained findings addressed. `make check` 6763 passed. Independent Opus probe re-confirmed all behaviors + season-source fix. Awaiting CI re-poll + cycle-2 re-review.

### Cycle 2

- Toolkit: 3 lenses on the cycle-1 delta (PR #199, CI green) — code-reviewer, pr-test-analyzer, silent-failure-hunter.
- Cycle-1 fixes verdict: **all correct + complete** (code-reviewer CLEAN; all 5 new tests mutation-sensitive — verified by mutation testing; season-source fix pins [0,0]≠[1,2]). No new critical/major, no regressions.
- Findings received: 2 (both medium, test-only — pin the cycle-1 fixes):
  - **F-I** no test pins the F-C observability fix (warning + exc_info) — a revert to debug would pass all 22 tests; repo rule "Test de régression par bug" applies.
  - **F-J** chain fall-through tested only on the empty branch; the DESIGN §4 error-then-fallback branch (primary raises → secondary tried) covered only transitively (GAP-2 two-layer ambiguity).
- Ignored/acceptable residual: F-2 empty-fall-through silence (DESIGN §6 governs only the exception arms; the mirror's `show_season_empty` is richer but not mandated — DESIGN-consistent residual, not a blocker).
- Decision: **Case B**. Fix phase 6 created (6.1 — 2 tests, no code change).
- Status: fix phase complete — `482ffbc7` (2 tests). F-I (caplog WARNING + exc_info regression test) + F-J (error-then-fallback chain branch). Both independently mutation-proven non-vacuous (debug-revert fails F-I). `make check` 6765 passed. Awaiting CI re-poll + cycle-3 re-review.

## Next action

All phases complete — run `/implement:feature-pr` (push cycle-2 fixes).
