# Phase 4 — Frontend control screen

## Gate

Phase 2 must have produced:

- All 6 pipeline control routes operational and returning correct Pydantic shapes
- `GET /api/pipeline/status` returning `{state, run_uid?, step?, paused, watcher_enabled, pid?}`
- OpenAPI schema regenerated (`make openapi`) so the frontend types (`schema.d.ts`) include the new endpoints
- `make test` passes backend, `npm run typecheck` passes frontend

## Scope

Replace the `/pipeline` `ComingSoon` stub with the operational control screen:

- `PipelineControls` bar (Démarrer/Pause/Reprendre/Kill + Watcher toggle)
- `PipelineStepper` (9-step progress visualization)
- `RunLogFeed` (scoped live log from WS)
- `usePipelineStatus` hook (TanStack Query on `/status` + WS invalidation)
- New typed API client helpers for the pipeline endpoints

## Sub-phases

### 4.1 — Pipeline page + control bar + typed API helpers

**Files:**

- Modify: `frontend/src/api/client.ts` (add pipeline API helpers)
- Create: `frontend/src/components/pipeline/PipelineControls.tsx`
- Modify: `frontend/src/pages/Pipeline.tsx` (new page, replace ComingSoon stub)
- Modify: `frontend/src/router.tsx` (replace ComingSoon with Pipeline page)

**Commit:** `feat(pipe-control): add Pipeline page with control bar`

- Add typed API helpers to `client.ts` following existing pattern:
  - `runPipeline(body: RunRequest): Promise<RunResponse>` — POST `/api/pipeline/run`
  - `pausePipeline(): Promise<StatusResponse>` — POST `/api/pipeline/pause`
  - `resumePipeline(): Promise<StatusResponse>` — POST `/api/pipeline/resume`
  - `killPipeline(): Promise<StatusResponse>` — POST `/api/pipeline/kill`
  - `setWatcher(body: WatcherRequest): Promise<WatcherResponse>` — POST `/api/pipeline/watcher`
  - `getPipelineStatus(): Promise<StatusResponse>` — GET `/api/pipeline/status`
  - Each mutating helper sets `X-Requested-With: TorrentMate` header (extend `apiFetch` with optional `headers` param).
- `PipelineControls.tsx`:
  - **Démarrer**: `<Button>` with `play` icon; opens a `<Dialog>` with `dry-run` `<Switch>` and "Démarrer" / "Annuler" buttons.
  - **Pause**: `<Button>` with `pause` icon; disabled when `state !== "running"`.
  - **Reprendre**: `<Button>` with `play` icon; disabled when `state !== "paused"`.
  - **Kill**: `<Button variant="destructive">` with `square` icon; opens `<Dialog>` confirm "Arrêter le pipeline ?" with danger styling.
  - **Watcher**: `<Switch>` "Auto-trigger" with label; calls `setWatcher({enabled})`.
  - Optimistic: disabled-states driven by `state` from the status hook.
  - Uses `useMutation` from TanStack Query; invalidates `["pipeline", "status"]` on success.
- `Pipeline.tsx` page: imports `PipelineControls`, `PipelineStepper`, `RunLogFeed`. Lays out mobile-first with Tailwind.
- Update `router.tsx`: replace `<ComingSoon title="Pipeline" wave="S2" />` with `<Pipeline />` (lazy import with `React.lazy`).

### 4.2 — PipelineStepper + RunLogFeed

**Files:**

- Create: `frontend/src/components/pipeline/PipelineStepper.tsx`
- Create: `frontend/src/components/pipeline/RunLogFeed.tsx`

**Commit:** `feat(pipe-control): add PipelineStepper + RunLogFeed components`

- `PipelineStepper`:
  - Static list of 9 step names (ingest → sort → clean → scrape → cleanup → enforce → verify → trailers → dispatch).
  - Each step rendered as a row: icon (pending/running/done/error) + label + optional elapsed time.
  - Current step highlighted via `step` field from `StatusResponse` / WS events.
  - Read-only mode (for history detail, used in Phase 5) — pass `steps: StepTiming[]` prop.
  - Uses `StatusDot` DS component for the step icons.
  - Tailwind: compact horizontal or vertical layout, responsive.
- `RunLogFeed`:
  - Reads `events` from `useEventStreamContext()`, filtered to the active run's `run_uid`.
  - Renders `LogLine` DS component for each matching event.
  - Auto-scroll to bottom (with "scroll to bottom" button when user scrolls up).
  - `prefers-reduced-motion` respected for scroll behavior.
  - Empty state: "Aucun log pour cette exécution." when no matching events.

### 4.3 — usePipelineStatus hook + WS integration

**Files:**

- Create: `frontend/src/hooks/usePipelineStatus.ts`
- Create: `frontend/src/hooks/usePipelineStatus.test.tsx`

**Commit:** `feat(pipe-control): add usePipelineStatus hook with WS-driven invalidation`

- `usePipelineStatus`:
  - `useQuery({ queryKey: ["pipeline", "status"], queryFn: getPipelineStatus, refetchInterval: 5000 })`
  - Also subscribes to WS events: on `PipelineStarted`, `PipelineEnded`, `PipelinePaused`, `PipelineResumed`, `StepStarted` → `queryClient.invalidateQueries({ queryKey: ["pipeline", "status"] })`.
  - Returns `{ state, run_uid, step, paused, watcher_enabled, pid, isLoading }`.
- Exported query keys: `pipelineKeys.status = ["pipeline", "status"] as const`
- Test: mock `getPipelineStatus` and WS events, verify invalidation triggers refetch.

## Files touched this phase

| Operation | File                                                    |
| --------- | ------------------------------------------------------- |
| Modify    | `frontend/src/api/client.ts`                            |
| Create    | `frontend/src/components/pipeline/PipelineControls.tsx` |
| Create    | `frontend/src/pages/Pipeline.tsx`                       |
| Modify    | `frontend/src/router.tsx`                               |
| Create    | `frontend/src/components/pipeline/PipelineStepper.tsx`  |
| Create    | `frontend/src/components/pipeline/RunLogFeed.tsx`       |
| Create    | `frontend/src/hooks/usePipelineStatus.ts`               |
| Create    | `frontend/src/hooks/usePipelineStatus.test.tsx`         |
