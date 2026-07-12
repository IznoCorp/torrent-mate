# TorrentMate — DESIGN_VISION

**Feature codename:** `webui-overhaul` · **Branch:** `feat/webui-overhaul` (off the `fix/webui-polish`
foundation) · **Author/guarantor:** orchestrator (Opus) · **Executors:** DeepSeek sub-agents only.

A deep UX/UI redesign of the TorrentMate web UI around three product objectives — a **living
pipeline**, a **scraping & matching** workspace, and **automated acquisitions** — grounded in the
data the backend actually exposes, extending the API where a needed datum is missing.

---

## 1. Immersion — architecture & real data (PHASE 0 result)

**Stack.** React 19 + Vite + TS strict (no `any`), TanStack Query, shadcn/ui + Tailwind v4
(`@theme` tokens), a bespoke DS layer (`components/ds/*`: StatPanel, StatusDot, LogLine), Redis→WS
live event stream (`useEventStreamContext`), FastAPI backend, SQLite (`library.db` indexer +
`scrape_decision`, `followed_series`, `wanted`, `pipeline_run` tables). Auth = single `guarded_api`;
mutations `require_not_staging` + `X-Requested-With`; every route typed → OpenAPI → `schema.d.ts`.

**Backend data surfaces (verified):**

| Domain                  | Endpoints                                                                                      | Real fields available                                                                                                                                                                 | Gaps for the vision                                                                           |
| ----------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Pipeline                | `POST /run\|pause\|resume\|kill\|watcher`, `GET /status`, `GET /history[/{uid}]`               | run state, per-step status + counts, run history                                                                                                                                      | **no per-media stage position**; **no per-stage aggregate counts**                            |
| Decisions (matching)    | `GET /`, `GET /{id}`, `POST /{id}/search\|resolve\|dismiss`                                    | `DecisionCandidate{provider,provider_id,title,year,score,poster_url,overview}`, trigger (`below_threshold\|mid_band\|ambiguous`), status (`pending\|resolved\|dismissed\|superseded`) | good — full candidate posters/overviews already there                                         |
| Acquisitions            | `GET /followed\|wanted\|obligations\|status`, `POST /followed`, `PATCH\|DELETE /followed/{id}` | `active`, `cadence.interval_minutes`, `wanted_pending`, `added_at`, provider ids                                                                                                      | **no poster/art**, **no next-trigger**, **no media search**, **no per-series manual trigger** |
| Staging library (OBJ2A) | —                                                                                              | (scraped NFO+artwork on disk; resolved decisions)                                                                                                                                     | **no endpoint** listing staged, matched media with metadata                                   |

**Derivable without new data:** the 3 acquisition états (`Désactivé` = `!active`; `En cours` =
`active && wanted_pending>0`; `À jour` = `active && wanted_pending==0`); pipeline live progress (WS
`StepStarted/StepCompleted/StepErrored/ItemProgressed`); matching backlog (decisions `pending`).

**Existing screen lacunes (from the static audit + Chrome loop):** Decisions = thin master-detail
list, no poster comparison, ambiguous states unclear; Acquisition = raw TVDB-id form + dense table,
no posters/feedback; Pipeline = a step stepper + logs, no "where is each media / what's blocked"
overview; cross-cutting data-illusions (failed fetch reads as empty), missing toasts, sub-44px
touch targets, tables that overflow < md. (Foundation fixes already merged/committed: DS color
tokens, shell wordmark, Config F6/F7, event-feed labels, Registry/Maintenance layout.)

---

## 2. Art direction

**Dark-first**, engineered for a control surface watched for long sessions. Keep the existing token
foundation (Geist / Geist Mono, amber `--primary`, signal palette `--success/--warning/--danger/
--info`) and extend it — **do not fork a second style**.

- **Surfaces:** three elevation steps (`--background` canvas → `--card` panel → hovered/active
  raise) with a hairline `--border`; generous negative space; content in a centered `max-w-6xl`
  shell (widen from `5xl` for the board views).
- **Signal-as-structure:** state is color + a `StatusDot`/`Badge`, never color alone (a11y). Amber
  = attention/in-flight, green = settled/ok, red = failure/blocked, blue = informational/queued.
- **Motion (discreet, purposeful):** 150–200 ms ease-out for state/enter transitions; a media
  "moving" between stages animates a brief count tick + row fade — never gratuitous. Respect
  `prefers-reduced-motion`.
- **Typography:** UI in Geist; **all machine data** (ids, counts, ratios, latencies, hashes, paths,
  run_uids) in Geist Mono + `tabular-nums`. Titles `text-xl font-semibold tracking-tight`
  (page) / `CardTitle` (section) — the single header rhythm from the polish pass.
- **Density:** comfortable default; a density toggle only where it earns its keep (media library).
- **Posters** are first-class: media reads as a catalog, not a spreadsheet, wherever art exists.

---

## 3. Design system additions (build FIRST — everything depends on it)

Extend `components/ds/*` (bespoke) and `components/ui/*` (shadcn) with reusable primitives:

