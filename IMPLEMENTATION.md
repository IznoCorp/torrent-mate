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

## Next action

Cycle-1 fixes done + pushed. Re-running CI + cycle-2 re-review, then manual merge handoff.
