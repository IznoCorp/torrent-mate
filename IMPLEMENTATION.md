# Implementation Progress — acquisition-queue

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V4 — Acquisition : rangées compactes, File d'acquisition, obligations titrées
**Type**: feat
**Branch**: feat/acquisition-queue (off main @ 3a7200e9 — bug wave 0.52.1)
**Ticket**: #308 (epic #304) — claimed; board moves broken (kanban-mate#187), card stays put
**PR**: https://github.com/IznoCorp/torrent-mate/pull/315
**Merge**: squash (**auto** — operator directive 2026-07-17)
**Design**: `docs/features/acquisition-queue/DESIGN.md` ← shared spec §3.1 + §5.1 + §7.2
**Version bump**: 0.52.1 → 0.53.0 (minor)

## Status: ALL PHASES DONE — feature-pr (push + PR + CI + review + AUTO merge)

**Master plan**: `docs/features/acquisition-queue/plan/INDEX.md`

## Phases

| #   | Phase                             | File                                                                         | Status |
| --- | --------------------------------- | ---------------------------------------------------------------------------- | ------ |
| 1   | Backend: ObligationItem.title     | [phase-01-backend-obligation-title.md](phase-01-backend-obligation-title.md) | [x]    |
| 2   | Suivis compact + Obligations rows | [phase-02-compact-rows.md](phase-02-compact-rows.md)                         | [x]    |
| 3   | File d'acquisition (merge + tabs) | [phase-03-file-dacquisition.md](phase-03-file-dacquisition.md)               | [x]    |
| 4   | Final gate                        | [phase-04-final-gate.md](phase-04-final-gate.md)                             | [x]    |
| 5   | PR fixes cycle 1                  | [phase-05-pr-fixes-cycle-1.md](phase-05-pr-fixes-cycle-1.md)                 | [x]    |

## Review cycles

### Cycle 1

- 4 agents on PR #315 @ 74a0e3ef. Code review: ZERO findings >=80. Silent-failures: F1 CRITICAL
  (downloads network-error renders the calm « Aucun téléchargement » lie — NE-DOIT-PAS-1/5; the
  wanted section has its error branch, downloads doesn't), F2 clipboard silent no-op, F3 latent
  notice nesting, F5 resolver fail-soft accepted. Tests review: 2 critical mutation gaps
  (case-insensitive join unpinned; per-row isolation unproven) + replace:true unpinned + 2 vacuous
  FollowedPanel assertions. Comments: 4 stale AcquisitionPage docblocks + resolver docstring
  overstates the per-row guarantee. Reviewer sub-threshold retained by orchestrator: movie rows
  render « Saison ?? » + raw enum (DOIT-2 polish, real data since D2 film ownership).
- Fix phase: phase-05-pr-fixes-cycle-1.md (3 sub-phases). Open items recorded there: pagination
  partial groups (needs arbitrage), badge-on-error, multi-row hash label non-determinism, crash vs
  no-data indistinguishable in UI.

## Dispatch notes

- Phase 3 notes: two max-turns salvages (3.1 committed by dispatch, 2.1/3.3-repairs committed by orchestrator after green gates); commit 96a1c8c9 label overstates (fixture repairs only — real redirect tests landed in 6077d914); 3 non-null lint errors from 3.2 fixed by orchestrator.
- Phase 1 dispatch: report OK but MODEL_IDENTITY probe MISSING (protocol anomaly recorded); content independently verified by orchestrator (lint 0, 61 tests, scope audit, code read).

## Scope guardrails (spec §6 sequencing invariant)

- Only `/acquisition` (tabs, rows, merge, obligations title) + `ObligationItem.title` backend enrichment.
- No Système/Config work (V5). Watcher tab untouched.
- No regression: watcher numbered results, obligations release flow, per-episode badges + FR reasons,
  downloads fail-soft notice, MediaSearchAdd flow.
- Route change ⇒ `make openapi` + commit regenerated files.
