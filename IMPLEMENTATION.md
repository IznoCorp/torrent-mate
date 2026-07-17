# Implementation Progress — pipeline-panel

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V3 — Pipeline : stepper réparé + historique rapatrié
**Type**: feat
**Branch**: feat/pipeline-panel (off main @ dc01fb11 — V2 + hotfix 0.51.1)
**Ticket**: #307 (epic #304) — claimed; board moves broken (kanban-mate#187), card stays in Backlog
**PR**: _(none yet)_
**Merge**: squash (**auto** — operator directive 2026-07-17)
**Design**: `docs/features/pipeline-panel/DESIGN.md` ← shared spec §2.3 + §1.1 (conditional `?run=` redirect)
**Version bump**: 0.51.1 → 0.52.0 (minor)

## Status: ALL PHASES DONE — feature-pr (push + PR + CI + review + AUTO merge)

**Master plan**: docs/features/pipeline-panel/plan/INDEX.md (4 phases)

## Phases

| # | Phase | File | Status |
| - | ----- | ---- | ------ |
| 1 | Stepper compression + mobile vertical | phase-01-stepper.md | [x] |
| 2 | History repatriation + legend popover | phase-02-history.md | [x] |
| 3 | Conditional /maintenance?run= redirect | phase-03-redirect.md | [x] |
| 4 | Final gate | phase-04-final-gate.md | [x] |

## Review cycles

### Cycle 1

- 4 agents on PR #313 @ 44fa6fed. No design contradictions. Code review: ZERO findings >=80 conf
  (cleanest wave). Tests review: mutation-PROVEN suite blindness (G1/G2/G7 — suite green with the
  DOIT-2 invariant broken). Silent-failures: core anomaly-visibility requirement STRUCTURALLY HOLDS;
  residual risk in error paths around the repatriated history (B1 dead teleported code, B2 empty ?run=,
  B3 non-dismissible 404/500-conflated error card, D1 unencoded uid, C1 SR-invisible legend menu,
  C2 legend lost on Maintenance). Comments: nine→eight-stage + RunDetail module doc + 5 precisions.
- Fix phase: phase-05-pr-fixes-cycle-1.md (3 sub-phases — DONE; mutations A/B verified RED then reverted). Open items recorded there incl. **B4
  (backend calm-empty history on DB failure — LOUD operator item, candidate hotfix)** and P2
  (active outranks blocked).

## Scope guardrails (spec §6 sequencing invariant)

- Only `/pipeline` (stepper + history + legend popover) + the CONDITIONAL `/maintenance?run=` redirect.
- Maintenance loses ONLY its pipeline-runs table; everything else untouched (V5 does /systeme).
- ZERO backend changes (no openapi run expected).
