# Phase 02 — History repatriation + legend popover

**Goal**: Pipeline run history (`RunHistoryTable kind="pipeline"` + `?run=` RunDetail drawer)
moves from Maintenance to the Pipeline page. The trigger legend becomes a tap-accessible popover.

**Constitution served**: §1/§2, DOIT-3, DOIT-9, DOIT-10, NE-DOIT-PAS-4.

## Surface

| File                                                        | Action                                                           |
| ----------------------------------------------------------- | ---------------------------------------------------------------- |
| `frontend/src/pages/Pipeline.tsx`                           | Add `RunHistoryTable kind="pipeline"` + `?run=` RunDetail drawer |
| `frontend/src/pages/Maintenance.tsx`                        | Remove `RunHistoryTable kind="pipeline"` + `TriggerLegend`       |
| `frontend/src/components/pipeline/RunDetail.tsx`            | Add cross-link for maintenance uids                              |
| `frontend/src/components/pipeline/TriggerLegend.tsx`        | Convert chip-paragraph to popover                                |
| `frontend/src/pages/Pipeline.test.tsx`                      | Migrate: assert history table + `?run=` drawer                   |
| `frontend/src/pages/Maintenance.test.tsx`                   | Migrate: assert pipeline table gone                              |
| `frontend/src/components/pipeline/RunHistoryTable.test.tsx` | Verify no regressions                                            |
| `frontend/src/components/pipeline/RunDetail.test.tsx`       | Add cross-link assertion                                         |

## Sub-phases

### 2.1 — Add history table + RunDetail drawer to Pipeline page

**Commit**: `feat(pipeline-panel): repatriate pipeline run history to /pipeline`

In `Pipeline.tsx`:

- Import `RunHistoryTable`, `RunDetail` + components already present
- Add `useSearchParams` to manage `?run=` query param (same pattern as `?stage=` in FlowBoard)
- Place `RunHistoryTable kind="pipeline" onSelect={openRun}` BELOW the collapsed
  `RunLogFeed` accordion (after it, before the page end). Wrap in its own `<section>`.
- Below the history table, render `{selectedRun !== null && <RunDetail runUid={selectedRun} onClose={closeRun} />}`
  — same inline-drawer pattern as Maintenance.tsx:102-104.
- The `?run=` and `?stage=` search params are independent (one key each); no conflict.

The existing `TriggerLegend` import is REMOVED from Pipeline.tsx (it moves to popover form
in sub-phase 2.3, rendered BY RunHistoryTable's header section).

### 2.2 — Remove pipeline runs from Maintenance, add cross-link

**Commit**: `feat(pipeline-panel): remove pipeline-run table from Maintenance, add cross-link`

In `Maintenance.tsx`:

- Delete the `RunHistoryTable kind="pipeline"` JSX line (line 92).
- Delete the `TriggerLegend` JSX line (line 99) — it now lives inside the history section
  on Pipeline.
- The `RunHistoryTable kind="maintenance"` stays UNTOUCHED.

In `RunDetail.tsx`:

- When `data.kind === "maintenance"` and rendered on the Pipeline page (detect via a new
  optional prop `showMaintenanceLink?: boolean`), add a cross-link below the metadata row:
  `→ Voir les exécutions de maintenance` linking to `/maintenance`.
- The prop defaults to `false` so Maintenance.tsx renders it without the cross-link
  (no circular noise).

### 2.3 — Convert TriggerLegend to tap-accessible popover

**Commit**: `feat(pipeline-panel): trigger legend popover on history header`

In `TriggerLegend.tsx`:

- Replace the inline chip-paragraph with a `Popover` (use shadcn `@/components/ui/popover`).
- Trigger: a `?` icon button placed in the history table header (accept `className` or
  render as a standalone element with a ref anchor).
- Content: one chip per trigger (Badge + meaning), same data from `TRIGGER_INFO`.
- Close on click outside / tap — the `Popover` component handles this natively.

In `RunHistoryTable.tsx`:

- Add an optional `legend` slot prop (or accept `ReactNode` children) so the Pipeline
  page renders the popover next to "Historique des exécutions" heading.
- Maintenance passes nothing — the popover only lives on Pipeline now.

### 2.4 — Test migration + gate

**Commit**: `test(pipeline-panel): migrate history + legend tests`

- `Pipeline.test.tsx`: assert `RunHistoryTable` renders on `/pipeline`; assert `?run=` opens
  RunDetail; assert `?run=` absent shows no drawer.
- `Maintenance.test.tsx`: assert pipeline-run table is ABSENT; assert maintenance-run table
  still renders.
- `RunDetail.test.tsx`: add assertion that maintenance-kind detail shows cross-link when
  `showMaintenanceLink=true`.
- Update any mock handlers that the history API needs (GET `/api/pipeline/history` with
  `?kind=pipeline`).

## Gate

- [ ] All 4 commits follow Conventional Commits with `(pipeline-panel)` scope
- [ ] `cd frontend && npm run lint && npm run lint:ds && npm run typecheck` → 0 errors
- [ ] `npx vitest run` → all 1556+ tests passing (existing suites migrate in-step)
- [ ] `make lint && make test` (backend — zero regressions, no OpenAPI drift)
- [ ] Visual: `/pipeline` shows history table + `?run=<uid>` opens RunDetail
- [ ] Visual: `/maintenance` shows ONLY the maintenance-run history table
- [ ] Visual: RunDetail on a maintenance uid (on `/pipeline`) shows cross-link
- [ ] Visual: legend popover opens on tap/click on `/pipeline`
