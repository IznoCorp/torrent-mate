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

**Master plan**: _(docs/features/control-medias/plan/INDEX.md)_

## Phases

| #                     | Phase | File | Status |
| --------------------- | ----- | ---- | ------ |
| _(populated by plan)_ |       |      |        |

## Scope guardrails (spec §6 sequencing invariant)

- Only `/` rebuild, NEW `/medias`, `/scraping`→`/medias` redirect, 2 nav label renames.
- Backend: ONLY `continue` + `discard` endpoints (+ make openapi). No other route changes.
- No V3–V5 surfaces (pipeline/maintenance/registry/config/acquisition pages untouched).
