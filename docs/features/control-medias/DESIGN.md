# DESIGN — control-medias (Design overhaul V2: Contrôle + Médias)

**Wave 2 of 5** of the design overhaul — epic #304, ticket #306. Merge mode: **auto** (operator directive
2026-07-17: chain all waves automatically).
**Binding shared spec:** `docs/superpowers/specs/2026-07-16-design-overhaul-design.md` — this wave implements
**§2.1 (Contrôle), §2.2 (Médias), §5.2 (continue endpoint), §5.3 (attention counts)** and the §1.1 pieces scoped
to it (component relocation, `/scraping` → `/medias` redirect, 2 nav-entry renames). On conflict the shared spec
wins; on conflict with `docs/reference/product-intent.md`, the constitution wins.
**Constitution served:** §2 (états FR clairs), §3 (sélecteur interactif accessible), §4 (la résolution termine le
pipeline, continuation VISIBLE), §6 (202 + « En file », jamais « occupé »), §7 (Ignorer/nettoyer = confirmation +
journal via DeleteAuthority), §8/DOIT-2 (« Ce qui n'avance pas » au poste de contrôle), DOIT-3, DOIT-5, DOIT-7
(porte de sortie garantie), DOIT-9, DOIT-10 (redirect avec params).

## 1. Scope

### 1.1 Routes & nav (scoped §1.1 subset — the REST of the nav overhaul is V5)

- NEW route `/medias` (page Médias) + `<LegacyRedirect>` component: `/scraping` → `/medias` forwarding
  `?media=` and `?decision=` (react-router `<Navigate>` does not forward query strings — custom component,
  unit-tested). `/scraping` ceases to exist as a page (redirect only).
- Nav renames (labels + icon targets, same grouping until V5): « Tableau de bord » → **« Contrôle »** (`/`,
  icon stays `Home`), « Scraping » → **« Médias »** (`/medias`, icon `ScanSearch` stays acceptable this wave).
  Bottom tabs follow (same 4 slots). Badge map keys: `/scraping` → `/medias` (AppShell + tests).
- All other routes untouched (Pipeline/Maintenance/Registry/Config/Acquisition = V3–V5).

### 1.2 Médias (`/medias`) — promote the staging library + guaranteed egress (spec §2.2)

- Page = current `Decisions.tsx` content REORGANIZED: grid view (StagingLibrary) becomes the DEFAULT view;
  the ResolutionDeck (« À résoudre ») and the decisions browse (DecisionList/DecisionDetail) remain as views
  reachable via the existing tabs, now labelled `Bibliothèque · À résoudre · Décisions`. `?media=` opens the
  sheet (existing), `?decision=` opens deck-if-pending / browse-detail-if-closed (existing behavior kept).
- **ONE merged filter system** (spec fix D4): grid segments become `À traiter · En cours · Prêts · Tous`
  mapped onto the existing read-model fields (`awaiting_action` cases / active / done+dispatchable / all);
  the redundant chip row (Tous/Identifiés/À résoudre/Non identifiés/Sans bande-annonce) is replaced by these
  segments + the existing search/density/sort (keep « Sans bande-annonce » as a secondary filter toggle —
  §8 visibility, do not lose it).
- **Media sheet guaranteed egress (DOIT-7)** — `StagingMediaDetail` actions by state:
  - `ambiguous` → « Résoudre le matching » (existing);
  - `absent` kind known → « Rechercher / résoudre manuellement » (existing enqueue);
  - `other` kind unknown → existing Film/Série chooser **plus NEW « Ignorer / nettoyer »** for non-media
    artifacts: Dialog with explicit §7 confirmation, executed by a NEW staging-scoped delete endpoint that
    routes through the existing DeleteAuthority (append-only journal entry mandatory — same journal as #300);
    regression test asserting the journal row.
  - **`matched` + blocked → NEW « Relancer et terminer le pipeline »** calling §5.2 `continue`;
  - `matched` clean → same action as secondary menu entry « Re-scraper cet élément ».
- Continuation visibility (§4): after `continue` returns 202, the sheet shows the queued/running state
  (reuse the resolve pattern: poll `GET /api/pipeline/history/{run_uid}` when run_uid known; « En file —
  pipeline en cours » pill when deferred) — timeline advances to Dispatché.

### 1.3 Contrôle (`/`) — attention-first rebuild (spec §2.1)

Panel order (Dashboard.tsx rebuilt, components reused not rebuilt — §méthode rule 5):

1. **À traiter** — generalizes `PipelineActionBanner`: rows for ALL `counts.awaiting_action` cases from
   `GET /api/staging/media` (mini poster + title + FR reason (`blocked_reason` / match state) + « Résoudre → »
   linking `/medias?media=<id>`; pending decisions link to the deck). Empty ⇒ one calm row « Rien à traiter ».
2. **Activité scraping** — `ScrapeActivityPanel` relocated from Decisions page (renders null when idle) —
   the anti-#249 acquis keeps a first-class home (NE-DOIT-PAS-2).
3. **Dernier run / run en cours** — digest card: trigger FR + relative time + counts summary + link
   `/pipeline?run=<uid>`; live interpreted progress while running (reuse `summariseSteps`/InterpretedRunFeed
   pieces; do NOT rebuild the pipeline page's feed).
4. **Ce qui n'avance pas** (§8/DOIT-2) — the RunDetail skip/defer block extracted into a shared component
   (`components/pipeline/StalledPanel` or similar) rendered here with the LAST run's data
   (`GET /api/pipeline/history/{run_uid}` of the latest run) — and still available in RunDetail.
5. **Acquisitions** — merge AcquisitionSummaryCard + SchedulersPanel: counters + next cron/watcher line each
   with last outcome chip; links `/acquisition`.
6. **Santé** — ONE compact row per domain: disks (inline mini-bars, replaces the giant per-disk cards on
   this page), index (1 line), Redis (dot), providers (dot + count OK). Detail links → `/maintenance`,
   `/registry` (until V5 moves them). HealthCard/IndexHealthPanel/DisksPanel stay the data sources —
   presentation-only compaction here.
7. **Pipeline control** — ONE state-dependent primary (Démarrer ⇄ Arrêter) + Pause/Reprendre inside a
   DropdownMenu + the Auto-trigger switch (PipelineControls refactor, keep all 5 mutations + queue-visible
   202 semantics §6).
8. **Version** → sidebar footer (collapsed rail: hidden). VersionCard leaves the Dashboard (full detail
   remains reachable — footer title attribute + Maintenance keeps nothing this wave; Système É tat hosts it
   in V5 per arbitration §7.4).

### 1.4 Backend (spec §5.2 + §7)

1. **`POST /api/staging/media/{id}/continue`** (staging-guarded, typed, `response_model`): validates the
   media exists (404 otherwise) and is `matched` (409-free contract: non-matched → 422 with FR detail
   pointing at resolve/enqueue instead — NOT a "busy" refusal, §6 respected: legitimate action = 202).
   Records an intent row (reuse/extend the decisions-activity read-model so the queue stays visible in
   ScrapeActivityPanel — NE-DOIT-PAS-2), then spawns the continuation via the single trigger authority
   (`spawn_pipeline_run(trigger_reason=continuation)` — full run, honest semantics; deferred-when-locked
   returns the queued state in the 202 body like resolve does). Unit + route tests (incl. the §6 pattern:
   202 while a run is active).
2. **Staging artifact delete** for « Ignorer / nettoyer »: `POST /api/staging/media/{id}/discard`
   (staging-guarded): only for `media_kind == other` non-media artifacts; moves the folder to a quarantine
   (or removes empty dirs) via DeleteAuthority with an append-only journal entry (who=web, what, when, path,
   decision) — NEVER a new deletion mechanism. 422 FR when preconditions unmet. Tests: journal row asserted,
   guard against non-`other` targets.
3. `make openapi` + commit regenerated `openapi.json` + `schema.d.ts` (CI drift guard).
4. NO other backend change (attention counts stay client-composed this wave — §5.3 escape only if measured).

## 2. Hard non-goals (sequencing invariant §6)

- No changes to `/pipeline`, `/maintenance`, `/registry`, `/config`, `/acquisition` pages (V3–V5).
- No nav-grouping flattening, no Système page (V5). No `/maintenance?run=` redirect (V3).
- No brand/token changes. No transversal visual pass (V5) — Contrôle uses existing primitives.

## 3. Acceptance (executable, per-wave proof protocol)

- Redirect: `/scraping?media=X` → `/medias?media=X` opens the sheet; `/scraping?decision=N` behaves as today.
- DOIT-7: every sheet state shows ≥1 action (seeded: ambiguous, absent, other-unknown, matched+blocked).
- §4: a matched+blocked media « Relancer et terminer » → 202 → run visible → timeline reaches Dispatché
  (real seeded media, `scripts/check-media-complete.py` green on it).
- §7: « Ignorer / nettoyer » writes a journal row (SELECT on the journal table shows the entry).
- Contrôle: À traiter lists the seeded blocked media from any screen via badge; « Ce qui n'avance pas »
  shows the last run's skip reasons; single primary control drives run start/stop.
- Frontend gates + `make check` green; mobile 390px iframe: overflow 0 on `/` and `/medias`.
- Prod proof post-merge: SW cache-bust + dated captures + version 0.51.0 asserted.
