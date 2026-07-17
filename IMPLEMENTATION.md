# Implementation Progress — overhaul-shell

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V1 — shell : sidebar sticky, badges d'attention, largeur
**Type**: feat
**Branch**: feat/overhaul-shell (off main @ 5a62a4ba)
**Ticket**: #305 (epic #304) — claimed via /kanban-work, card in Brainstorming
**PR**: _(none yet — created by /implement:feature-pr after last phase)_
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
| 4   | Test update (helpers + count-based badges)       | phase-04-test-update-gate.md        | [ ]    |
| 5   | Pipeline dot test + WS refresh test + final gate | phase-05-pipeline-dot-final-gate.md | [ ]    |

**Next action**: phase 4 — test update (phase-04-test-update-gate.md)

## Scope guardrails (from spec §6 sequencing invariant)

- NO route additions/removals/renames, no redirects, no nav-entry changes in this wave.
- No page-content redesign (V2–V5).
- Optional-only backend: `GET /api/attention/counts` if badge chattiness measured too high.
