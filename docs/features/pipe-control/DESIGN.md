# DESIGN — S2 Pipeline control (`pipe-control`)

**Wave**: TorrentMate web UI **S2** · **Ticket**: #181 · **Bump**: 0.40.0 → **0.41.0** (minor, `feat`)
**Builds on**: S1 (`tm-shell`) — FastAPI `personalscraper/web/`, JWT-cookie auth,
Redis-Streams→WebSocket live event relay, the design-system-aligned React shell
(shadcn + TanStack + domain primitives), and the `/pipeline` route stub.

---

## 0. Cross-cutting rules (inherited from S1, non-negotiable)

- **Single trigger authority**: every write goes through the SAME `pipeline.lock`
  as the Watcher. No parallel writer. The EventBus stays **observe-only** — the web
  never mutates engine state except by the controls defined here.
- **Sync engine, async only at the WS relay** (S1 pattern). New routes are sync
  `def` handlers on the FastAPI threadpool.
- **Auth + CSRF**: all `/api/*` under `require_session`; every mutating POST carries
  the `X-Requested-With: TorrentMate` header guard (S1 §4.6 convention).
- **DS-strict frontend**: shadcn + TanStack + domain primitives only; zero raw
  hex/px (ESLint DS-adherence guard); FR-leading copy; machine tokens EN.
- **Pre-1.0**: no back-compat / migration-script burden — schema + config evolve in
  place on the single instance.

## 1. Overview & scope

The `/pipeline` screen becomes the operator's **control deck** for a pipeline run:

