# Design overhaul V5 — Système + Config + passe visuelle transversale

**Ticket**: #309 (epic #304, dernière vague) · **Binding source**:
`docs/superpowers/specs/2026-07-16-design-overhaul-design.md` §3.2 + §3.3 + §4 + §1.1 — the spec
wins on conflict. **Product intent**: §7 (journal home), §8, DOIT-9/DOIT-2 (no hover-only reason
carriers), DOIT-10 (URL-addressable), findings F1, G2, E3, H1–H6.

## Grounding (verified in code 2026-07-17)

- `frontend/src/router.tsx:53` (`maintenance`) + `:69` (`registry`) — legacy routes to remove with
  redirects `/registry` → `/systeme?tab=etat`, `/maintenance` → `/systeme?tab=etat`
  (LegacyRedirect precedent exists; `/maintenance?run=` already teleports to `/pipeline?run=` — V3
  MaintenanceRunRedirect stays honored: `?run=` still wins over the tab redirect).
- `frontend/src/pages/Maintenance.tsx` (98 L, thin shell) + `frontend/src/components/maintenance/`
  (ActionCatalog/ActionForm/DestructiveLogPanel/DisksPanel/IndexHealthPanel/LocksPanel + more) —
  panels to redistribute into the new tabs.
- `frontend/src/pages/RegistryPage.tsx` (228 L) — providers panel folds into État.
- `frontend/src/pages/Config.tsx` (765 L) — master-detail kept; G2 + Secrets sibling tab + FR.
- The FIVE divergent outcome maps: `dashboard/SchedulersPanel.tsx` (outcomeLabel),
  `pipeline/RunHistoryTable.tsx:53` (OUTCOME_BADGE), `pipeline/RunDetail.tsx:38` (OUTCOME_BADGE),
  `acquisition/meta.ts` (STATUS_LABEL + RUN_OUTCOME_LABEL).

## 1. `/systeme` — hub in 4 tabs (`?tab=etat|actions|maintenance|journal`, default `etat`)

- **État**: compact disk rows (DisksPanel), locks & sentinelles with the cached orphan sweep
  labelled « analyse en arrière-plan » + dated result, index health, providers (ex-Registre),
  EventFeed/RecentEventsTable sized to content (H4).
- **Actions**: current action catalog + runner, kept as-is (maintenance.md invariants intact —
  pipeline.lock held for the runner lifetime, staging-guarded).
- **Exécutions de maintenance** (F1 — the second history table, renamed): own `&run=` RunDetail
  drawer scoped to this tab; the V3 conditional `/maintenance?run=` → `/pipeline?run=` redirect
  keeps working for legacy links.
- **Journal**: deletions journal §7 (DestructiveLogPanel) gets its addressable home.
- Page shell mirrors AcquisitionPage: URL-addressable tabs, default clean URL, tablist
  `flex-nowrap overflow-x-auto` (E5 precedent).

## 2. Config (G2 + E3)

- First file auto-selected on arrival; **Secrets** becomes a sibling tab of the file list;
  `restart` chip gains a tap-accessible hint « Redémarrage requis après modification » (no
  hover-only); secret descriptions in French.

## 3. Transversal visual pass (§4)

- **`frontend/src/lib/outcome-labels.ts`** (new, single source): backend outcome/state → {FR label,
  tone}. ALL FIVE maps migrate to it; divergences resolved: `success→Succès`, `error→Échec`,
  `killed→Interrompu`, `queued→En file`, `blocked→Bloqué`, `pending→En attente`, `deferred→Différé`.
  Rendering rule: tone chip = outcomes; StatusDot = live states; mono = machine tokens.
- Surface hierarchy 3 levels max (H1) on the touched pages; type scale (H2): display sizes only for
  attention counts; version/disk-free at base mono.
- Empty states via `ds/EmptyState` on the touched surfaces; containers size to content (H4).
- One amber primary per view; em-dash placeholders get tap-accessible disclosure or visible
  microcopy (H6, DOIT-9).

## 4. Routes & redirects (§1.1)

- `/systeme` new route; `/registry` and `/maintenance` removed, both redirect (replace) to
  `/systeme?tab=etat`; `/maintenance?run=<uid>` still lands on `/pipeline?run=<uid>` (V3 contract).
- Sidebar « Maintenance » + « Registre » entries collapse into one « Système » entry; version
  detail lives in Système → État (§7.4 arbitration).

## 5. Backend scope

- ZERO backend changes (no openapi run expected). All web invariants intact.

## 6. Proof (§méthode)

- Dated prod capture: 4 tabs live, journal addressable, providers in État, redirects effective
  (`/registry`, `/maintenance`, `/maintenance?run=` all three), Config Secrets tab + auto-selected
  first file, one shared outcome vocabulary (Succès/Échec/Interrompu consistent across Pipeline,
  Système, Acquisition).
- 390 px iframe: zero page overflow on /systeme (all 4 tabs) + /config.
- Full test suites migrated (Maintenance suites → Système), redirect map tests complete.

## Sequencing invariant

Epic close-out: no NEW surface beyond /systeme + /config + the shared vocabulary; no backend
change; every V1–V4 acquis un-regressed (nav badges, Contrôle, Médias, Pipeline, Acquisition).
