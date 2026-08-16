# webui-ux — Post-S7 Web-UI UX Polish + Full-Interface Overhaul

**codename**: webui-ux
**commit_type**: feat
**bump**: minor (0.47.0 → 0.48.0)
**kanban**: #248
**merge**: manual (Opus guarantor + adversarial review before human-gated merge)

## Purpose

The S1–S7 TorrentMate web-UI epic is fully shipped and deployed. This feature is a
**two-part UX effort** on that already-shipped surface, from operator feedback while using
the live app:

- **Part A** — five targeted fixes from the operator's post-S7 backlog
  (memory `feedback_post_s7_ux_backlog`): Maintenance StatPanel legibility, Registry
  sub-circuit grouping, Pipeline page UX, Config SchemaForm redesign, Scraping page refonte.
- **Part B** — a **full-interface UX/design/ergonomics overhaul** of **every** page, driven
  by a **Chrome-tested-on-staging redesign loop** until each page meets a checkable "perfect"
  rubric (memory `project_webui_ux_full_overhaul_directive`).

## Non-goals / hard constraints

- **Do NOT regress S1–S7 invariants** (`project_webui_review_shipped`): every mutating endpoint
  stays `require_not_staging` + typed (`response_model` → `make openapi` on any route change);
  the single `guarded_api` auth perimeter (never per-route `Depends(require_session)`); runners
  hold `pipeline.lock` for their lifetime; epoch step timestamps; boot-cached BUILD_COMMIT.
- **Stack unchanged**: FastAPI + Pydantic v2 backend; React 19 + Vite + TS strict (no `any`) +
  TanStack Query + shadcn; PWA mobile-first.
- **Never a local server on 8710/8711** (`feedback_never_local_server_on_prod_port`). The Chrome
  preview environment is **staging** (`tm-staging.iznogoudatall.xyz`), fed by pushing
  `feat/webui-ux` → the `staging` branch (autodeploy). Prod (8710, tracks `main`) stays on stable
  `main` throughout dev; re-sync staging→main only at the final merge.
- **Staging is read-only** (`PERSONALSCRAPER_WEB_ROLE=staging` → 403 on writes). The Chrome loop
  therefore validates **visual / layout / ergonomics / responsive** (which is the stated task);
  write-flow correctness is covered by unit/e2e tests + a prod spot-check, not the Chrome loop.

## Architecture context (from the code-grounded survey)

- **Cross-process**: the web process is separate from the pipeline/watcher process. Live pipeline
  state crosses ONLY via the Redis→WS event stream; persisted state (acquire.db, library.db) is
  read directly per-request (`with closing(sqlite3.connect(...))`, WAL, lock-free reads).
- **Pipeline run data**: `pipeline_run.steps_json` persists only per-step timing+status;
  rich `StepReport` (counts, failed_items, unmatched_paths) + per-item `ItemProgressed` live ONLY
  on the event bus at runtime (`personalscraper/models.py:62`, `pipeline_events.py`,
  `docs/reference/event-bus.md`). ⇒ **interpreted logs for a LIVE run** = a frontend reducer over
  the WS stream; **for the persisted last-run report** = we must enrich `steps_json` with the
  StepReport summary counts at `update_step`/`finalize` time (`pipeline_history.py:170`).
- **Triggers** (`pipeline_run.trigger`, free TEXT, no enum): `cli`, `web`, `cron`, `completion`,
  `safety_net`, `manual` — sources `run_journal.py:160`, `web/decisions/runner.py:267`,
  `acquire/watcher.py:{173,218,261}`. Shown raw in `RunHistoryTable.tsx:142` (no label map).
- **shadcn gap**: no Accordion/Collapsible/Tabs component yet (native `<details>` + badge chips in
  use). Custom design-system parts: `StatPanel`, `StatusDot`, `LogLine`, `PipelineStepper`.

---

## Part A — targeted fixes

### Phase 1 — Quick presentation fixes (low-risk, no product ambiguity)

**1a. Maintenance "Santé de l'index" StatPanel legibility.** `IndexHealthPanel.tsx:247` stats grid
is `grid-cols-2` with no responsive breakpoint; the custom `StatPanel` secondary text clips /
overlaps (operator screenshot: `ITEMS 1837` / `FICHIERS 97605` overflow with `19… / To`
fragments). Fix the panel grid (`grid-cols-1 md:grid-cols-2 xl:grid-cols-4` parent already;
inner stat grid needs responsive cols + min-width-0 + truncation-safe secondary line). Audit the
`StatPanel` component itself (label/value/secondary layout) so long numbers + secondary units
never overlap at any width.

