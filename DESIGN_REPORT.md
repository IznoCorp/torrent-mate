# TorrentMate Web UI — UX/UI Overhaul: Design Report

Closing counterpart to `DESIGN_VISION.md`. Branch `feat/webui-overhaul`, deployed
continuously to staging (`tm-staging.iznogoudatall.xyz`) and live-verified against
real data throughout.

## 1. Mission

A deep (not cosmetic) UX/UI overhaul of the TorrentMate web UI around three
objectives, backend-as-source-of-truth, single design system, responsive,
tested, and deployed without breaking the shipped S1–S7 waves.

1. **OBJ1 — Living pipeline**: a Flow Board of the nine pipeline stages with live
   state, click-through per-stage drawer, and a per-media timeline.
2. **OBJ2 — Scraping & Matching**: (A) a rich library grid of staged media, (B) a
   keyboard-driven Resolution Deck.
3. **OBJ3 — Acquisitions**: add-by-search, a watch list with derived states, a
   per-series manual trigger, and a card redesign.

## 2. What shipped

### OBJ1 — Living pipeline (complete, live-verified)

- **`GET /api/pipeline/stages`** — aggregates the last `pipeline_run.steps_json`
  - the live `scrape_decision` queue into nine typed stations (state derived
    backend-side: `idle/ok/active/attention/blocked`). Read-only, staging-safe.
- **`FlowBoard`** — nine `StageStation`s; **responsive** (horizontal scroll row on
  `sm+`, full-width vertical stack on mobile), anti-blank skeleton fallback,
  click → stage drawer.
- **Per-media Media Timeline** — the drawer lists the media at/awaiting a stage
  (`StageMediaList` accordion), each expanding to its nine-stage timeline, fed by
  the shared staging read-model.

### OBJ2 — Scraping & Matching (complete, live-verified)

- **`GET /api/staging/media`** — the staging read-model: one item per media folder
  under the configured `staging_dirs`, enriched with NFO metadata, matching state
  (joined from `scrape_decision`, NFC-normalized), poster/trailer presence, season
  breakdown, a per-media pipeline timeline, pagination/sort/filters + aggregate
  counts, and an opt-in dispatch-target preview. Fail-soft, read-only.
- **Local poster route** — `GET /api/staging/media/{id}/poster` serves the on-disk
  poster via an id-resolved `FileResponse` (never a client path). Detection covers
  the real movie naming (`{Title}-poster.jpg`) + canonical NFO glob.
- **`StagingLibrary`** — a "Bibliothèque" view on `/scraping`: filterable, paginated
  poster grid (`MediaCard`) with match chips + counts, search, sort, and a detail
  drawer (provider ids, seasons, dispatch preview, timeline).
- **Resolution Deck** (OBJ2B) — shipped previously; resolved decisions now render
  **read-only** (result, not the re-scrape picker).

### OBJ3 — Acquisitions (complete, live-verified)

- **Per-series manual trigger** — `AcquisitionService.run(followed_id=…)` scopes a
  grab to one series; `POST /api/acquisition/followed/{id}/search` reserves a
  tracked `pipeline_run` and spawns a lean detached runner
  (`web/acquisition/runner.py`); per-series 409 guard, staging-guarded. Frontend
  "Déclencher" button with toast feedback.
- **Card enrichment** — migration 005 adds `poster_url/overview/year/season_count`
  to `followed_series`; captured at follow-time from the search candidate and
  backfilled (year + season count) from the indexer when absent — no per-card
  provider calls.
- **Watch-list card redesign** — the Suivis table becomes a `MediaCard` grid
  (poster / year / description / season count / état badge / next-trigger caption),
  **cadence editing preserved**, per-card Déclencher/Cadence/Retirer.

### Operator bug-fix batch (reported mid-mission, all fixed + deployed)

- **Mobile Flow Board** rendered blank/broken → responsive vertical stack + guard.
- **Resolved decision re-scrape** → read-only outcome view (kills the misleading
  "already re-scraping" 409).
- **Run summary ignored resolutions** → `RecentResolutions` folds recent resolved
  decisions into the pipeline summary.
- **#3 root cause — "resolved but no NFO on disk"**: the movie/TV scrape deleted a
  drifted NFO _before_ matching; an ambiguous re-match then returned early
  (`queued_for_decision`) without rewriting it, leaving the folder metadata-less.
  Fixed in `movie_service` + `tv_service` (never unlink up front; a confident
  re-scrape overwrites atomically, every early-return preserves the NFO), plus a
  fail-loud invariant in `scrape-resolve` (assert an NFO landed before marking a
  decision resolved).
