# Implementation Plan — acquisition-queue

**Feature**: Design overhaul V4 — Acquisition : rangées compactes, File d'acquisition, obligations titrées
**Epic**: #304, **Ticket**: #308
**Binding spec**: `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §3.1 + §5.1 + §7.2
**Binding design**: `docs/features/acquisition-queue/DESIGN.md` (extraction; spec wins on conflict)
**Branch**: `feat/acquisition-queue`
**Merge mode**: auto

## Phase table

| #   | Phase                             | File                                                                         | Status |
| --- | --------------------------------- | ---------------------------------------------------------------------------- | ------ |
| 1   | Backend: ObligationItem.title     | [phase-01-backend-obligation-title.md](phase-01-backend-obligation-title.md) | [ ]    |
| 2   | Suivis compact + Obligations rows | [phase-02-compact-rows.md](phase-02-compact-rows.md)                         | [ ]    |
| 3   | File d'acquisition (merge + tabs) | [phase-03-file-dacquisition.md](phase-03-file-dacquisition.md)               | [ ]    |
| 4   | Final gate                        | [phase-04-final-gate.md](phase-04-final-gate.md)                             | [ ]    |

## Sequencing rationale

Phase 1 MUST ship first — the ObligationItem `title` field is a backend schema change
that requires `make openapi` + regenerated `openapi.json`/`schema.d.ts`. Frontend phases
(2, 3) consume the regenerated types and cannot compile against the new field until it exists.

Phase 2 ships next because the compact-row refactors (FollowedPanel + ObligationsPanel) are
independent of the tab merge. Each panel's tests stay self-contained; no cross-panel coupling.

Phase 3 ships last before the gate because the tab merge (wanted+downloads → File d'acquisition)
touches `AcquisitionPage.tsx`, `meta.ts` (TABS), `router.tsx` (redirects), and creates the new
merged panel. The compact-row styles from Phase 2 set the visual baseline that Phase 3 extends
(segmented control, grouped searches).

Phase 4 is the quality gate — no code changes, only verification.

## Hard guardrails

1. **Only `/acquisition` surfaces** + ObligationItem enrichment — no Système/Config (V5), no
   other routes, no backend refactors beyond the title resolver.
2. **No regression on**: watcher numbered results, obligations release flow, per-episode
   badges + FR reasons, downloads fail-soft notice, MediaSearchAdd flow.
3. **Route change ⇒ `make openapi`** + commit regenerated `openapi.json` / `schema.d.ts` (CI
   drift guard — known incidents).
4. **Per-commit frontend gate**: `cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run`
5. **Per-commit backend gate** (Phase 1): `make lint && make test`
6. **Product intent served**: §5 (completeness épisode-par-épisode), §9 (one flow
   wanted→grabbed→ingest), DOIT-2 (FR reasons, truthful states), DOIT-10 (URL-addressable),
   NE-DOIT-PAS-1/5 (never a calm lie on unreachable torrent client), E1–E6 findings.
7. **Proof-gated (§méthode)**: no « conforme » without a dated executed run; 390px iframe
   harness for mobile checks; SW cache-bust protocol for frontend verification.
