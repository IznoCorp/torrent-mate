# overhaul-shell — Implementation Plan

> **Feature:** Design overhaul V1: shell (sticky sidebar, attention badges, width)
> **Spec:** `docs/features/overhaul-shell/DESIGN.md` + shared spec `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §1.1 + §6
> **Epic:** #304 · **Ticket:** #305
> **Branch:** `feat/overhaul-shell`

## Global Constraints

- **NO route additions/removals/renames**, no redirects, no nav-entry label/order/grouping changes.
- **NO page-content redesign** — that is V2–V5. Only shell chrome changes.
- **NO new backend endpoint** unless badge-chattiness measurement demands `GET /api/attention/counts` (and then: staging-guarded read pattern + `make openapi` + commit regenerated files).
- **Frontend gates per commit:** `cd frontend && npm run lint && npm run typecheck && npx vitest run`.
- **Version target:** 0.50.0 — bumped by this feature's create-branch commit (`af959fbb`). ⚠ The
  solidify worktree also targets 0.50.0; whichever PR merges second re-bumps (flagged to operator).
- **Constitution served:** §8 (badges = « rien en silence »), DOIT-3 (agir là où l'on observe), DOIT-9 (mobile poste principal), DOIT-10 (aucune URL cassée).

## Phases

| #   | Phase                                            | File                                                                       | Status |
| --- | ------------------------------------------------ | -------------------------------------------------------------------------- | ------ |
| 1   | Sticky sidebar                                   | [phase-01-sticky-sidebar.md](phase-01-sticky-sidebar.md)                   | [ ]    |
| 2   | Attention badges (data sources + WS refresh)     | [phase-02-attention-badges.md](phase-02-attention-badges.md)               | [ ]    |
| 3   | Content width                                    | [phase-03-content-width.md](phase-03-content-width.md)                     | [ ]    |
| 4   | Test update (helpers + count-based badges)       | [phase-04-test-update-gate.md](phase-04-test-update-gate.md)               | [ ]    |
| 5   | Pipeline dot test + WS refresh test + final gate | [phase-05-pipeline-dot-final-gate.md](phase-05-pipeline-dot-final-gate.md) | [ ]    |
