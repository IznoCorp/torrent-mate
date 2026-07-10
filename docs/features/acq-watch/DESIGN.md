# DESIGN — S7 Web UI: Acquisition + Watcher (`acq-watch`)

**Roadmap**: S7 (web-UI wave), KanbanMate ticket #186. Depends on S1 #158 (shell + auth + WS — done)
and RP4 #154 (acquisition events — done).
**Bump**: minor (`0.46.0 → 0.47.0`) — additive read + CRUD surface + new page.
**Commit type**: `feat`.

## 1. Purpose

Expose the acquisition subsystem in the web UI at **/acquisition**: the followed-series list (with
CRUD), the wanted queue (status + history), seed obligations + ratio state, and watcher status —
plus per-series **override rules** editing. Fed by direct reads of the shared `acquire.db` and live
updates from the existing acquisition event stream.

## 2. What already exists (from the code map)

- **`acquire.db`** — shared, on-disk, **WAL** SQLite at `config.acquire.db_path`
  (`paths.data_dir/acquire.db`). Schema `acquire/migrations/001_init.sql` (+002 cross-seed, +003
  watch_state). Tables: **`followed_series`** (id, media_ref_json, title, active, quality_profile_json,
  cadence_json, added_at), **`wanted`** (followed_id FK, media_ref_json, kind, season, episode, status
  ∈ pending/searching/grabbed/done/abandoned, criteria_json, enqueued_at, last_search_at, attempts,
  grabbed_hash), **`seed_obligation`** (info_hash, source_tracker, dispatched_path, min_seed_time_s,
  min_ratio, added_at, satisfied_at, breached_at, released_at), **`ratio_state`** (tracker_name,
  observed_ratio, accumulated_seed_time_s, hnr_count, updated_at), **`watch_state`** (KV:
  `last_successful_run_at`).
- **Store** (`acquire/store.py`): **WAL + BEGIN IMMEDIATE + busy_timeout=5000** per write (`_write_tx`),
  **no lifetime FileLock**, reads lock-free — so the web process may read AND write acquire.db
  concurrently with the pipeline/watcher, exactly like it reads `library.db` for pipeline status.
  Sub-stores: `store.follow` (add / find_by_ref / get / list_active / list_all / set_active),
  `store.wanted`, `store.seed`, `store.watch` (get_last_successful_run_at). Domain model
  `FollowedSeries` (`acquire/domain.py`): media_ref, title, added_at, active, quality_profile_json,
  cadence_json, id.
- **Events** (`acquire/events.py`, all in the catalog, auto-relay to WS): SeriesFollowed/Unfollowed,
  WantedEnqueued/Abandoned, GrabSucceeded/Failed, SeedObligationRecorded/Breached/Satisfied,
  RatioMeasured, WatcherRunTriggered (`reason` ∈ completion/safety_net/manual), CrossSeedInjected/Rejected.
- **Watcher control**: `POST /api/pipeline/watcher {enabled}` already exists (sentinel toggle); the
  status endpoint already surfaces `watcher_enabled`.
- **Frontend**: `/acquisition` is a `ComingSoon` stub (`router.tsx:68`); the nav entry is **already
  active** (`nav.ts:71`, Radar icon) and in the mobile bottom tab bar. Mirror `Pipeline.tsx`
  (status + history + controls) and `Maintenance.tsx` (panels + actions) patterns; `useEventStreamContext`
  for live updates.
- **Override rules**: `cadence_json` (per-series search cadence, **active** — consumed by
  `acquire/desired.py effective_cadence`) and `quality_profile_json` (**RP3a — deferred / not yet
  consumed by the backend**).

## 3. Design decisions

### 3.1 CROSS-PROCESS: direct acquire.db (NOT an event projection)

Unlike S6 (in-memory registry → needed a projection), acquisition state is **persisted** in the
shared WAL `acquire.db`. So S7 reads it **directly** (lock-free) and writes it **directly** via the
store's `_write_tx` (BEGIN IMMEDIATE + busy_timeout — concurrent-writer-safe with the pipeline/watcher).
Live updates come from the acquisition event stream (WS) used only as a "something changed → refetch"
signal (the S2 pipeline pattern), never as the source of truth. A web-side `AcquireStore` opens
`config.acquire.db_path`.

### 3.2 REST — reads (`GET`, guarded_api, staging-allowed)

- `GET /api/acquisition/followed?active=all|active|inactive` → `{items: FollowedSeriesItem[]}` — each:
  id, title, media_ref (tvdb/tmdb/imdb), active, cadence (parsed from cadence_json), added_at (epoch),
  wanted_pending count (a cheap COUNT join to `wanted`), quality_profile (read-only, may be null).
- `GET /api/acquisition/wanted?status=&page=&page_size=` → paginated `{items, total, page, page_size}`
  of wanted rows (id, title, kind, season, episode, status, attempts, enqueued_at, last_search_at).
- `GET /api/acquisition/obligations?status=all|pending|breached|satisfied` → seed obligations joined
  with ratio_state per tracker.
