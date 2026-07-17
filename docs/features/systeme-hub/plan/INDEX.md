# Implementation Plan — systeme-hub

**Feature**: Design overhaul V5 — Système + Config + passe visuelle transversale
**Epic**: #304, **Ticket**: #309
**Binding spec**: `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §3.2 + §3.3 + §4 + §1.1
**Binding design**: `docs/features/systeme-hub/DESIGN.md` (extraction; spec wins on conflict)
**Branch**: `feat/systeme-hub`
**Merge mode**: auto

## Phase table

| #   | Phase                                    | File                                                     | Status |
| --- | ---------------------------------------- | -------------------------------------------------------- | ------ |
| 1   | Outcome-labels foundation                | [phase-01-outcome-labels.md](phase-01-outcome-labels.md) | [ ]    |
| 2   | /systeme hub (4 tabs, routes, redirects) | [phase-02-systeme-page.md](phase-02-systeme-page.md)     | [ ]    |
| 3   | Config polish (G2 + Secrets + FR)        | [phase-03-config-polish.md](phase-03-config-polish.md)   | [ ]    |
| 4   | Visual pass + final gate                 | [phase-04-visual-gate.md](phase-04-visual-gate.md)       | [ ]    |

## Sequencing rationale

Phase 1 MUST ship first — `outcome-labels.ts` is the shared vocabulary module consumed by every
surface Phase 2 redistributes. The five divergent maps (SchedulersPanel.outcomeLabel,
RunHistoryTable.OUTCOME_BADGE, RunDetail.OUTCOME_BADGE, acquisition/meta.ts STATUS_LABEL,
acquisition/meta.ts RUN_OUTCOME_LABEL) are migrated here, resolving the Réussi/Succès,
Arrêté/Interrompu, Erreur/Échec divergences. ZERO visual change beyond the unified wording.

Phase 2 ships next — the `/systeme` page with 4 URL-addressable tabs (`etat|actions|maintenance|journal`,
default `etat`) creates the new surface that absorbs the legacy `/maintenance` and `/registry` routes.
The existing maintenance components (DisksPanel, LocksPanel, IndexHealthPanel, ActionCatalog,
DestructiveLogPanel, EventFeed, RecentEventsTable, RunHistoryTable) and registry provider cards
are redistributed, not rewritten. Only the page shell, routing, sidebar, and redirects are new code.

Phase 3 ships the Config polish on a stable foundation — the `/systeme` hub is already the canonical
home for maintenance/registry surfaces, so Config changes (first-file auto-select, Secrets sibling tab,
restart hint tap-accessible, FR descriptions) land without cross-surface conflicts.

Phase 4 is the visual pass across all touched surfaces (H1–H6 surface hierarchy, amber primary,
EmptyState, em-dash placeholders) plus the final quality gate — full frontend + backend suites,
redirect map tests complete, IMPLEMENTATION.md table.

## Hard guardrails

1. **Only the surfaces in DESIGN.md**: outcome-labels.ts + /systeme page + Config + visual pass.
   ZERO backend changes, ZERO other route modifications, ZERO openapi regeneration.
2. **No regression on**: V3 `/maintenance?run=` → `/pipeline?run=` teleport (MaintenanceRunRedirect
   stays honored); maintenance invariants (pipeline.lock held for runner lifetime, staging-guarded);
   every V1–V4 acquis (nav badges, Contrôle, Médias, Pipeline, Acquisition).
3. **Route changes**: `/registry` + `/maintenance` → `/systeme?tab=etat` (LegacyRedirect pattern);
   `/maintenance?run=<uid>` still teleports to `/pipeline?run=<uid>`.
4. **Per-commit frontend gate**: `cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run`
5. **Per-commit backend gate**: `make lint && make test` (only if backend files move; this feature has
   zero backend changes, so Phase 2–4 skip except for the module move in Phase 3).
6. **Product intent served**: §7 (journal home), §8, DOIT-2 (no hover-only reason carriers),
   DOIT-9 (tap-accessible), DOIT-10 (URL-addressable), H1–H6 (surface hierarchy + type scale +
   EmptyState + amber primary + em-dash microcopy).
7. **Proof-gated (§méthode)**: no « conforme » without a dated executed run; 390px iframe harness
   for mobile checks on /systeme (all 4 tabs) + /config; SW cache-bust protocol for frontend
   verification.
8. **Test migration**: Maintenance.test.tsx + RegistryPage.test.tsx suites migrate to the new
   page; old pages deleted only once tests pass on the new surface.
