# Phase 5 — Frontend: Maintenance Page

## Gate

**Prerequisite — Phase 1–4 delivered**:

- All 6+ backend routes operational (`/api/maintenance/disks`, `/locks`, `/index-health`, `/actions`, `/actions/{id}/run`, `/api/pipeline/history?kind=`).
- `RunSummary`/`RunDetail` carry `kind` and `command` fields.
- `openapi.json` regenned from the routes → `schema.d.ts` includes all new types.
- `make test` passes on backend (all S2 tests intact after model extension).

**Produces for Phase 6**: fully functional `/maintenance` page replacing the S1 `ComingSoon` stub.

**Reusable S2 components**: `RunHistoryTable` (already renders `RunSummary[]` in `Pipeline.tsx`), `RunLogFeed` (already subscribes WS by `run_uid`), `StatPanel` + `StatusDot` from the DS kit.

## Sub-phases

### 5.1 — Maintenance page shell + 4 monitoring panels (`feat(maint-dash): add Maintenance page with disks, locks, index-health panels`)

**Files:**

- Create: `frontend/src/pages/Maintenance.tsx`
- Create: `frontend/src/components/maintenance/DisksPanel.tsx`
- Create: `frontend/src/components/maintenance/LocksPanel.tsx`
- Create: `frontend/src/components/maintenance/IndexHealthPanel.tsx`
- Modify: `frontend/src/router.tsx:48-50` (replace `ComingSoon` with `Maintenance` lazy import)

**`Maintenance.tsx`**: responsive grid (1 col mobile, 2 col tablet, 4 col desktop). Renders the 4 panel components + a placeholder `ActionCatalog` (empty div until 5.2). Each panel is a `<Card>` with the DS card component.

**`DisksPanel`**: TanStack `useQuery` on `GET /api/maintenance/disks` (refetchInterval: 60s). Renders one row per disk: `StatPanel` with `label`, `free_gb`/`total_gb` as value, capacity bar (`used_pct`), `StatusDot` green (mounted + >10% free), yellow (<10%), red (unmounted).

**`LocksPanel`**: `useQuery` on `GET /api/maintenance/locks` (refetchInterval: 10s). Renders: lock state with `StatusDot` (green=not held, yellow=held+PID alive, red=stale), pause/watcher sentinel presence + age in human-readable format, tmp-orphan count with expandable list (capped at 100 items per backend).

**`IndexHealthPanel`**: `useQuery` on `GET /api/maintenance/index-health` (refetchInterval: 60s). Renders headline counts (items/movies/shows/files) in a horizontal stat row using `StatPanel`. Sub-checks: NFO coverage ratio with `StatusDot` (green >90%, yellow >70%, red <70%), repair queue pending count + oldest age, outbox pending, last scan status (green=success, yellow=stuck, red=failed), soft-deleted count, canonical NULL count. Deep-links each sub-check to the relevant action (e.g. "Réparer les NFO" → opens `ActionForm` for `library-fix-nfo`).

### 5.2 — ActionCatalog + ActionForm (`feat(maint-dash): add action catalog with generated forms and dry-run-first UX`)

**Files:**

- Create: `frontend/src/components/maintenance/ActionCatalog.tsx`
- Create: `frontend/src/components/maintenance/ActionForm.tsx`
- Create: `frontend/src/components/ui/select.tsx` (shadcn wrapper) + add scoped `@radix-ui/react-select` dep
- Modify: `frontend/src/api/client.ts` (add `getActions` + parameterized `runMaintenanceAction` helpers + type aliases)
- Modify: `frontend/src/hooks/useMaintenanceKeys.ts` (add `actions` query key)
- Modify: `frontend/src/pages/Maintenance.tsx` (replace the placeholder with `<ActionCatalog />`)

**`ActionCatalog`**: `useQuery` on `GET /api/maintenance/actions` (refetchInterval: 0 — static). Groups actions by `category` with collapsible sections. Each action card shows: `title` (FR), `description` (FR), badges for `risk` (`ro`=grey, `write`=yellow, `destructive`=red) and `long_running` (clock icon). Click opens `ActionForm` in a `<Dialog>` (shadcn).

**`ActionForm`**: receives `MaintenanceAction` entry. Generates form fields from `options[]`:

- `str` → `<Input>` (shadcn)
- `int` → `<Input type="number">`
- `bool` → `<Switch>` (existing DS component)
- `enum` → `<Select>` with `enum_values` as options
  Each field shows `label` (FR) + `help` rendered **inline** under the control
  (no tooltip primitive is added — see the S3 dependency policy).

**Dry-run UX** (for `dry_run='supported'` actions):

- **Risk `ro`**: hides dry-run checkbox, single "Exécuter" button (always `dry_run: false`).
- **Risk `write`**: shows dry-run checkbox (default checked), "Exécuter (dry-run)" button.
- **Risk `destructive`**: "Dry-run" primary button always visible. "Apply" button **disabled** with tooltip "Lancer un dry-run d'abord". After a successful dry-run (poll or TanStack mutation success), "Apply" becomes enabled. On 428 response from backend, "Apply" re-locks with backend-provided detail message.

Form state includes `dryRun: boolean` defaulting to `true` for supported actions. On submit, POST to `/api/maintenance/actions/{action.id}/run` with `{options, dry_run}`.

### 5.3 — RunOutput live feed (`feat(maint-dash): add live output feed for spawned maintenance runs`)

**Files:**

- Modify: `frontend/src/components/maintenance/ActionForm.tsx` (add post-submit output panel)
- Modify: `frontend/src/components/pipeline/RunLogFeed.tsx` (verify reuse; minimal
  backward-compatible addition — surface a human-readable `data.line` for
  `maintenance.run_log` envelopes instead of the raw JSON dump. The "kind-aware
  title" idea was dropped: the title is already run-scoped and changing it would
  break the existing `/Journal d.exécution/` assertion for no user benefit.)

**`RunOutput` panel** (rendered inside `ActionForm` dialog after a successful `POST .../run`):

1. Shows `run_uid` and status badge.
2. Reuses S2 `RunLogFeed` component which already subscribes to the Redis→WS relay filtered by `run_uid`. The relay already tags events with `run_uid` (S2 envelope); the maintenance runner (Phase 3.3) publishes to the same stream with the same envelope, so no WS-side changes needed.
3. Fallback after run completion: `useQuery` on `GET /api/pipeline/history/{run_uid}` → displays `output_tail` field in a `<LogLine>` list (existing DS component).
4. Close button dismisses the output panel (stays in history).

### 5.4 — OpenAPI regen + type commit (`chore(maint-dash): regenerate openapi.json and schema.d.ts for maintenance routes`)

**Files:**

- Modified by `make openapi`: `frontend/openapi.json`, `frontend/src/api/schema.d.ts`

**Steps**:

1. Run `make openapi` (generates OpenAPI spec from FastAPI routes including all new maintenance models/routes).
2. Verify `git diff --exit-code frontend/openapi.json frontend/src/api/schema.d.ts` (CI guard — will fail if drift).
3. Frontend type-check: `cd frontend && npx tsc --noEmit` — must pass against the regenerated `schema.d.ts`.
4. Commit both generated files with the implementation commit.

**Note**: the actual `make openapi` regen and commit happens once per phase that touches models/routes (Phase 2, 3, 4), but the final frontend commit in Phase 5 ensures the types are consistent with the full endpoint surface. The DESIGN §7 mandates committing these together.
