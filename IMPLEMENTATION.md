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

## Status: branch created — awaiting plan (/implement:plan)

**Master plan**: _(to be generated)_

## Phases

_(plan pending)_

## Review cycles

_(none yet)_

## Scope guardrails (spec §6 sequencing invariant)

- Only `/acquisition` (tabs, rows, merge, obligations title) + `ObligationItem.title` backend enrichment.
- No Système/Config work (V5). Watcher tab untouched.
- No regression: watcher numbered results, obligations release flow, per-episode badges + FR reasons,
  downloads fail-soft notice, MediaSearchAdd flow.
- Route change ⇒ `make openapi` + commit regenerated files.
