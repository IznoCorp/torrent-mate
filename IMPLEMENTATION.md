# Implementation Progress — follow-list

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Follow D1 — followed-series list (store CRUD + `follow` CLI) (minor)
**Version bump**: 0.28.0 → 0.29.0
**Branch**: feat/follow-list
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/197
**Design**: docs/features/follow-list/DESIGN.md
**Master plan**: docs/features/follow-list/plan/INDEX.md

## Phases

| #   | Phase                                                       | File               | Status |
| --- | ----------------------------------------------------------- | ------------------ | ------ |
| 1   | Store CRUD (_FollowSubStore completion + Protocol)          | phase-01-store.md  | [x]    |
| 2   | Title resolution helper (fail-soft metadata lookup)         | phase-02-title.md  | [x]    |
| 3   | follow CLI command group (add/list/remove)                  | phase-03-cli.md    | [x]    |
| 4   | Docs + ACCEPTANCE + gate                                    | phase-04-gate.md   | [x]    |
| 5   | PR review fixes — cycle 1                                    | phase-05-pr-fixes-cycle-1.md | [x]    |

## Review cycles

### Cycle 1

- Toolkit: code-reviewer + pr-test-analyzer on PR #197 (CI SUCCESS). Suite confirmed strong + non-vacuous; dedup/reactivate state machine + fail-soft resolver correct for single-id. Retained findings (design-conformant — match the tvdb-primary rule / close test gaps; NO design contradiction):
  - **C1 (major)** `find_by_ref` keys on the EXACT canonical media_ref_json tuple → cross-key blind spot (VERIFIED): a series followed with `--tvdb X --tmdb Y` is NOT found by `find_by_ref(tvdb=X)` → `follow remove --tvdb X` says "not found" AND a re-`follow add --tvdb X` creates a DUPLICATE row. DESIGN §4 says tvdb primary → find_by_ref must match on the primary available id (tvdb→tmdb→imdb), not the exact tuple.
  - **C2 (major)** `follow remove --id <rowid>` branch (get vs find_by_ref) entirely untested — a user-facing input mode that would regress silently.
  - m1 (medium) already-inactive `follow remove` (no 2nd SeriesUnfollowed) untested. m2 (medium) resolver empty/None-title fall-through untested.
- Decision: **Case B**. Fix phase 5 executed (1 commit `a0724a4c`): **C1** find_by_ref now matches on the primary available id via `json_extract` ($.tvdb_id→tmdb→imdb, ORDER BY id LIMIT 1) — cross-key match fixed (verified: add tvdb+tmdb → find_by_ref(tvdb-only) matches; no false-merge; CLI remove --tvdb + re-add dedups, no duplicate row); **C2** remove --id test (branch was correct), **m1** already-inactive double-remove no-double-event test, **m2** resolver None/empty-title placeholder test. make check 6701 green. Merge = manual.

## Next action

All phases complete — run `/implement:feature-pr`.