- **Start** a run (direct + confirm; optional `--dry-run` toggle).
- **Pause / Resume** the _running_ pipeline (cooperative, at step boundaries).
- **Kill** the running pipeline (SIGTERM the subprocess).
- **Pause / Resume the Watcher** (cut the daemon's auto-trigger — a distinct lever).
- **Live logs** for the active run (the S1 WS event feed, scoped to the run) + a
  `PipelineStepper` of the 9 steps.
- **Run history** — a durable, sortable table of past runs with per-step timings.

Two pause levers, deliberately distinct:

- **Pause pipeline** = freeze the _current_ run between steps (engine checkpoint).
- **Pause watcher** = stop the daemon from _auto-starting_ new runs (does not touch
  a run already in progress).

## 2. Architecture

```
                    ┌────────────────── /pipeline screen (React, DS) ───────────────────┐
                    │  Control bar   PipelineStepper   LogLine feed   Run-history table  │
                    └──────┬───────────────▲───────────────▲──────────────▲─────────────┘
          POST controls    │      WS (S1)  │ status/events  │              │ GET history
                    ┌──────▼───────────────┴────────────────┴──────────────┴─────────────┐
                    │  FastAPI  personalscraper/web/routes/pipeline.py  (sync, guarded)   │
                    │  run · pause · resume · kill · watcher · status · history · history/{id} │
                    └──┬────────────┬───────────────┬───────────────────┬────────────────┘
        spawn/SIGTERM  │   sentinels │ (pipeline.pause, watcher.paused)  │ SELECT
                    ┌──▼────────┐  ┌─▼───────────────────────────┐   ┌───▼──────────────┐
                    │ subprocess│  │ engine: pause checkpoint +  │   │ indexer DB        │
                    │ personal- │  │ run-history writer          │   │ pipeline_run tbl  │
                    │ scraper   │  │ (personalscraper/pipeline*) │   │                   │
                    │ run       │  └─────────────────────────────┘   └───────────────────┘
                    │ (lock,pid)│
                    └───────────┘
```

- The web **spawns** the run exactly as the watch loop does today (`personalscraper
run --no-console --trigger-reason web`), detached; the run claims `pipeline.lock`
  (pid-based). Kill = SIGTERM that pid. Pause = a sentinel the engine polls.
- The web **never runs the pipeline in-process** — it orchestrates the subprocess
  and reads state from the lock + sentinels + the WS feed + the history table.

## 3. Engine changes (`personalscraper/`, 2 cooperative additions)

### 3.1 Pause checkpoint (between-steps)

- A `PauseController` reads a **sentinel file** `pipeline.pause` (next to
  `pipeline.lock`, path from config/paths). **Before each of the 9 steps**, the run
  calls `checkpoint()`: if the sentinel exists → log `pipeline_paused`, emit a
  `PipelinePaused` event, then poll (e.g. 0.5s) until the sentinel clears
  (`resume` → `PipelineResumed`) OR SIGTERM arrives (graceful exit + lock release).
- Granularity is the **step boundary** (an in-flight step is never interrupted by
  pause — only Kill/SIGTERM stops mid-step). This is documented as the contract.
- No new dependency; pure file-sentinel + existing signal handling.

### 3.2 Run-history writer + `pipeline_run` table (indexer migration)

- New indexer migration adds table **`pipeline_run`**:
  `id INTEGER PK`, `run_uid TEXT UNIQUE`, `trigger TEXT` (web|watch|cli|safety-net),
  `dry_run INTEGER`, `started_at REAL`, `ended_at REAL NULL`,
  `outcome TEXT NULL` (success|error|killed|running|paused),
  `steps_json TEXT` (per-step `{name, started_at, ended_at, status}`),
  `error TEXT NULL`, `pid INTEGER NULL`.
- The run **writes its own record**: insert (running) at start, update step timings
  as it advances (reusing the existing step start/complete events), finalize outcome
  at end (incl. `killed` on SIGTERM, `error` on failure). Fail-soft — a history-write
  error never breaks the run.
- This makes history durable + queryable independent of the Redis stream window.

## 4. Backend — `personalscraper/web/routes/pipeline.py` (contracts)

All under `require_session`; mutating POSTs require `X-Requested-With: TorrentMate`.

| Method | Path                              | Body                 | Returns                                                       | Semantics                                                                                                                 |
| ------ | --------------------------------- | -------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| POST   | `/api/pipeline/run`               | `{dry_run?: bool}`   | `202 {run_uid}` / `409` if lock held                          | Spawn `personalscraper run --no-console --trigger-reason web [--dry-run]`; refuse if a run is already active (lock held). |
| POST   | `/api/pipeline/pause`             | —                    | `200 {state}`                                                 | Create the `pipeline.pause` sentinel. No-op if no active run.                                                             |
| POST   | `/api/pipeline/resume`            | —                    | `200 {state}`                                                 | Remove the sentinel.                                                                                                      |
| POST   | `/api/pipeline/kill`              | —                    | `200 {state}`                                                 | SIGTERM the run pid (from the lock); clear the pause sentinel; the run releases the lock + finalizes history as `killed`. |
| POST   | `/api/pipeline/watcher`           | `{enabled: bool}`    | `200 {watcher}`                                               | Set/clear the `watcher.paused` sentinel (the watch loop honours it in addition to `config.watch.enabled`).                |
| GET    | `/api/pipeline/status`            | —                    | `200 {state, run_uid?, step?, paused, watcher_enabled, pid?}` | Live status from lock + sentinels + latest `pipeline_run` row.                                                            |
| GET    | `/api/pipeline/history`           | `?limit&offset&sort` | `200 {runs: RunSummary[], total}`                             | Paginated, sortable list from `pipeline_run`.                                                                             |
| GET    | `/api/pipeline/history/{run_uid}` | —                    | `200 RunDetail` / `404`                                       | One run incl. `steps_json` timings.                                                                                       |

- `state` ∈ `idle | running | paused`. Pydantic response models (typed OpenAPI →
  `openapi-typescript` client, S1 convention).
- **Producer wiring**: the new engine events (`PipelinePaused/Resumed`, run
  lifecycle) flow through the existing EventBus → RedisEventPublisher → WS (S1), so
  the screen updates live with no polling.

## 5. Frontend — `/pipeline` (replaces the « À venir » stub)

Built strictly on the DS. New page `src/pages/Pipeline.tsx` + components under
`src/components/pipeline/`:

- **Control bar** (`PipelineControls`): **Démarrer** (Button `play`; opens a confirm
  with a `Switch` « dry-run »), **Pause/Reprendre** (Button `pause`/`play`, disabled
  when idle), **Kill** (Button `square`, danger, confirm dialog), and a **Watcher**
  toggle (`Switch` « Auto-trigger »). Actions call the typed client; each mutating
  call sends `X-Requested-With`. Optimistic disabled-states driven by `/status` + WS.
- **PipelineStepper** (DS domain primitive, re-implemented): the 9 steps
  (ingest→…→dispatch) with live status from the WS feed scoped to the active run.
- **Live logs** (`RunLogFeed`): the S1 `EventStream` LogLine feed **filtered to the
  active run** (auto-follow tail, reduced-motion aware).
- **Run history** (`RunHistoryTable`): TanStack Table over `/api/pipeline/history`
  — sortable columns Date · Trigger · Issue (`Badge` tone) · Durée; row → detail
  (`RunDetail` with the per-step timings via `PipelineStepper` in a read-only mode).
- Real-time: `useEventStreamContext` (S1) + a `usePipelineStatus` hook (TanStack
  Query on `/status`, invalidated by WS run events).

## 6. Testing

- **Engine**: unit tests for the pause checkpoint (sentinel present → polls, cleared
  → proceeds, SIGTERM → exits+releases), and the run-history writer (insert/update/
  finalize incl. killed/error). Migration test for `pipeline_run`.
- **Web**: route tests (run 202 / 409-lock-held, pause/resume/kill state, watcher
  toggle, status shape, history pagination+sort) with the lock + subprocess mocked;
  auth + X-Requested-With guard tests; a marked E2E smoke (spawn a `--dry-run` run
  via the API, observe the WS run events, read the history row).
- **Frontend**: control-bar states (disabled logic), confirm dialogs, dry-run
  toggle, history table sort, WS-driven status; DS-adherence + typecheck + zero-any.

## 7. Deploy / CI

- No new infra: rides the S1 prod/staging rails (deploy scripts, autodeploy, Caddy,
  PM2 `torrentmate-web`/`-staging`). The `pipeline_run` migration applies at DB open.
- CI unchanged (backend + frontend jobs). New commands/config documented in
  `docs/reference/commands.md` + `docs/reference/web-ui.md`.

## 8. Non-goals (deferred to later waves)

- Per-step manual re-run / step-level start (S2 controls the whole run only).
- Scheduling / cron editing from the UI (that's S4 config / not here).
- Multi-run concurrency (single trigger authority forbids it by design).
- Historical log replay beyond what the WS window + history table hold.

## 9. Phases (for the plan)

1. **Engine** — pause checkpoint (`PauseController` + `checkpoint()` between steps,
   events) + `pipeline_run` migration + run-history writer.
2. **Web controls** — `run/pause/resume/kill/watcher/status` routes (lock, subprocess,
   sentinels), auth + X-Requested-With guards, Pydantic models, producer wiring.
3. **Web history** — `history` + `history/{run_uid}` routes + models.
4. **Frontend control screen** — Pipeline page: control bar + PipelineStepper + live
   log feed + status hook.
5. **Frontend history** — run-history table + detail.
6. **Deploy rails + docs + ACCEPTANCE** — web-ui.md/commands.md updates, ACCEPTANCE
   (executable ACC-NN), staging validation.

## 10. ACCEPTANCE (sketch — executable ACC-NN, finalized in phase 6)

- `curl -X POST …/api/pipeline/run -H 'X-Requested-With: TorrentMate' -d '{"dry_run":true}'` → `202` + a `run_uid`; a second immediate call → `409` (lock held).
- `…/api/pipeline/pause` then `…/status` → `state:"paused"`; `…/resume` → `running`.
- `…/api/pipeline/kill` → the run pid gone, lock released, history row `outcome:"killed"`.
- `…/api/pipeline/watcher {"enabled":false}` → `watcher.paused` sentinel present; watch loop no-ops.
- `…/api/pipeline/history` → the run appears with per-step timings.
- Frontend: `npm run typecheck` 0, `npm run lint` 0 (zero no-explicit-any), DS-adherence green.