- **`PageHeader`** — title + optional description + actions slot; one rhythm across every page.
- **`MediaPoster`** — aspect-2/3 poster with graceful fallback (initials/gradient) + skeleton;
  `kind` movie|tv badge; lazy-loaded. (An eslint DS contract already reserves a `MediaPoster kind`.)
- **`MediaCard`** — poster hero + title/year/ids/overview; hover/expand for detail; selectable.
- **`StageStation`** — one pipeline stage: label, live count, state ring (ok/active/attention/
  blocked), click affordance. Composes into the flow board.
- **`StatusBadge`** — the canonical state chip (tone + dot + French label) unifying the ad-hoc
  badges (folds registry circuit chips, wanted status, decision status).
- **`EmptyState` / `ErrorState`** — one soigné convention (icon + title + hint + optional retry);
  kills the data-illusion class (failed fetch ≠ empty).
- **`Skeleton` shapes** — card/grid/table/row skeletons matching each eventual layout.
- **`Toaster` usage** — a shared `toast` helper wired into every mutation (success/error/gate).
- **`Kbd`** — keyboard-hint chip for the resolution deck.
- **Textarea** primitive (shadcn) to retire the hand-rolled JSON textarea.

These land as one DS lot with unit tests + a lightweight visual story doc, before screen lots.

---

## 4. Information architecture

Nav regrouped around the operator's mental model (French labels):

- **Supervision** — **Pipeline** (OBJ1 living board), **Scraping** (OBJ2: `Bibliothèque` +
  `À résoudre` tabs), **Acquisitions** (OBJ3), **Tableau de bord** (at-a-glance health + what needs
  me + schedulers).
- **Système** — **Maintenance**.
- **Configuration** — **Registre**, **Config**.

The dashboard becomes a genuine "command center": counts per pipeline stage, the **action queue**
(ambiguous + failures, the single "what needs me" list), next scheduled triggers, disk/health.

---

## 5. OBJ1 — Living pipeline: the **Flow Board** (paradigm choice)

**Chosen paradigm: a horizontal Flow Board of stage "stations".** Nine stations
(Arrivée → Staging → Nettoyage → Tri → Matching → Scraping → Trailers → Vérification → Dispatch),
each a `StageStation` showing a **live count**, a **state ring** (ok / active / attention / blocked),
and (where meaningful) a mini split (e.g. Matching: matché / ambigu / sans-match). Between stations,
a thin connector conveys flow direction; a media moving forward ticks the counts with a discreet
animation. Clicking a station opens a **Stage Drawer** listing the items currently at that stage;
clicking an item opens the **Media Timeline** (its stage history + current blocker + actions).

**Why the Flow Board over the alternatives:**

- **vs. kanban columns:** items don't persist as long-lived cards in per-stage columns here — most
  stages are transient batch steps; a kanban implies manual card dragging that doesn't map to an
  automated pipeline. The board keeps the _flow_ metaphor without faking drag semantics.
- **vs. sankey:** beautiful for volume-over-time but poor for "act on this item now" and heavy to
  keep live; we keep a small **throughput sparkline** as a secondary accent, not the primary view.
- **vs. plain table:** a table buries the macro state; the board answers "where is everything, what's
  blocked" in one glance, then drills into a table _inside_ a stage drawer.

The Flow Board is data-backed by a **new `GET /api/pipeline/stages`** aggregation (counts +
attention/blocked per stage, sourced from staging dir + `scrape_decision` + indexer + last run),
refreshed live by the existing WS stream. The **action queue** (ambiguous + failures) is surfaced
both on the board (attention rings) and as a persistent, impossible-to-miss list on the dashboard.

---

## 6. OBJ2 — Scraping & Matching workspace

Two tabs under **Scraping**:

**A. Bibliothèque (staged, matched media).** A poster grid (`MediaCard`), density-adjustable, with
title/id/year/overview and, for series, a season/episode disclosure. Data: **new
`GET /api/staging/media`** listing currently-staged, scraped media (metadata + artwork from the
resolved decision + on-disk NFO/artwork; falls back to the indexer catalog for already-dispatched).
Search/filter by kind/title; virtualized grid.

**B. À résoudre (the Resolution Deck).** A focused, keyboard-driven decision surface over
`pending` decisions with `trigger ∈ {ambiguous, below_threshold, mid_band}`. For each item: the
extracted folder title/year on the left; **candidate posters compared side-by-side** (poster, title,
year, overview, score) as selectable cards; a manual **title/year search** override
(`POST /{id}/search`) that appends fresh candidates; **one-click validate** (`resolve` with
`via=pick|search_override`) → the item animates out and the deck **auto-advances to the next**, with
a **remaining counter** and full **keyboard nav** (←/→ candidates, ⏎ validate, `s` search, `d`
dismiss, `j/k` prev/next). Target: resolve 20 ambiguous in ~2 minutes. Dismiss + superseded states
get plain-language labels and never read as data-illusions.

---

## 7. OBJ3 — Automated acquisitions

