# Phase 5 — Frontend history: run-history table + detail

## Gate

Phase 4 must have produced:

- `Pipeline.tsx` page replacing the ComingSoon stub, rendering controls + stepper + log feed
- `PipelineControls` with all buttons working against the backend
- `usePipelineStatus` hook returning live state
- `npm run typecheck` 0, `npm run lint` 0, DS-adherence green

## Scope

Two components completing the `/pipeline` page:

- `RunHistoryTable` — sortable table of past runs via `/api/pipeline/history`
- `RunDetail` — per-run view with `PipelineStepper` (read-only mode) + error info

## Sub-phases

### 5.1 — RunHistoryTable + RunDetail

**Files:**

- Create: `frontend/src/components/pipeline/RunHistoryTable.tsx`
- Create: `frontend/src/components/pipeline/RunDetail.tsx`
- Modify: `frontend/src/pages/Pipeline.tsx` (add table + detail below controls)
- Modify: `frontend/src/api/client.ts` (add history API helpers)

**Commit:** `feat(pipe-control): add run-history table + detail view`

- Add typed API helpers to `client.ts`:
  - `getPipelineHistory(params: {limit?, offset?, sort?}): Promise<HistoryResponse>`
  - `getPipelineRunDetail(run_uid: string): Promise<RunDetail>`
- `RunHistoryTable.tsx`:
  - TanStack Table over `/api/pipeline/history`.
  - Columns: Date (`started_at`, formatted with `Intl.DateTimeFormat`), Déclencheur (`trigger` — `web|watch|cli|safety-net`), Issue (`outcome` — Badge tone mapped: success→green, error→red, killed→yellow, running→blue), Durée (`duration_s` formatted as `Xm Ys`).
  - Sortable by Date (default desc), Durée. Server-side sort via `sort` query param.
  - Pagination via `limit`/`offset` (prev/next or infinite scroll).
  - Row click → navigate to detail view (or expand inline). Use `useState` for selected run UID.
  - Empty state: "Aucune exécution enregistrée."
- `RunDetail.tsx`:
  - Receives `run_uid` prop, fetches via `useQuery({ queryKey: ["pipeline", "history", run_uid], queryFn: () => getPipelineRunDetail(run_uid) })`.
  - Renders: header with run_uid + trigger + outcome Badge + duration + dates.
  - PipelineStepper in read-only mode (`steps: StepTiming[]` prop from `RunDetail.steps`).
  - Error section: conditional, renders `error` in a `<Card>` with danger styling.
  - "Retour" button to close detail.
- Update `Pipeline.tsx`: add `RunHistoryTable` below the control bar + stepper + log feed section. Show `RunDetail` as a slide-over or card when a row is selected.
- `npm run typecheck` must pass (zero errors, zero `any`).

## Files touched this phase

| Operation | File                                                   |
| --------- | ------------------------------------------------------ |
| Modify    | `frontend/src/api/client.ts`                           |
| Create    | `frontend/src/components/pipeline/RunHistoryTable.tsx` |
| Create    | `frontend/src/components/pipeline/RunDetail.tsx`       |
| Modify    | `frontend/src/pages/Pipeline.tsx`                      |