**1b. Registry `*-bootstrap` / `*-download` sub-circuit grouping.** `RegistryPage.tsx` renders one
flat card per provider, so `tvdb` and `tvdb-bootstrap` look like a duplicate. `tvdb-bootstrap`
(`api/_contracts.py` `TVDB_BOOTSTRAP`) is the TVDB v4 auth/token circuit — deliberately separate.
Group sub-circuits (`<provider>-bootstrap`, `<provider>-download`, …) visually **under their
parent provider card** with a clear label/tooltip ("circuit d'authentification TVDB v4"). Pure
frontend grouping over the existing `GET /api/registry/status` payload; no API change.

**ACCEPTANCE (Chrome, staging):** Maintenance index-health cards legible at 375px + 1280px (no
overlap/clip); Registry shows `tvdb` with `tvdb-bootstrap` nested/labelled, not as a twin card.

### Phase 2 — Pipeline page UX

- **Trigger names + legend.** Add `frontend/src/components/pipeline/triggers.ts` (mirroring
  `components/decisions/triggers.ts`): map raw trigger → human label + tone + one-line meaning
  (`completion` → "Fin de téléchargement", `safety_net` → "Filet de sécurité (intervalle mini)",
  `manual` → "Déclenché manuellement", `cli`, `web`, `cron`). Render a small legend/caption.
- **Interpreted logs (accordion) replacing raw logs by default.** Add an `Accordion` primitive to
  `components/ui/`. On the Pipeline page, the raw WS log view collapses into an accordion (hidden
  by default); the default view is an **interpreted-log reducer** over the live WS event stream
  (`StepStarted`/`StepCompleted`/`ItemProgressed`/`StepErrored`) producing plain French lines:
  download-folder scan, newly collected items, move-to-staging (what→where), cleaning
  (before→after), scrape ok / ambiguous-awaiting-decision, trailers dl/unavailable, dispatch
  destination per media. Reuses the `event.data` already streamed per `run_uid`.
- **Persist last-run StepReport summary** so the interpreted last-run report survives past the live
  stream: enrich `steps_json` entries at `pipeline_history.update_step`/`finalize` with the
  StepReport summary (`success_count`/`skip_count`/`error_count`/`counts`/`unmatched_paths` length).
  Additive column-shape change (no migration — `steps_json` is JSON); typed via the run-detail
  response_model → `make openapi`.
- **Remove run-history duplication.** `RunHistoryTable` renders on both Pipeline + Maintenance. Drop
  it from the Pipeline page (keep only on Maintenance). No backend change.
- **Always keep the last report.** When idle, the Pipeline page shows the most recent run's
  interpreted summary (query `GET /api/pipeline/history?limit=1`) until a newer run replaces it —
  never blanks.

**ACCEPTANCE:** trigger labels + legend visible; raw logs collapsed by default with interpreted
lines shown; no run-history table on Pipeline; last-run report visible when idle.

### Phase 3 — Config SchemaForm redesign

Keep the auto-render from `Config.model_json_schema()` (decision locked). The current
`SchemaForm.tsx` already recurses with typed inputs (`Input`/`Switch`/`Select`), `humanize()`
labels, per-field 422 mapping, and native `<details>` sections — the complaint is **visual /
ergonomic**. Redesign:

- Replace native `<details>` with a styled `Accordion`/`Collapsible` (shadcn primitive from
  Phase 2) — consistent chrome, chevrons, spacing.
- **Domain section grouping** at the top level (each top-level object = a titled, collapsible
  section with its description) instead of an undifferentiated nested tree.
- **Human labels + descriptions**: keep `title` when the schema provides it, humanize keys
  otherwise; always surface `description` as helper text; mark required + shadowed-by-local keys.
- **Type-appropriate inputs** already mostly present — audit: bool→Switch, enum→Select,
  int/number→number Input, path-like strings could get a monospace hint; arrays/objects keep the
  add/remove editors but restyled.
- **Inline validation** on blur (not only on save) where cheap; keep the 422 server mapping.
- **Responsive**: 2-col peer-field grid on desktop (`md:grid-cols-2`), single column mobile;
  the FileList sidebar collapses to a top selector on mobile.

**ACCEPTANCE:** Config page legible + navigable at 375px + 1280px; sections collapsible with human
labels; no raw unstyled `<details>`; a save round-trips (unit/e2e, since staging is read-only).

