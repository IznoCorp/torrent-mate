# Implementation Progress — control-medias

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V2 — Contrôle (poste de contrôle) + Médias (hub + fiche cockpit)
**Type**: feat
**Branch**: feat/control-medias (off main @ 27b6e21c — V1 squash)
**Ticket**: #306 (epic #304) — claimed; board moves broken (kanban-mate#187), card stays in Backlog
**PR**: _(none yet — created by /implement:feature-pr after last phase)_
**Merge**: squash (**auto** — operator directive 2026-07-17: chain all waves automatically)
**Design**: `docs/features/control-medias/DESIGN.md` ← binding shared spec
`docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §2.1 + §2.2 + §5.2 + §1.1(scoped)
**Version bump**: 0.50.0 → 0.51.0 (minor) — ⚠ solidify (worktree) targeted 0.50.0 which V1 took;
solidify re-bumps at its merge

## Status: BRANCH CREATED — awaiting plan

**Master plan**: `docs/features/control-medias/plan/INDEX.md` (6 phases; guarantor pass: deferred
detail phrased truthfully — no dedicated queue entry, runs sweep staging; activity-read-model intent
row recorded as documented deviation vs spec §5.2)

## Phases

| #   | Phase                                         | File                                 | Status |
| --- | --------------------------------------------- | ------------------------------------ | ------ |
| 1   | Backend — `continue` endpoint                 | phase-01-continue-endpoint.md        | [x]    |
| 2   | Backend — `discard` endpoint                  | phase-02-discard-endpoint.md         | [x]    |
| 3   | `/medias` page + LegacyRedirect + nav renames | phase-03-medias-page-redirect-nav.md | [x]    |
| 4   | Media-sheet egress actions                    | phase-04-media-sheet-egress.md       | [x]    |
| 5   | Contrôle rebuild (`/`)                        | phase-05-controle-rebuild.md         | [ ]    |
| 6   | Final gate — mobile proof + ACC               | phase-06-final-gate.md               | [ ]    |

**Next action**: phase 5 — Contrôle rebuild (incl. navigate('/scraping')→'/medias' in FlowBoard/PipelineActionBanner)

## Scope guardrails (spec §6 sequencing invariant)

- Only `/` rebuild, NEW `/medias`, `/scraping`→`/medias` redirect, 2 nav label renames.
- Backend: ONLY `continue` + `discard` endpoints (+ make openapi). No other route changes.
- No V3–V5 surfaces (pipeline/maintenance/registry/config/acquisition pages untouched).
