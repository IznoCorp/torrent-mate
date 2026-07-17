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

## Status: BRANCH CREATED — awaiting plan

**Master plan**: _(docs/features/pipeline-panel/plan/INDEX.md)_

## Phases

| #                     | Phase | File | Status |
| --------------------- | ----- | ---- | ------ |
| _(populated by plan)_ |       |      |        |

## Scope guardrails (spec §6 sequencing invariant)

- Only `/pipeline` (stepper + history + legend popover) + the CONDITIONAL `/maintenance?run=` redirect.
- Maintenance loses ONLY its pipeline-runs table; everything else untouched (V5 does /systeme).
- ZERO backend changes (no openapi run expected).
