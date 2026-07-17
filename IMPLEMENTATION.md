# Implementation Progress — control-medias

> For Claude: read this file at session start. Current feature tracker.

**Feature**: Design overhaul V2 — Contrôle (poste de contrôle) + Médias (hub + fiche cockpit)
**Type**: feat
**Branch**: feat/control-medias (off main @ 27b6e21c — V1 squash)
**Ticket**: #306 (epic #304) — claimed; board moves broken (kanban-mate#187), card stays in Backlog
**PR**: #311 → main (https://github.com/IznoCorp/torrent-mate/pull/311) — OPEN, CI en cours
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
| 5   | Contrôle rebuild (`/`)                        | phase-05-controle-rebuild.md         | [x]    |
| 6   | Final gate — mobile proof + ACC               | phase-06-final-gate.md               | [x]    |

**Next action**: phase 7 — PR fixes cycle 1, then push + CI + verify cycle 2 + AUTO merge

## Review cycles

### Cycle 1

- 4 agents on PR #311 @ fadca5b3. No design contradictions.
- Retained: 2 CRITICAL (A1 deferred continuation without durable trace §8; C1 disks-error rendered as
  « Aucun disque configuré » — regression vs DisksPanel), 7 HIGH (B1 move failures opaque, B2 journal
  read-back stale-row false positive §7, C2 providers calm-nothing, C4/C5 digest+StalledPanel
  calm-nothing, D1 journaled=false as success toast §7, D3 dead ?media deep-link), mediums (A2 promised
  run_uid unverified, A3 corrupt-NFO 422, B3/B4 journal completeness, C3 mislabeling, D2 silent
  ?decision drop) + model-docstring factual errors exported to OpenAPI (#1 timeline_resumes, #2
  emptied-in-place) + comment sweep (#3-#11, CM-4) + test gaps (403 staging-role ×2, quarantine
  collision, verbatim toasts, invalidation contracts, hook derivations, collapsed sidebar).
- Fix phase: phase-07-pr-fixes-cycle-1.md (3 sub-phases).

## Open items (operator arbitration — §méthode rule 4)

- Server-side `position`/`awaiting` param for GET /api/staging/media (pagination-correct segments +
  ATraiterList >100 cap) — THE tracking record referenced by code comments.
- B5 quarantine TOCTOU nesting (theoretical under single-writer topology).
- E ScrapeActivityPanel drift-guard silent on schema-drifted 200 (OpenAPI CI gate compensates).
- A2 deeper: server-side promised-runs ledger.

## Scope guardrails (spec §6 sequencing invariant)

- Only `/` rebuild, NEW `/medias`, `/scraping`→`/medias` redirect, 2 nav label renames.
- Backend: ONLY `continue` + `discard` endpoints (+ make openapi). No other route changes.
- No V3–V5 surfaces (pipeline/maintenance/registry/config/acquisition pages untouched).
