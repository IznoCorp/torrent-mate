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
| 5   | PR fixes cycle 1                  | phase-05-pr-fixes-cycle-1.md     | [ ]    |

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
- Status: fix phase dispatched → awaiting /implement:phase.

## Next action

Run `/implement:phase` to execute Phase 5 (PR fixes cycle 1).