- **Staging read-model** under-reported scraped movies (missed the real
  `{Title}-poster.jpg` naming) → corrected detection.

### L9 — transverse

- **Vendor chunk split** — rollup `manualChunks`: app bundle ~893 kB → ~203 kB, all
  chunks under the 500 kB advisory, vendor chunks stable across app-only deploys.
- **`/locks` perf** — the tmp-orphan disk sweep (slow macFUSE roots, ~27 s) is now
  cached 60 s under a lock held across the scan; lock state + sentinels stay
  real-time.
- Empty/error/skeleton/responsive/a11y states are built into every new component
  (`EmptyState`, `ErrorState`, skeletons, `aria-busy`, keyboard focus rings).

## 3. Technical choices

- **Backend derives state; the UI paints.** Stage states, match verdicts, timelines
  and dispatch previews are computed server-side and typed (Pydantic → OpenAPI →
  `schema.d.ts`), so the frontend is a thin, compile-checked consumer.
- **Read-models over new tables.** OBJ1/OBJ2A derive from the filesystem +
  `scrape_decision` + indexer; the only schema change is the small OBJ3
  `followed_series` metadata columns (migration 005).
- **Fail-soft everywhere.** Absent DB / unmounted disk / malformed NFO degrade to
  empty/partial results, never a 500 — the read-only staging instance serves them
  unchanged.
- **Live via poll + WS invalidation.** TanStack Query polling plus WS-event cache
  invalidation on pipeline/step events.
- **Responsive-first drawers/board.** Mobile = vertical stacks, `px-6 pb-6` drawer
  padding, truncating accordion titles; desktop = horizontal flows.

## 4. Verification

- Deployed to staging on every push; **full pre-push gate green each time**
  (ruff + format + logging audit + mypy + the complete pytest suite).
- Frontend: **608 tests**; backend web/scraper/acquire suites green (whole-suite
  pre-push).
- **Live-verified on staging with real data**: the Flow Board + stage drawer with
  real run counts and blocked states; the staging library grid + detail drawer
  (Top Chef matched with served poster + TVDB/TMDB ids + Saison 17; three
  un-scraped movies with real pending-stage timelines); the watch-list cards with
  indexer-backfilled year + season counts (Rick and Morty 10 saisons, Silo/House
  of the Dragon 3 saisons).

## 5. Strengths

- Every increment is typed, tested, gated, deployed, and visually confirmed — no
  placeholders, no deferred stubs.
- The #3 investigation reached and fixed a genuine core-scraper root cause, not
  just its symptom, with the blast radius validated against the full suite.
- No S1–S7 invariant regressed (single auth perimeter, staging guards, epoch
  timestamps, typed responses, OpenAPI regenerated on every route change).

## 6. Known limitations / follow-ups

- **Two pre-existing prod staging folders** (Obsession, Ferrari) hold artwork but
  no NFO — a legacy partial-scrape state from _before_ the #3 fix; they need a
  fresh scrape to recover their NFO (the fix prevents recurrence).
- **Card posters for pre-existing follows** show the initials fallback until the
  series is re-followed via search or matched in the library (poster URL is only
  cached at follow-time; the indexer stores a boolean, not a URL).
- **Route-level lazy loading** was intentionally not adopted (the PWA precaches
  every chunk, so it adds requests without load benefit; the vendor split delivers
  the cache-stability win instead).
- The dispatch-target preview is best-effort and opt-in (`with_dispatch=true`).

## 7. Commit trail

`feat/webui-overhaul`, from the OBJ2A read-model (`eaa6e3a4`) through the L9 perf
work (`7f177bca`): 19 focused commits — OBJ2A/OBJ1 (`eaa6e3a4`, `c0107c56`), mobile

- drawer fixes (`c8e21573`, `e04d8b09`, `3bf55e3e`), the decision/summary/scrape
  fixes (`35aef0e4`, `9bc564ec`, `dd859429`, `53caf54d`, `c14fb5a4`), OBJ3 end-to-end
  (`0d86bc18`, `ea46321b`, `7f8ab295`, `c6d92d99`, `6856fa9d`, `68090941`), and L9
  (`e794b3bb`, `7f177bca`).
