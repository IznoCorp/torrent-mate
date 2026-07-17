# Phase 01 — Stepper compression + always-visible anomaly

**Goal**: The FlowBoard stations compress so the red anomaly signal is ALWAYS visible
without horizontal scroll at any width (DOIT-2, §8). Mobile gets a compact vertical list.

**Constitution served**: §1, §2, §8, DOIT-2, DOIT-9.

## Surface

| File                                                  | Action                                                    |
| ----------------------------------------------------- | --------------------------------------------------------- |
| `frontend/src/components/ds/StageStation.tsx`         | Add `compact` variant (no label/count when quiet)         |
| `frontend/src/components/pipeline/FlowBoard.tsx`      | Anomalous=expanded+red, quiet=icon+count, mobile vertical |
| `frontend/src/components/pipeline/FlowBoard.test.tsx` | Migrate tests to new variant behaviour                    |

## Sub-phases

### 1.1 — Add `compact` prop to StageStation

**Commit**: `feat(pipeline-panel): add compact variant to StageStation`

When `compact=true`, quiet states (`idle`, `ok`) render only: icon (14px) + count (mono, `--text-base`).
Anomalous states (`attention`, `blocked`) ALWAYS render expanded regardless of `compact`:
label + count + blocked chip + state dot. The `attention`/`blocked` red lavis + ring classes
already exist in `STATE_CONTAINER` — only the render selection changes.

Also add a `size` prop: `"sm"` (mobile, ~40px row) vs default (existing). `size="sm"` trims
padding to `py-2`, shrinks the count to `text-lg`, and optionally hides `split` sub-counts.

### 1.2 — Rewire FlowBoard to use compact stations

**Commit**: `feat(pipeline-panel): compress FlowBoard stations, red anomaly always visible`

In `FlowBoard.tsx`:

- Desktop (sm+): pass `compact=true` to all StageStations. The active step and any step with
  `blocked>0` or `state==="attention"` — already rendered expanded per 1.1 — get the red ring.
- The horizontal row keeps `flex-wrap` so stations wrap rather than overflow (no scrollbar).
- Mobile (<md): pass `size="sm"` → stations stack vertically ~40px/row (replacing the current
  full-height cards). Keep the `?stage=` click handler — the drawer opens the same way.
- The `?stage=` Sheet drawer is UNTOUCHED — it already works.
- Remove `PipelineStepper` import if still referenced (the FlowBoard IS the stepper now).

### 1.3 — Test migration + gate

**Commit**: `test(pipeline-panel): migrate FlowBoard tests to compact variant`

- Update `FlowBoard.test.tsx`: assert compact rendering (no label visible for `ok` steps),
  blocked step renders expanded + red ring, mobile stack assertion.
- Run full gate: `cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run`

## Gate

- [ ] All 3 commits have Conventional Commits format with `(pipeline-panel)` scope
- [ ] `cd frontend && npm run lint` → 0 errors
- [ ] `cd frontend && npm run lint:ds` → 0 errors
- [ ] `cd frontend && npm run typecheck` → 0 errors
- [ ] `npx vitest run` → all passing
- [ ] `make lint && make test` (backend — assert zero regressions)
- [ ] Visual check: at 1440px, a FlowBoard with `blocked>0` shows the red step without horizontal scroll overlay
- [ ] Visual check: at 390px (mobile iframe), the vertical list renders all 8 steps, overflow-x = 0