### Phase 4 — Scraping / decisions page refonte + parallel scraping

**UX (decision locked: single flat list + optional filters + inline actions — NOT a kanban board).**
Today `Decisions.tsx` uses status **filter chips** (`pending`/`resolved`/`dismissed`/`superseded`
→ En attente/Résolues/Ignorées/Remplacées) + a list/detail split. Rework:

- One flat, always-visible list of all decisions with **optional** filter chips (not mandatory
  tabs) + a status count on each; default = show all (or pending-first) rather than a forced tab.
- **Clarify the confusing states**: rename/relabel `dismissed` → "Ignorée (laissée telle quelle)"
  and `superseded` → "Remplacée (re-scrapée depuis)" with tooltips; consider a plain "Traitée"
  umbrella. No enum/DB change — presentation only (backend `status` values stay).
- **Inline per-row actions** to advance/relaunch (resolve/dismiss/re-search) without leaving the
  list where possible; detail panel remains for candidate selection.

**Parallel scraping (backend — riskiest item; explicit safety design).** Today the decision runner
holds no lock but the child `scrape-resolve` self-acquires the **global** `pipeline.lock` for its
lifetime (`web/decisions/runner.py:14`), so resolves serialize. Design a **scoped, scrape-only
lock** so disjoint staging items resolve in parallel while the global single-writer guarantee for
dispatch/move is preserved:

- `scrape-resolve` operates on ONE staging path (metadata/NFO/artwork only — it does not dispatch/
  move). Two resolves on **different** staging paths do not share filesystem targets.
- Replace the global `pipeline.lock` acquisition in the `scrape-resolve` path with a **per-staging-
  path lock** (`<data_dir>/locks/scrape-<hash(staging_path)>.lock`), so concurrent resolves on
  distinct items proceed; a second resolve of the SAME item still blocks (idempotent guard).
- The global `pipeline.lock` remains held by full-pipeline runs and dispatch/maintenance — a
  scrape-resolve must still refuse to start if a full pipeline run holds the global lock (read-only
  check), preventing a scrape racing a dispatch of the same tree.
