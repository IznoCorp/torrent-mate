# Implementation Progress — systeme-hub

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V5 — Système + Config + passe visuelle transversale
**Type**: feat
**Branch**: feat/systeme-hub (off main @ 33472fc7 — V4 0.53.0)
**Ticket**: #309 (epic #304, dernière vague) — claimed; board moves broken (kanban-mate#187)
**PR**: https://github.com/IznoCorp/torrent-mate/pull/317
**Merge**: squash (**auto** — operator directive 2026-07-17)
**Design**: `docs/features/systeme-hub/DESIGN.md` ← shared spec §3.2 + §3.3 + §4 + §1.1
**Version bump**: 0.53.0 → 0.54.0 (minor)

## Status: ALL PHASES DONE — feature-pr (push + PR + CI + review + AUTO merge)

**Master plan**: `docs/features/systeme-hub/plan/INDEX.md`

## Phases

| #   | Phase                                    | File                                                                                    | Status |
| --- | ---------------------------------------- | --------------------------------------------------------------------------------------- | ------ |
| 1   | Outcome-labels foundation                | [phase-01-outcome-labels.md](docs/features/systeme-hub/plan/phase-01-outcome-labels.md) | [x]    |
| 2   | /systeme hub (4 tabs, routes, redirects) | [phase-02-systeme-page.md](docs/features/systeme-hub/plan/phase-02-systeme-page.md)     | [x]    |
| 3   | Config polish (G2 + Secrets + FR)        | [phase-03-config-polish.md](docs/features/systeme-hub/plan/phase-03-config-polish.md)   | [x]    |
| 4   | Visual pass + final gate                 | [phase-04-visual-gate.md](docs/features/systeme-hub/plan/phase-04-visual-gate.md)       | [x]    |
| 5   | PR fixes cycle 1                         | [phase-05-pr-fixes-cycle-1.md](docs/features/systeme-hub/plan/phase-05-pr-fixes-cycle-1.md) | [ ]    |

## Review cycles

### Cycle 1

- 4 agents on PR #317 @ 77003a6c. Code: 2 findings >=80 (button-in-button FileList; RunDetail
  cross-link lands on État instead of ?tab=maintenance, test locks the stale target). Silent-failures:
  F1 HIGH « Jamais exécuté » for an executed-but-unmapped outcome canonized in the shared module;
  F2 « — » erases unknown tokens; F3 /registry LegacyRedirect builds a double-? URL and the test
  certifies the broken param forwarding; F5 auto-select re-adds ?file= behind Secrets. Tests (live
  mutation probes): redirects + deep-link guard proven RED; RunDetail divergent-label revert is a
  PROVEN SURVIVING MUTANT; circuit-badge labels lost in suite migration; restart hint + FR secrets
  shipped with zero tests. Comments: Config/nav/RunDetail/CompactHealth stale docblocks + 6 active
  claims in web-ui.md/maintenance.md now false. Backend extraction verified byte-identical, clean.
- Fix phase: phase-05-pr-fixes-cycle-1.md (3 sub-phases). Open items recorded there (F6/F7
  pre-existing quiet-error styling, stale &run= sanctioned pattern).

## Scope guardrails (epic close-out)

- /systeme (4 tabs) + /config (G2/Secrets/FR) + lib/outcome-labels.ts migration (5 maps) + redirects
  /registry + /maintenance → /systeme?tab=etat (V3 ?run= teleport preserved).
- ZERO backend change. Every V1–V4 acquis un-regressed.
- Maintenance invariants intact (runner lock lifetime, staging guards, journal §7/§8).