- `GET /api/acquisition/status` → watcher status: `last_successful_run_at` (watch_state, epoch |
  null), `watcher_enabled` (sentinel), `recent_runs` (the last N watcher-triggered `pipeline_run`
  rows from library.db — reuse the existing pipeline history read, filtered to the watcher trigger).
- All timestamps Unix-epoch floats; Pydantic `response_model` → OpenAPI → `schema.d.ts`; fail-soft
  (a DB read error returns an empty list/nulls, never 500).

### 3.3 REST — writes (`POST`/`PATCH`/`DELETE`, guarded_api + `require_not_staging` + XRW)

Follow CRUD, written directly via `store.follow` (the store's BEGIN IMMEDIATE serialises against the
pipeline). Each mutating route: `require_not_staging` (staging 403), `require_x_requested_with` (CSRF).

- `POST /api/acquisition/followed` `{tvdb_id?|tmdb_id?|imdb_id?, title?}` → 201 the created/reactivated
  item. Dedup: `find_by_ref` → if present + inactive, reactivate (set_active True); if present +
  active, 409; else `add`. At least one id required (422 otherwise).
- `PATCH /api/acquisition/followed/{id}` `{active?, cadence?}` → 200 updated item. `active` toggles
  via `set_active`; `cadence` writes `cadence_json` (validated against the cadence shape). 404 on
  unknown id.
- `DELETE /api/acquisition/followed/{id}` → 204 (soft unfollow via `set_active(False)`). 404 on unknown.
- **Watcher control**: reuse the existing `POST /api/pipeline/watcher {enabled}` — S7 does NOT add a
  new watcher route; the page calls the pipeline one.
- **Override-rules scope**: only **cadence** is editable (the active override). `quality_profile_json`
  is surfaced **read-only** with a "not yet enforced (RP3a)" note — editing it would front-run an
  unshipped backend capability (do NOT expose a quality-profile editor).
- **Event emission from web writes is out of scope** (deferred): the acting client re-fetches on the
  mutation response; the pipeline reads fresh DB at detect time; a cross-client live SeriesFollowed
  would need a web-side Redis publisher — noted as a follow-up, not shipped in S7.

### 3.4 Frontend — `/acquisition` page

- Replace the `ComingSoon` stub with an `AcquisitionPage` (nav entry already active).
- Typed client `frontend/src/api/acquisition.ts` + TanStack hooks (`useFollowed`, `useWanted`,
  `useObligations`, `useAcquisitionStatus`, mutations `useFollow`/`useUpdateFollow`/`useUnfollow`).
- Layout (tabs or stacked panels, mirroring Maintenance): **Followed** (table + add form + per-row
  unfollow + edit-cadence dialog), **Wanted** (paginated status table), **Obligations** (seed/ratio
  panel), **Watcher** (status card: last run, enabled toggle → the pipeline watcher route, recent runs).
- Live: `useEventStreamContext` filters acquisition events (SeriesFollowed/Unfollowed, WantedEnqueued/
  Abandoned, GrabSucceeded/Failed, SeedObligation*, RatioMeasured, WatcherRunTriggered) via the R13
  new-events-only ref pattern → invalidate the matching query. Mutations invalidate their own queries.
- Vitest: typed client, each hook, the page (renders each panel, add/unfollow flow, empty states).

## 4. Non-goals

- No quality-profile editing (RP3a deferred — backend doesn't consume it).
- No web-side event emission for follow writes (deferred; acting client invalidates).
- No new watcher route (reuse the pipeline watcher toggle).
- No manual "grab now" / "detect now" trigger from the web in S7 (status/history/CRUD only; a manual
  trigger is a candidate follow-up).

## 5. Phases

1. **Read routes + models** — web-side `AcquireStore` read wiring; `GET /api/acquisition/{followed,
wanted,obligations,status}` + Pydantic models + openapi regen + route tests (auth, shape, staging-
   allowed, fail-soft, pagination).
2. **Write routes** — `POST/PATCH/DELETE /api/acquisition/followed` (store writes, dedup/reactivate,
   staging-guard + XRW, 409/404/422) + openapi + route tests + mutation-checked guards.
3. **Frontend typed client + hooks** — `api/acquisition.ts` + the read/mutation hooks + vitest.
4. **Frontend page** — `AcquisitionPage` (Followed/Wanted/Obligations/Watcher panels + CRUD forms +
   live WS invalidation), replace stub, vitest + a11y.
5. **Integration + ACC + docs** — e2e, executable ACC, `docs/reference/web-ui.md` §Acquisition, gate.

## 6. ACCEPTANCE (executable — in ACCEPTANCE.md)

- `GET /api/acquisition/followed` (authed) → 200 with the frozen item shape; unauth → 401; staging → 200.
- `POST /api/acquisition/followed {tvdb_id}` (prod, XRW) → 201; the same id again → 409; staging → 403.
- `DELETE /api/acquisition/followed/{id}` → 204; the row is `active=0` in acquire.db.
- `GET /api/acquisition/status` returns `last_successful_run_at` + `watcher_enabled`.
- Frontend `/acquisition` renders the followed table + a WS WantedEnqueued event refreshes the wanted
  panel without a reload (manual/browser check).
- `make check` green; frontend triple gate green; openapi + design-gaps + feature-map clean.