**Add via search.** A media search box → **new `GET /api/acquisition/search?q=`** (reuses the
provider search that already backs decisions) → result **cards** (poster, year, type, overview,
season/episode count for series) → **follow in one click** (`POST /followed`).

**Watch list.** `MediaCard`-style rows/cards, each showing: poster + title; **état** badge (`En
cours` / `À jour` / `Désactivé`, derived as in §1); **prochain déclenchement** (new computed
`next_trigger_at` = `last_search + cadence.interval_minutes`, exposed on `FollowedSeriesItem`);
`wanted_pending` count; an **activer/désactiver** toggle (`PATCH active`); a **déclencher
maintenant** button with live feedback (new **`POST /api/acquisition/followed/{id}/search`** →
enqueues a search now, toast + state) ; and remove (guarded confirm). Posters via a
**`poster_url` added to `FollowedSeriesItem`** (looked up from the provider by id, cached).

The screen conveys control: what's running (En cours, pulsing), what's waiting (À jour + next
trigger), what's paused (Désactivé, muted).

---

## 8. Backend endpoints to add (typed, guarded, `make openapi`)

1. `GET /api/pipeline/stages` → `StagesResponse{ stages: [{ key, label, count, attention, blocked,
split? }] }` — the Flow Board aggregation. Read-only (safe on staging).
2. `GET /api/staging/media` → `StagingMediaResponse{ items: [{ id, kind, title, year, poster_url,
overview, provider_ids, seasons? }] , total }` — OBJ2A library.
3. `GET /api/acquisition/search?q=&kind=` → `MediaSearchResponse{ results: [{ provider, provider_id,
title, year, kind, poster_url, overview, season_count? }] }` — OBJ3 add-by-search.
4. `POST /api/acquisition/followed/{id}/search` (202, `require_not_staging` + XRW) → enqueues a
   wanted-search run for that series now; returns a run/ack.
5. Extend `FollowedSeriesItem` with `state: Literal["running","up_to_date","disabled"]`,
   `next_trigger_at: float | None`, `poster_url: str | None`.

Each is a typed Pydantic `response_model`; any route change ⇒ `make openapi` + commit the regenerated
`openapi.json` + `schema.d.ts`. All read endpoints must be staging-safe; all writes staging-guarded.
Never regress S1–S7 invariants (single `guarded_api`, epoch timestamps, boot-cached build sha).

---

## 9. Work plan — delegable lots (DeepSeek execution, Opus guarantor)

Sequence: **DS foundation → backend endpoints (parallel) → screens (parallel per objective) →
transverse pass → audit**. Each lot = its own commit(s), gated (frontend: eslint+tsc+vitest;
backend: `make lint` slice + pytest slice + `make openapi`), guarantor-verified before integration.

| Lot                     | Scope                                                                 | Depends on            | Executor |
| ----------------------- | --------------------------------------------------------------------- | --------------------- | -------- |
| **L0 DS**               | §3 primitives + tests + tokens                                        | —                     | DeepSeek |
| **L1 API-pipeline**     | `GET /pipeline/stages` + model + tests + openapi                      | —                     | DeepSeek |
| **L2 API-staging**      | `GET /staging/media` + model + tests + openapi                        | —                     | DeepSeek |
| **L3 API-acq**          | search + manual-trigger + FollowedSeriesItem fields + tests + openapi | —                     | DeepSeek |
| **L4 Pipeline board**   | Flow Board + stage drawer + media timeline + WS wiring                | L0,L1                 | DeepSeek |
| **L5 Scraping/Library** | Bibliothèque grid                                                     | L0,L2                 | DeepSeek |
| **L6 Resolution deck**  | keyboard resolution flow                                              | L0 (candidates exist) | DeepSeek |
| **L7 Acquisitions**     | search-add + watch list + états + triggers                            | L0,L3                 | DeepSeek |
| **L8 Dashboard**        | command-center reorg + action queue                                   | L0,L1                 | DeepSeek |
| **L9 Transverse**       | responsive/a11y/empty+error/skeleton/toast sweep + regressions        | L4–L8                 | DeepSeek |
| **L10 Audit**           | brief checklist E2E, build green, `DESIGN_REPORT.md`                  | all                   | Opus     |

**Guarantor protocol (every lot):** independently re-run the gates, read the diff, verify DS
conformity + no `any` + French labels + real-data wiring + no S1–S7 regression + tests actually
exercise behavior (no vacuous asserts); reject/redo non-conforming work. DeepSeek dispatches have a
~10-min wrapper cap → lots are sized to bank work incrementally (commit-after-each-file discipline in
the prompt); on timeout, the orchestrator inspects, finishes, and commits.

**Testing surface (unchanged constraints):** front tested on `tm-staging` via Chrome MCP (desktop
live; mobile via mobile-first class reads — the MCP window can't shrink below ~1920px). Staging is
read-only (writes 403) → write-flow correctness validated via unit/e2e + prod spot-check.

**Deploy/verify loop:** push `feat/webui-overhaul` → `staging` per integrated lot → Chrome-verify.
