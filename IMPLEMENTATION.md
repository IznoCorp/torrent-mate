# Implementation Progress — overhaul-shell

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V1 — shell : sidebar sticky, badges d'attention, largeur
**Type**: feat
**Branch**: feat/overhaul-shell (off main @ 5a62a4ba)
**Ticket**: #305 (epic #304) — claimed via /kanban-work, card in Brainstorming
**PR**: #310 → main (https://github.com/IznoCorp/torrent-mate/pull/310) — OPEN, CI en cours
**Merge**: squash (manual — operator merges)
**Design**: `docs/features/overhaul-shell/DESIGN.md` (wave design) ← binding shared spec
`docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §1.1 + §6
**Version bump**: 0.49.16 → 0.50.0 (minor) — ⚠ solidify (worktree) also targets 0.50.0; whichever PR merges
second re-bumps at merge-conformance time (flagged to operator)

## Status: PLAN READY — next action `/implement:phase`

**Master plan**: `docs/features/overhaul-shell/plan/INDEX.md` (5 phases; guarantor-realigned:
badge poll 60s per DESIGN, green-gate-per-commit test retarget in 2.1, StatusDot real props)

## Phases

| #   | Phase                                            | File                                | Status |
| --- | ------------------------------------------------ | ----------------------------------- | ------ |
| 1   | Sticky sidebar                                   | phase-01-sticky-sidebar.md          | [x]    |
| 2   | Attention badges (data sources + WS refresh)     | phase-02-attention-badges.md        | [x]    |
| 3   | Content width                                    | phase-03-content-width.md           | [x]    |
| 4   | Test update (helpers + count-based badges)       | phase-04-test-update-gate.md        | [x]    |
| 5   | Pipeline dot test + WS refresh test + final gate | phase-05-pipeline-dot-final-gate.md | [x]    |
| 6   | PR fixes cycle 1 (review findings)               | phase-06-pr-fixes-cycle-1.md        | [x]    |

**Next action**: push + re-poll CI, review cycle 2 (verify fixes), then operator merge (manual)

## Review cycles

### Cycle 1

- 4 agents (code / tests / comments / silent-failures) on PR #310 @ 086155eb.
- Retained: **1 major** — SF-1 regression (decisions WS bridge dropped: Decisions live-refresh +
  ScrapeActivityPanel reviver orphaned); **8 medium** — SF-2 badge error rendered as all-clear,
  SF-3 acquisition badge without refresh + false comment, paused dot labelled « en cours d'exécution »,
  TC-1/TC-3/TC-4 test gaps, docstring/docblock inaccuracies (queryOptions undocumented, WS list
  incomplete), SF-6/SF-7 hardening (optional chain, key constant).
- Ignored (with reason): none out-of-scope dismissed silently — 4 items surfaced for operator
  arbitration in phase-06 §« Explicitly NOT fixed » (SF-4 ring deafness parity, SF-5 parse drops
  pre-existing, ItemProgressed load observation, eslint message cosmetics).
- Design contradictions: none.
- Fix phase: phase-06-pr-fixes-cycle-1.md (2 sub-phases).

## Scope guardrails (from spec §6 sequencing invariant)

- NO route additions/removals/renames, no redirects, no nav-entry changes in this wave.
- No page-content redesign (V2–V5).
- Optional-only backend: `GET /api/attention/counts` if badge chattiness measured too high.
