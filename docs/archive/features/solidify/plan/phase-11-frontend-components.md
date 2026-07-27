# Phase 11 — Frontend component decomposition (T9b)

## Gate

```bash
make lint && make test && make check

# Frontend gates incl. design-system lint (CI parity)
cd frontend && npm run lint && npm run lint:ds && npm run typecheck && npx vitest run && npm run build && cd ..

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-11 — frontend gates green)
cd frontend && npm run lint && npm run typecheck && npx vitest run --reporter=dot && cd .. && echo ACC-11-OK
```

Plus the 390px mobile iframe audit (memory rule) is re-run once after this phase: for each
route, inject a same-origin 390px iframe and assert `scrollWidth - innerWidth == 0` and any
sheet renders full-screen (no visual change expected — realign rule).

## Objective

Decompose the god components without touching layout (DESIGN §5 T9b; realign, never raze):
`SchemaForm.tsx` (1,611 non-blank LOC) → schema engine + field kit + recursive renderer
modules; `Config.tsx` (718 non-blank, hotspot #1) → page shell + `useConfigEditor` hook +
panels; and the four remaining 569–639-line components split into
data-machine/presentation. Each split consumes the P10 hooks/formatters. UI pixels and
snapshots stay unchanged.

## Findings addressed

FRONTEND-COMPONENTS-01 (SchemaForm god component), FRONTEND-COMPONENTS-02 (Config hotspot),
FRONTEND-COMPONENTS-05/06 (the 4 large components mix data-machine + presentation), plus the
data-layer coupling those components had to the pre-P10 duplicated helpers.

## Code anchors (verified)

- `frontend/src/components/config/SchemaForm.tsx` — 1,722 raw lines (~1,611 non-blank); has `SchemaForm.test.tsx` (1,175 lines). Split into: a schema engine (validation/defaults), a field kit (per-primitive field components), and a recursive renderer.
- `frontend/src/pages/Config.tsx` — 765 raw lines (~718 non-blank); has `Config.test.tsx` (866 lines). Split into: page shell + `useConfigEditor` hook + panels.
- The four remaining large components (verified via `wc -l`): `frontend/src/components/decisions/DecisionDetail.tsx` (639), `frontend/src/components/maintenance/ActionForm.tsx` (612), `frontend/src/components/decisions/ResolutionDeck.tsx` (596), `frontend/src/components/acquisition/FollowedPanel.tsx` (569). Each splits into a data-machine (hook) + presentation.
- Consumes P10 seams: `hooks/useRunToCompletion`, per-domain query-key factories, `lib/format.ts`, the WS-invalidation map.
- Existing test coverage to keep green: `SchemaForm.test.tsx`, `Config.test.tsx`, `DecisionDetail.test.tsx`, `pages/AcquisitionPage.test.tsx`, `pages/Decisions.test.tsx`.

## Tasks

1. **P11.1 — SchemaForm decomposition.** Split `SchemaForm.tsx` into `components/config/schema/engine.ts` (validation + defaults), `components/config/schema/fields/*` (field kit per primitive), and `components/config/schema/Renderer.tsx` (recursive renderer). `SchemaForm.tsx` becomes a thin composition. Keep the rendered form identical. Verify: `npx vitest run frontend/src/components/config/SchemaForm.test.tsx` green (unchanged assertions); each new module ≤ ~400 LOC.
2. **P11.2 — Config page shell + `useConfigEditor`.** Extract `hooks/useConfigEditor.ts` (load/dirty/save/validate machine) and split the panels out of `Config.tsx` into `components/config/panels/*`; `Config.tsx` becomes the page shell. Verify: `npx vitest run frontend/src/pages/Config.test.tsx` green; `Config.tsx` well under 700 LOC.
3. **P11.3 — DecisionDetail split.** Extract the data-machine (a hook using P10 decision mutations + query keys) from `DecisionDetail.tsx`; keep presentation in the component. Verify: `npx vitest run frontend/src/components/decisions/DecisionDetail.test.tsx` green.
4. **P11.4 — ActionForm split.** Extract the run-launch machine from `maintenance/ActionForm.tsx` onto `useRunToCompletion`; presentation stays. Verify: `npx vitest run` covers ActionForm; a maintenance action still launches via the shared hook.
5. **P11.5 — ResolutionDeck split.** Split `decisions/ResolutionDeck.tsx` into deck-state hook + presentation. Verify: `npx vitest run frontend/src/pages/Decisions.test.tsx` green.
6. **P11.6 — FollowedPanel split.** Split `acquisition/FollowedPanel.tsx` into a data hook (query keys + `useTrackedAcquisitionRun` via P10) + presentation. Verify: `npx vitest run frontend/src/pages/AcquisitionPage.test.tsx` green.
7. **P11.7 — 390px mobile audit + full frontend gate.** Re-run the 390px iframe audit per route (memory rule): pin the Chrome-MCP viewport, inject a same-origin 390px iframe, assert `scrollWidth - innerWidth == 0` and full-screen sheets on every route. Run `npm run lint && npm run lint:ds && npm run typecheck && npx vitest run && npm run build`. Verify: zero horizontal overflow on every route (no visual change vs pre-phase); all frontend gates green.

## Non-goals

- Do not change any layout, spacing, colors, copy, or component visual output (realign rule —
  the 390px audit must show zero change).
- Do not touch the backend or `schema.d.ts` (no OpenAPI change this phase).
- Do not re-introduce local format helpers or inline query keys (must consume the P10 seams).
- Do not add new screens, routes, or features.

## Commit

```
refactor(solidify): SchemaForm -> schema engine + field kit + recursive renderer
refactor(solidify): Config -> page shell + useConfigEditor + panels
refactor(solidify): DecisionDetail/ActionForm/ResolutionDeck/FollowedPanel split data-machine/presentation
```

Phase-gate commit:

```
chore(solidify): phase 11 gate — frontend god-component decomposition + 390px audit
```
