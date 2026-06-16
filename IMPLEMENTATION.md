# Implementation Progress — match-guard

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Scraper match guard for degenerate/truncated titles — directional length-ratio guard + episode-filename fallback (bugfix)
**Version bump**: 0.34.0 → 0.34.1
**Branch**: fix/match-guard
**PR merge**: manual
**PR**: https://github.com/IznoCorp/personal-scraper/pull/203
**Design**: docs/features/match-guard/DESIGN.md
**Master plan**: docs/features/match-guard/plan/INDEX.md

## Phases

| #   | Phase                                                         | File                                  | Status |
| --- | ------------------------------------------------------------- | ------------------------------------- | ------ |
| 1   | Directional length-ratio guard in confidence path (Unit 1)    | phase-01-length-ratio-guard.md        | [x]    |
| 2   | Episode-filename fallback for degenerate show titles (Unit 2) | phase-02-episode-filename-fallback.md | [x]    |
| 3   | Phase gate — make check + AC-1..AC-7 re-exercise              | phase-03-gate.md                      | [x]    |
| 4   | PR #203 review fixes (cycle 1)                                | phase-04-pr-fixes-cycle-1.md          | [x]    |
| 5   | PR #203 review fixes (cycle 2)                                | phase-05-pr-fixes-cycle-2.md          | [ ]    |

## Review cycles

### Cycle 1 — PR #203 (CI green)

Adversarial review (4 dimensions × refute-by-default): 16 findings, **14 confirmed** (all "minor" per verifiers), 2 refuted.

- **functional** — `_recover_title_from_episodes` scans non-recursively → **Unit 2 Orville recovery returns `None` on the real `…/ S03/Saison 3/…` layout** (PROVEN; AC-2 test used a flat layout). → Phase 4.1.
- **functional** — `_SEASON_TOKEN_RE` strips from the _first_ `S\d` → over-strips embedded-S-number titles to `""`. → 4.1.
- **functional** — DESIGN's "empty title" fallback branch unhandled (only season-token). → 4.1.
- **test-quality** — AC-1 no-alias test is **vacuous** (passes with the guard removed); missing 0.40-boundary / Prince-Andrew / recovery-branch tests. → 4.2.
- **cosmetic** — bare `except Exception`; stale `0.67` in test docstrings + inline comment. → 4.1/4.3.
- _refuted_: guard rejects the right long title (best-of over aliases preserves it); AC-6 `^`-anchor mutation.
- _accepted (no fix)_: guard also applies to the movie path — beneficial, 877 tests green.

### Cycle 2 — PR #203 (re-review of the cycle-1 fix)

The cycle-1 fix INTRODUCED 2 regressions (both concretely reproduced):

- **major** — `rglob` recovery can pick a video from an `Extras/Featurettes/Bonus` subdir (`is_sample_path` only excludes sample/proof) → wrong show title. PROVEN: ` S03/Extras/…` → recovered `"Some Behind The Scenes Doc"`. → Phase 5.2 (restrict to root + season dirs via `SEASON_DIR_RE`).
- **medium** — narrowing the regex to `S\d+E\d+` broke the season-only case (`clean → "{title} S03"`): PROVEN `"The Orville Saison 3"` → `"The Orville S03"` (S03 leaked). → Phase 5.1 (end-anchored `S\d+(?:E\d+)?\s*$`).

Lesson: cycle-1's two changes each traded one bug for another; cycle-2 fixes both at the root + adds the missing regression tests (Extras-subdir, season-only).

## Next action

Run `/implement:phase` to execute Phase 5 (PR review fixes, cycle 2).
