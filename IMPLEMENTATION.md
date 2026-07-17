# Implementation Progress — acquisition-queue

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V4 — Acquisition : rangées compactes, File d'acquisition, obligations titrées
**Type**: feat
**Branch**: feat/acquisition-queue (off main @ 3a7200e9 — bug wave 0.52.1)
**Ticket**: #308 (epic #304) — claimed; board moves broken (kanban-mate#187), card stays put
**PR**: _(none yet)_
**Merge**: squash (**auto** — operator directive 2026-07-17)
**Design**: `docs/features/acquisition-queue/DESIGN.md` ← shared spec §3.1 + §5.1 + §7.2
**Version bump**: 0.52.1 → 0.53.0 (minor)

## Status: phase 3 done — next: phase 4 (final gate)

**Master plan**: `docs/features/acquisition-queue/plan/INDEX.md`

## Phases

| #   | Phase                             | File                                                                         | Status |
| --- | --------------------------------- | ---------------------------------------------------------------------------- | ------ |
| 1   | Backend: ObligationItem.title     | [phase-01-backend-obligation-title.md](phase-01-backend-obligation-title.md) | [x]    |
| 2   | Suivis compact + Obligations rows | [phase-02-compact-rows.md](phase-02-compact-rows.md)                         | [x]    |
| 3   | File d'acquisition (merge + tabs) | [phase-03-file-dacquisition.md](phase-03-file-dacquisition.md)               | [x]    |
| 4   | Final gate                        | [phase-04-final-gate.md](phase-04-final-gate.md)                             | [ ]    |

## Review cycles

- Phase 3 notes: two max-turns salvages (3.1 committed by dispatch, 2.1/3.3-repairs committed by orchestrator after green gates); commit 96a1c8c9 label overstates (fixture repairs only — real redirect tests landed in 6077d914); 3 non-null lint errors from 3.2 fixed by orchestrator.
- Phase 1 dispatch: report OK but MODEL_IDENTITY probe MISSING (protocol anomaly recorded); content independently verified by orchestrator (lint 0, 61 tests, scope audit, code read).

## Scope guardrails (spec §6 sequencing invariant)

- Only `/acquisition` (tabs, rows, merge, obligations title) + `ObligationItem.title` backend enrichment.
- No Système/Config work (V5). Watcher tab untouched.
- No regression: watcher numbered results, obligations release flow, per-episode badges + FR reasons,
  downloads fail-soft notice, MediaSearchAdd flow.
- Route change ⇒ `make openapi` + commit regenerated files.