- Web layer: allow multiple concurrent decision runners (remove the single-runner 409 where it was
  global; keep the per-decision 409 so the same decision can't double-launch).

**ACCEPTANCE:** flat list + optional filters render; relabeled states with tooltips; two decisions
on distinct staging paths resolve concurrently (integration test with two temp staging dirs);
same-item double-resolve still 409; a scrape-resolve refuses while the global pipeline.lock is held.

### Phase 5 — Dashboard reorg + scheduler overview

- **Move event panels to Maintenance.** `EventFeed` + `RecentEventsTable`
  (`components/dashboard/`) are self-contained, both read one `useEventStreamContext()`. Relocate
  both to the Maintenance page; Dashboard keeps `HealthCard` + `VersionCard` + the new scheduler
  overview.
- **Scheduler / cron / watcher overview.** New typed read endpoint (extend
  `GET /api/acquisition/status` or add `GET /api/maintenance/schedulers`) aggregating each scheduled
  agent: **watcher** (`personalscraper-watch`: enabled = ¬`data_dir/watcher.paused`, last run =
  `acquire.db watch_state.last_successful_run_at`); **follow-detect** (03:00), **grab**
  (03:20 & 15:20), **index-enrich** (Sun 04:30) from a static schedule registry mirroring
  `ecosystem.config.js`, with last-run/outcome from `pipeline_run` (by trigger/command). Each row:
  name, kind (watcher/cron), schedule-or-enabled, last_run_at, last_outcome. Typed response_model →
  `make openapi`. A Dashboard panel renders the overview ("Planificateurs").

**ACCEPTANCE:** Dashboard no longer shows the event feed/table (now on Maintenance); Dashboard shows
a scheduler overview with the watcher + 3 crons, each with last-run; endpoint typed + in openapi.

### Backend fold-in — followed_series dedup (safe, real bug)

`followed_series.media_ref_json` has no UNIQUE constraint; dedup is app-level
(`find_by_ref ORDER BY id LIMIT 1`), which is racy. Add acquire.db migration `002`: dedup existing
rows (keep lowest id, deactivate/merge dups), then `CREATE UNIQUE INDEX` on `media_ref_json`
(canonical fixed-key JSON from `_media_ref_to_json` → stable text). Switch `store.add` to
`INSERT … ON CONFLICT(media_ref_json) DO UPDATE`/idempotent reactivate. Regression test for the
race. (This is the only backend fold-in in scope.)

### Backend fold-in NOT taken — quality_profile editor (BLOCKED, documented)

`quality_profile_json` exists end-to-end for READ but the grab/search phase does not consume it
(RP3a deferred; explicit "do NOT expose an editor until the backend consumes it" comment in
`web/models/acquisition.py:154`). Exposing an editor now = a no-op footgun (cf. the S4
`process_clean` decision). **Held as a documented follow-up** requiring the RP3a backend consumer
first; not implemented in webui-ux unless the operator scopes full RP3a. (Open item — surfaced to
the operator, not silently dropped, per `feedback_nothing_out_of_scope_without_signoff`.)

---

## Part B — full-interface UX overhaul loop (after Part A)

After Part A, audit + redesign **every** page against the rubric below, in a
deploy→Chrome-test→fix loop on staging, until each page passes at mobile (~375px) AND desktop
(~1280px+). Pages: Login, Dashboard, Pipeline, Maintenance, Registry, Config, Decisions,
Acquisition, plus the app shell/nav.

**"Perfect" rubric (per-page ACCEPTANCE):**

1. **Design system respected** — shadcn components used consistently; consistent spacing/typography/
   color tokens; no ad-hoc one-off styles; matches the shell.
2. **Responsive / PWA** — no horizontal overflow, no clipped/overlapping text at 375px; usable at
   ≥1280px; adequate touch targets.
3. **Ergonomics** — primary action obvious; destructive actions guarded; loading/error/EMPTY states
   present (no data-illusion); sensible hierarchy; no dead-ends.
4. **Consistency across pages** — shared header/nav pattern; uniform table/card/badge conventions.
5. **No broken UX** — inline validation, action feedback (toasts), zero console errors.

**Loop protocol (per page):**

1. Deploy current `feat/webui-ux` → `staging` branch (autodeploy) → wait for health.
2. Chrome (`/chrome`): authenticate to `tm-staging.iznogoudatall.xyz` (forged HS256 `tm_session`
   cookie from `.env WEB_JWT_SECRET`, sub = `config/web.json5` username, OR the login form),
   navigate the page, screenshot at 375px + 1280px, read console.
3. Assess vs rubric → list concrete findings.
4. Fix (frontend; backend only where a display gap requires it) → local gates
   (`npm run lint && typecheck && vitest run`; `make check` if backend touched) → commit → redeploy.
5. Re-test → repeat until the page passes all 5 rubric points.

Part B is inherently iterative — the plan captures the protocol + the per-page checklist, not a
fixed sub-phase count. Findings that need backend work become explicit tracked items (never
silently deferred).

---

## Phase list (for the plan)

| #   | Phase                                | Scope                                                                                                                               |
| --- | ------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Quick presentation fixes             | Maintenance StatPanel legibility + Registry sub-circuit grouping                                                                    |
| 2   | Pipeline page UX                     | triggers+legend, Accordion primitive, interpreted-log reducer, persist StepReport summary, remove run-history dup, keep last report |
| 3   | Config SchemaForm redesign           | styled collapsible sections, human labels, typed inputs, inline validation, responsive                                              |
| 4   | Scraping refonte + parallel scraping | flat list + optional filters + inline actions + relabel states; scoped per-staging-path scrape lock                                 |
| 5   | Dashboard reorg + scheduler overview | move event panels→Maintenance; scheduler/cron/watcher overview endpoint + panel                                                     |
| 6   | Backend fold-in                      | followed_series UNIQUE-index dedup migration 002 + ON CONFLICT                                                                      |
| 7   | Full-interface UX overhaul loop      | per-page Chrome-on-staging redesign against the rubric (Part B)                                                                     |

## Testing

- Backend: unit + e2e (`@pytest.mark.e2e`), no `Design:` markers on e2e (feature-map cascade trap
  `project_openapi_drift_ci_guard` / feature-map). Any route change ⇒ `make openapi` + commit
  `frontend/openapi.json` + `schema.d.ts`.
- Frontend: `npm run lint && npm run typecheck && npx vitest run` before every commit
  (`feedback_frontend_ci_eslint_gate`).
- Live: Chrome-on-staging per the Part B loop; forged-JWT curl ACC for the new endpoints.
- Guarantor: adversarial review before the human-gated merge; commit before every mutation-check
  (`feedback_commit_before_mutation_check`).
