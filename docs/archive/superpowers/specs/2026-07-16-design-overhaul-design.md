# TorrentMate — Design Overhaul (media-centric IA + systemic visual pass)

**Date:** 2026-07-16 · **Status:** APPROVED — validated section-by-section by the operator (sections 1–4),
revised after a 3-lens adversarial review (constitution / consistency / feasibility, 19 findings folded in),
and the 4 open arbitrations resolved by the operator on 2026-07-16 (see §7).
**Approach chosen:** B — « IA média-centrée » (operator choice over A "targeted realignment" and C "total redesign
incl. brand").
**Constitution:** this spec serves §1, §2, §3, §4, §5, §6, §7, §8, §9, §10, DOIT-1..10, NE-DOIT-PAS-1..8 —
citations inline. Brand (amber/dark/Geist, tokens, logo) is **unchanged**: the operator's declared pains are
readability/hierarchy, navigation/journeys, and mobile comfort — not the visual identity.

**Grounding — executed evidence (§méthode rule 2):**

- Live prod review 2026-07-16, all 7 surfaces, desktop 1440px + mobile 390px iframe harness, real data (v0.49.16):
  `docs/analysis/2026-07-16-design-review-findings.md` (findings A1–H6 referenced below).
- Code-grounding workflow (5 parallel inventory agents + adversarial synthesis), then a 3-lens adversarial spec
  review — all design-critical assumptions verified with file:line evidence:
  - A. §8 skip-reasons block exists only in `RunDetail.tsx:414-421`, rendered only from `Maintenance.tsx:103` — the
    Dashboard lacks it; promotion is **frontend-only** (data already served by `GET /api/pipeline/history/{run_uid}`).
  - B. A matched-but-verify-blocked media has **zero UI actions**: `StagingMediaDetail.tsx` gates its two actions on
    `match==='ambiguous'` (resolve) / `match==='absent'` (enqueue); `blocked_reason` is display-only. No per-media
    continuation endpoint exists in the backend.
  - C. `ObligationItem` (`web/models/acquisition.py:147`) has **no title/display-name field** (the only
    title-derivable fields are `info_hash` and nullable `dispatched_path`); a real title requires an API change.
  - D. Sidebar is not sticky: `Sidebar.tsx:68-72` plain flex child of `AppShell.tsx:80` `min-h-screen` div.
  - E. Outcome labels diverge across **five** local maps: `success` → « Réussi » (`SchedulersPanel.tsx:87`) vs
    « Succès » elsewhere; `killed` → « Arrêté » (`RunHistoryTable.tsx:59`, `RunDetail.tsx:39`,
    `acquisition/meta.ts` STATUS_LABEL) vs « Interrompu » (`SchedulersPanel.tsx:91`, `acquisition/meta.ts`
    RUN_OUTCOME_LABEL — the same file diverges internally); `error` → « Erreur » vs « Échec ». No shared module.
- Corrections the evidence passes made to the live findings (kept honest, §10-5): the locks endpoint is **already**
  split/cached (background sweep + TTL, `routes/maintenance.py:335-411`) — finding F3 is stale, no backend work
  needed there; `/pipeline?stage=` already opens a per-stage FlowBoard drawer — C1/C2 are about visibility + the
  dead-end sheet, not a missing drawer; `counts.awaiting_action` already counts **all** blocked cases (see §1.1).

---

## 1. Information architecture & shell (validated)

### 1.1 Navigation: 7 module-entries → 6 journey-entries

| New entry       | Route          | Content                                                                                           | Comes from                            |
| --------------- | -------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------- |
| **Contrôle**    | `/`            | §8 control station: à traiter, activité scraping, dernier run, ce qui n'avance pas, santé résumée | Dashboard rebuilt                     |
| **Médias**      | `/medias`      | Poster grid (staging) + media sheet = timeline + **guaranteed actions** + decisions browse        | `/scraping` promoted                  |
| **Pipeline**    | `/pipeline`    | Fixed stepper + last run + **run history (repatriated)**                                          | Pipeline + Maintenance history #1     |
| **Acquisition** | `/acquisition` | Unchanged structure, densified (section 3)                                                        | Acquisition                           |
| **Système**     | `/systeme`     | Tabs: État · Actions · Historique maintenance · Journal                                           | Maintenance split + Registre absorbed |
| **Config**      | `/config`      | Unchanged, defects fixed                                                                          | Config                                |

- **Nav is flat (6 entries, no group micro-labels)** — the Supervision/Système/Configuration grouping of
  `nav.ts:62-83` disappears (a « Système » group label colliding with a « Système » page label would confuse).
- « Scraping » disappears as a nav entry: pending decisions become a **media state** (badge on Médias + « À
  traiter » list on Contrôle). The §3 interactive selector (ResolutionDeck — kept as-is, strong acquis) opens from
  the media sheet, the À-traiter list, and `/medias?decision=`.
- **Component relocation map** (nothing silently dropped — §méthode rule 4): `ResolutionDeck` → Médias ·
  `StagingLibrary` + `StagingMediaDetail` → Médias · `DecisionList`/`DecisionDetail` (cross-status browse incl.
  resolved/dismissed history) → Médias secondary view « Décisions » (adressable, see redirects) ·
  **`ScrapeActivityPanel` → Contrôle** (see §2.1 — this is the resolve-queue visibility acquis of #249/§6; it must
  never lose a home) · `RecentResolutions` → stays on Pipeline · `EventFeed`/`RecentEventsTable` → Système État ·
  `RunDetail`/`RunHistoryTable` → Pipeline (kind=pipeline) and Système (kind=maintenance) · `DestructiveLogPanel` →
  Système Journal · Registry cards → Système État. `/login` and NotFound are **untouched**.
- **Sidebar sticky** (fix A1/D): make the `<aside>` `sticky top-0 h-screen overflow-y-auto` (or equivalent) inside
  the existing flex shell; preserve the collapse rail (`md:w-16`/`md:w-56`) and `tm-sidebar-collapsed` persistence;
  the same `NavSections` keeps powering the mobile Sheet.
- **Attention badges** (fix A3): extend the existing `badges: Record<path, ReactNode>` mechanism in `AppShellInner`.
  **Médias badge = `counts.awaiting_action` alone** — the field already counts every `position_state=='blocked'`
  case: ambiguous (pending decision), absent, unknown-kind `other`, and verify-blocked (`stages.py:118-131`); do
  NOT add pending decisions on top (double-count). Verify-blocked specifically = `position_stage=='verify' &&
position_state=='blocked'`. Pipeline badge = running dot; Acquisition badge = pending wanted count.
  **Refresh strategy:** the existing WS listener (ItemProgressed `queued_for_decision`) extends to invalidate the
  staging-counts query on ItemProgressed status changes and on run-finished events; fallback poll 60s. Note:
  `GET /api/staging/media` is a filesystem-scanning endpoint — if measurement shows badge queries are too chatty,
  ship the small aggregate `GET /api/attention/counts` endpoint (§5.3) instead of widening polling.
- **Mobile bottom-tabs (4):** Contrôle · Médias · Pipeline · Acquisition (Système/Config in the hamburger Sheet —
  matches the operator's 2026-07-15 directive that removed Maintenance from the tab bar; `BottomTabBar.tsx`
  docstring is stale, don't "restore" it).
- **DOIT-10 redirects** — via a shared `<LegacyRedirect>` component (react-router `<Navigate>` does not forward
  query strings; `router.tsx` has no redirect infra today) that forwards/rewrites search params:
  - `/scraping` → `/medias` (forwarding `?media=`, `?decision=`);
  - `/registry` → `/systeme?tab=etat` (providers live inside État — no `providers` tab exists; scroll-anchor ok);
  - `/maintenance` → `/systeme?tab=etat`; **conditional:** `/maintenance?run=<uid>` → `/pipeline?run=<uid>` —
    RunDetail on Pipeline renders **any** uid (backend `GET /api/pipeline/history/{run_uid}` serves both kinds);
    when the uid is a maintenance run it renders with a link « voir les exécutions de maintenance » → Système;
  - `/acquisition?tab=wanted|downloads` → `/acquisition?tab=file`.
  - Canonical Système tab values: `etat | actions | maintenance | journal` (default `etat`); maintenance-run detail
    is URL-addressable as `/systeme?tab=maintenance&run=<uid>` (own RunDetail drawer).
- **Width:** container max ≈1280px with 2-col grids where justified (fix A4).

### 1.2 What is deliberately kept (§méthode rule 5 — never raze acquis)

ResolutionDeck (keyboard nav, manual re-query, 202-resolve continuation), **ScrapeActivityPanel — the global
« Scrapes en cours / En file : N » queue visibility (§6 reference pattern, anti-#249)**, URL-addressability
everywhere, per-media « Parcours pipeline » timeline, Maintenance action catalog with safety badges, French
interpreted log lines, watcher's numbered run results (DOIT-6), poster grid with density/sort toggles, WS badge
refresh, collapse-rail sidebar behaviour, `blocked_reason` visible even on « Identifié » items (§méthode rule 6),
DownloadsPanel's fail-soft `client_available=false` explicit notice + per-torrent live rows (§8/NE-DOIT-PAS-5).

## 2. Core screens: Contrôle, Médias, Pipeline (validated)

### 2.1 Contrôle (`/`) — attention-first, inverted hierarchy

Order: (1) **À traiter** — unified impasse list: all `counts.awaiting_action` cases — verify-blocked
(`position_stage=='verify' && position_state=='blocked'`), non-identifiés (`match=='absent'`), pending decisions
(ambiguous), unknown-kind `other`; each row = mini poster + title + FR reason + direct action « Résoudre → »
(opens media sheet / deck). Empty ⇒ one calm line « Rien à traiter ». Generalizes the existing
`PipelineActionBanner` (which today only surfaces pending decisions). _Replacement confirmations (DOIT-8) are NOT
a row type here_ — no pending-replacement queue exists in the backend; the confirmation remains modal-time at
follow-add (current `already_owned` flow, `routes/acquisition.py:824-840`).
(2) **Activité scraping** — `ScrapeActivityPanel` relocated here (renders null when idle): running scrapes +
« En file : N » pills — it IS « ce qui se passe maintenant », and the §5.2 continuation feeds this same activity
read-model so its queue stays visible (NE-DOIT-PAS-2).
(3) **Dernier run / run en cours** — one-card digest: trigger FR, relative time, « 3 traités · 78 ignorés », link
`/pipeline?run=`; live progress when running.
(4) **Ce qui n'avance pas** (§8/DOIT-2) — the RunDetail skip/defer block promoted here (frontend-only, confirmed).
(5) **Acquisitions** — counters + next cron (merges AcquisitionSummaryCard + SchedulersPanel).
(6) **Santé** — ONE compact row per domain (disks inline bars, index, Redis, providers); detail → Système.
Version demoted to sidebar footer (arbitrated §7.4; hidden in the collapsed `md:w-16` rail; full backend-vs-frontend
build detail lives in Système → État).
Pipeline controls stay here as **one state-dependent control** (Démarrer ⇄ Arrêter + Pause/Reprendre in a menu),
not 4 always-on buttons (B4).

### 2.2 Médias (`/medias`) — the hub; the sheet becomes the media's cockpit

- Grid = current StagingLibrary (kept) with ONE merged filter system (fix D4): segments
  `À traiter · En cours · Prêts · Tous` + existing search/density/sort. Chips carry counts (already served).
- Secondary view « Décisions » (DecisionList/DecisionDetail browse, incl. history) reachable from the grid header;
  `/medias?decision=<id>` opens the deck focused on that decision when pending, the browse detail when closed —
  same behavior as today's `/scraping?decision=` (Decisions.tsx:93-126), relocated. Add to §6 redirect tests.
- **Media sheet** (kept, URL `?media=`) — enriched with **guaranteed egress** (DOIT-7): every state exposes at
  least one action:
  - `ambiguous` → « Résoudre le matching » (existing);
  - `absent` (kind known) → « Rechercher / résoudre manuellement » (existing enqueue);
  - `other` kind unknown → existing Film/Série chooser **plus** « Ignorer / nettoyer » for non-media artifacts
    (the « MOVIES »/« TV SHOWS » folder-artifact case, finding D2) — §7 requires BOTH: explicit confirmation AND
    an append-only journal entry, routed through the existing DeleteAuthority path (never a new deletion
    mechanism); regression-tested (§6);
  - **`matched` + blocked (NEW)** → « Relancer et terminer le pipeline » via the §5.2 continuation endpoint;
  - `matched` + clean → same continuation as a secondary (menu) action, worded « Re-scraper cet élément ».
    Both labels invoke the SAME §5.2 endpoint — contextual wording only, one contract.
- Resolution and continuation show progress (§4-constitution): the timeline advances as the continuation run
  executes (stages query invalidated; the sheet polls `GET /api/pipeline/history/{run_uid}` like DecisionDetail
  does today). **Honest caveat:** when the pipeline lock is held, `spawn_pipeline_run` defers (returns None) — the
  UI shows the §6 « En file » state (never « occupé »), and the timeline resumes when the queued run fires.

### 2.3 Pipeline (`/pipeline`) — the instrument, repaired

- **Stepper fits the width** (fix C1): compressed rail — icon + count per step, active/anomalous steps expanded;
  anomalous step = red, **clickable** → existing `?stage=` FlowBoard drawer listing affected media → media sheet.
  No red signal off-screen, ever. Mobile: compact vertical list (~40px/row), not 8×90px cards (C4).
- « Dernière exécution » card sizes to content (C3); **Historique des exécutions (pipeline runs) repatriated**
  from Maintenance with the `?run=` RunDetail drawer (keeps « Ce qui n'a pas avancé » per-run view too; renders
  any uid incl. maintenance, with a cross-link — see redirects).
- Trigger legend becomes a **tap-accessible popover** on the history header (not hover-only — DOIT-9: reasons must
  be reachable at the finger), replacing the chip-paragraph (C5).

## 3. Acquisition, Système, Config (validated)

### 3.1 Acquisition

- **Suivis = compact rows** (fix E1): poster thumb (~72px) + title + status chip + completeness `89/89` (tabular
  mono) + next due; actions collapse into a `⋯` DropdownMenu (Rechercher maintenant, Cadence, Retirer, Actif) —
  ends primary-amber inflation (E2). « Détail par épisode » expands inline (season by season, §5).
- **English synopses removed** from rows (E3) — available in a detail view only if wanted.
- **Obligations keyed by title** (E4): row leads with media title (new API field, §5), hash demoted to truncated
  mono + copy affordance.
- **Recherches grouped** série → saison with counts (E6) — groups are **expandable**: each episode row keeps its
  status badge and FR reason (notably abandoned/deferred — the acquisition-coherence lies live in the tail), and
  the status filter survives the merge (DOIT-2, §5 épisode-par-épisode).
- **Tabs 5 → 4**: « Recherches » + « Téléchargements » merge into **File d'acquisition** (wanted → grabbed →
  ingest, one §9 flow); `?tab=wanted|downloads` redirect to `?tab=file`. The merged tab **preserves** per-download
  rows (progress, state badge, size, 3s poll) and the explicit « client torrent injoignable » fail-soft notice
  (never an empty state that reads as « rien de téléchargé », NE-DOIT-PAS-1/5). Segmented control with a clear
  active state (E5); horizontal scroll on mobile instead of 3 wrapped rows.
- Watcher tab unchanged (numbered results = DOIT-6 acquis).

### 3.2 Système

Tabs (URL-addressable `?tab=etat|actions|maintenance|journal`, default `etat`): **État** (compact disk rows,
locks & sentinelles with the cached orphan sweep labelled « analyse en arrière-plan, résultat daté », index
health, providers ex-Registre, live EventFeed + RecentEventsTable sized to content, H4) · **Actions** (current
catalog, kept) · **Historique maintenance** (the second « Historique des exécutions » table, renamed « Exécutions
de maintenance », F1 — own `&run=` RunDetail drawer) · **Journal** (deletions journal §7, addressable home).

### 3.3 Config

Master-detail kept. First file auto-selected (G2); **Secrets** becomes a sibling tab of the file list (no more
scroll-to-find); `restart` chip gets a tap-accessible hint « Redémarrage requis après modification » ; secret
descriptions translated FR (E3).

## 4. Transversal visual system (validated)

- **Surface hierarchy — 3 levels max** (H1): page (bare background) → panel (Card, hairline) → row (separator
  only, never a third nested border). Nested StatPanels become rows.
- **Type scale realigned to operator value** (H2): display sizes (36–48px) reserved for attention counts
  (« 2 à traiter »); version/disk-free drop to `--text-base` mono. Critical states never render as 12px chips only.
- **Unified state vocabulary** (H3/E): ONE shared module (e.g. `frontend/src/lib/outcome-labels.ts`) mapping
  backend outcomes/states → {FR label, tone}: `success→Succès`, `error→Échec`, `killed→Interrompu`,
  `queued→En file`, `blocked→Bloqué`, `pending→En attente`, `deferred→Différé`… **All five** divergent maps
  migrate: `SchedulersPanel.outcomeLabel`, `RunHistoryTable.OUTCOME_BADGE`, `RunDetail`'s map, and BOTH
  `acquisition/meta.ts` maps (STATUS_LABEL + RUN_OUTCOME_LABEL), resolving the Réussi/Succès, Arrêté/Interrompu
  and Erreur/Échec divergences. Rendering rule: tone chip = outcomes; StatusDot = live states; mono = machine
  tokens.
- **Empty states normalized** (H4): the good existing pattern (`ds/EmptyState`: icon + title + FR reason)
  everywhere; containers size to content (no more 450px voids).
- **Buttons**: one amber primary per view; secondary = outline/ghost; destructive = danger + §7 confirmation.
  Density: panel padding 12–16px; touch targets ≥44px (kept).
- **Segmented controls**: distinct hover/focus/active treatments (H5). Em-dash placeholders get **tap-accessible**
  disclosure or always-visible « pas encore de données » microcopy — hover-only tooltips are forbidden as the sole
  carrier of a reason (DOIT-9/DOIT-2) (H6).

## 5. Backend scope (validated; grounded)

1. **Obligations title** — enrich `ObligationItem` with `title` (server-side join/resolver from `dispatched_path`
   or the indexer by info_hash); OpenAPI regen (`make openapi`) + commit generated files (known CI guard).
2. **Per-media continuation** (NEW — honestly scoped after code verification): `POST /api/staging/media/{id}/continue`
   (name arbitrated, §7.3). It does NOT reuse `scrape-resolve` (that CLI hard-requires a pending decision row,
   `commands/scrape_resolve.py:182-184`) and there is NO per-media verify/dispatch machinery today. Semantics:
   validate the media exists and is matched, record the intent (for sheet feedback + activity read-model), then
   spawn a **pipeline continuation run** via the existing single trigger authority (`spawn_pipeline_run`, same
   202 + visible « En file » pattern as resolve — §6, NE-DOIT-PAS-7). The run is a full pipeline pass (idempotent;
   fast-skip makes it cheap) — the spec does NOT promise media-scoped execution; if a media-scoped runner is later
   wanted, that is a separate feature. Deferred-when-locked is visible, never silent (§8).
3. **Attention counts** — reuse `counts.awaiting_action` (+ decisions/wanted count queries already in place);
   add a dedicated lightweight `GET /api/attention/counts` only if measurement shows the composite is too chatty
   (staging scan cost).
4. ~~Locks split~~ — already shipped (C25); UI only labels the background sweep + its age.
5. Every mutating route stays staging-guarded + typed (web-ui invariants); route changes ⇒ `make openapi`.

## 6. Delivery method (§10 + §méthode) (validated)

- **Decomposition:** one KanbanMate **epic** + 5 child tickets; each wave = its own `/implement:feature` cycle
  (branch → phases → PR → squash), waves ordered as dependencies. This spec is the shared design; each wave's
  DESIGN.md references the relevant sections.
- **Waves:** V1 shell (sticky sidebar, badges, width — **no route removals**) → V2 Contrôle + Médias (incl.
  §5.2 continuation + relocation of deck/browse/activity; ships `/scraping`→`/medias` redirect) → V3 Pipeline
  (stepper + history repatriation; ships `/maintenance?run=` conditional redirect) → V4 Acquisition (rows, merged
  tab + its redirects, obligations title) → V5 Système + Config + transversal visual pass (label module, empty
  states, buttons; ships `/registry` + `/maintenance` redirects).
  **Sequencing invariant:** a legacy URL's redirect ships only in the wave where its target surface handles every
  carried param (`?media=`, `?decision=`, `?run=`, `?tab=`); until then the legacy route stays fully live — no
  intermediate prod state may break a §3 flow or a deep link (DOIT-10).
- **Per-wave proof:** one PR, version bump, executed prod déroulé with dated captures — never « conforme » on
  empty data; mobile proven via the 390px iframe harness; **SW cache-bust protocol** for every frontend proof
  (unregister SW + caches.delete, compare loaded chunk vs no-store `/index.html` — known stale-bundle trap).
- **Tests:** one regression test per bug fixed en route; the **5 guard tests enumerated in
  `product-intent.md` §méthode (« Les 5 tests de garde »)** stay green; redirect map tested (old URLs → new,
  incl. query params and the conditional `/maintenance?run=` rule); `outcome-labels` module unit-tested; WS badge
  behaviour kept under test; « Ignorer / nettoyer » journal-entry regression test (§7). **Existing page suites
  migrate with their surfaces** (Dashboard.test → Contrôle, Decisions.test → Médias, Maintenance.test → Système,
  router/nav/AppShell tests re-keyed off `/scraping`) — wave estimates must include this.
- Frontend gates: lint + typecheck + vitest before every commit (known CI incidents).

## 7. Operator arbitrations — RESOLVED 2026-07-16 (nothing self-labelled out-of-scope, §méthode rule 4)

1. « MOVIES »/« TV SHOWS » category-folder artifacts: **keep surfacing them** (§8 honesty) and add the
   « Ignorer / nettoyer » egress (§7 confirmation + append-only journal via DeleteAuthority). The read-model does
   NOT filter them.
2. Wanted/Téléchargements merge into « File d'acquisition »: **confirmed** (residual muscle-memory risk accepted;
   redirects cover URLs).
3. Continuation endpoint name: **`continue`** — `POST /api/staging/media/{id}/continue` (contract as in §5.2).
4. Version placement: **sidebar footer** (hidden in collapsed rail; detail in Système → État).
