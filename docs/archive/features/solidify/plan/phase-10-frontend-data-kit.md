# Phase 10 — Frontend data kit (T9a)

## Gate

```bash
make lint && make test && make check

# Frontend gates (CI parity — DESIGN §4)
cd frontend && npm run lint && npm run typecheck && npx vitest run && cd ..

# Type-extraction helpers defined ONCE (was 4 copies)
test "$(rg -c 'type SuccessBody' -g '*.ts' frontend/src/api/ -g '!*.test.ts' | wc -l)" = "1"

python -c "import personalscraper" && echo IMPORT-OK

# ACC hook (DESIGN §10 ACC-10 — no duplicated format helpers; one poll-202 hook)
test "$(rg -c 'function relativeTime|const relativeTime' -g '*.ts*' frontend/src/ | wc -l)" = "1" \
 && test "$(rg -l 'useRunToCompletion' -g '*.ts*' frontend/src/hooks/ | wc -l)" -ge 1 && echo ACC-10-OK
```

## Objective

Consolidate the frontend data layer (DESIGN §5 T9a; UI pixels unchanged — realign, never
raze): split the 968-line `api/client.ts` into per-domain modules
(pipeline/staging/acquisition/maintenance/decisions/config/registry) behind the generated
`schema.d.ts`, with ONE copy of the OpenAPI type-extraction helpers
(`SuccessBody`/`QueryParamsOf`/`RequestBodyOf`) and a `client.ts` shrunk to fetch-core +
auth + error normalization. Add the four shared machines to `hooks/`: `useRunToCompletion`
(launch-202 → poll → terminal outcome, replacing 4 divergent copies), query-key factories
per domain, ONE WS-event→invalidation map (the event-name enum imported from ONE module),
and shared decision mutations with one invalidation set. Collapse the scattered format
helpers into a single `lib/format.ts`.

## Findings addressed

FRONTEND-DATA-01..07 (client.ts god module; duplicated type-extraction helpers; 4 divergent
poll-202 flows; scattered query keys; duplicated WS-invalidation; duplicated formatters),
MECHANICAL-DUP-11.

## Code anchors (verified)

- `frontend/src/api/`: `client.ts` (968 lines — the god module to split), `acquisition.ts`, `decisions.ts`, `registry.ts`, `events.ts`, `schema.d.ts`. Domains still living inside `client.ts`: pipeline / staging / maintenance / config.
- Type-extraction helpers duplicated (verified in 4 files): `type SuccessBody<T>` / `type QueryParamsOf<Op>` in `frontend/src/api/acquisition.ts` (:23, :34), and copies in `client.ts`, `decisions.ts`, `registry.ts`. Target: ONE copy (e.g. `frontend/src/api/_schema-helpers.ts`).
- Scattered formatters (T9a / ACC-10): `formatDate` duplicated in `frontend/src/components/pipeline/RunDetail.tsx:80` AND `frontend/src/components/pipeline/RunHistoryTable.tsx:80`; `formatSize` in `frontend/src/components/staging/meta.ts:65`; `relativeTime` in `frontend/src/components/acquisition/meta.ts:310`; `formatDatetime` in `frontend/src/components/acquisition/meta.ts:323`. Canonical home: `frontend/src/lib/format.ts` (exists, has `format.test.ts`).
- `frontend/src/hooks/`: existing `useAcquisition.ts` (incl. `useTrackedAcquisitionRun` :190), `useConfig.ts`, `useConfigKeys.ts`, `useDecisions.ts`, `useAuth.ts`. `useRunToCompletion` is NEW (verified absent).
- WS event source of truth: `frontend/src/api/events.ts` — `EventMessage` :29 (`type` = emitting event class name, e.g. `"PipelineStepStarted"`), `HELLO_TYPE`/`PING_TYPE`, type guards `isEvent`/`isHello`/`isPing`. The 6-name event enum + invalidation map imports from here.
- French labels defined once (DESIGN §2): outcome-tone maps + `relativeTime`/`formatDate`/`formatSize` land in `lib/format.ts`.

## Tasks

1. **P10.1 — One schema-helper module.** Create `frontend/src/api/_schema-helpers.ts` exporting `SuccessBody`/`QueryParamsOf`/`RequestBodyOf`; import it in `acquisition.ts`/`decisions.ts`/`registry.ts` and the new domain modules; delete the 3 duplicate copies. Verify: `rg -c 'type SuccessBody' -g '*.ts' frontend/src/api/ -g '!*.test.ts'` == 1; `npm run typecheck` green.
2. **P10.2 — Split `client.ts` into per-domain modules.** Extract `api/pipeline.ts`, `api/staging.ts`, `api/maintenance.ts`, `api/config.ts` (acquisition/decisions/registry already exist); each behind `schema.d.ts`. Shrink `client.ts` to fetch-core + auth + error normalization (imported by every domain module). Keep every call's request/response shape identical. Verify: `npm run typecheck && npx vitest run`; `client.ts` LOC well under 968; each `pages/*` importing from the new domain module compiles.
3. **P10.3 — `lib/format.ts` single owner (ACC-10).** Move `formatDate`/`formatSize`/`relativeTime`/`formatDatetime` + outcome-tone maps into `lib/format.ts` (French labels once); replace the duplicates in `RunDetail.tsx`, `RunHistoryTable.tsx`, `staging/meta.ts`, `acquisition/meta.ts` with imports. Verify: `rg -c 'function relativeTime|const relativeTime' -g '*.ts*' frontend/src/` == 1; `npx vitest run frontend/src/lib/format.test.ts` green.
4. **P10.4 — `useRunToCompletion` hook.** Add `frontend/src/hooks/useRunToCompletion.ts` implementing launch-202 → poll → terminal-outcome once; migrate the 4 divergent copies (pipeline / maintenance / acquisition / decisions run flows, incl. `useTrackedAcquisitionRun`) onto it. Verify: `rg -l 'useRunToCompletion' -g '*.ts*' frontend/src/hooks/` ≥ 1; `npx vitest run` covers a 202→poll→done cycle; the four call-sites use the shared hook.
5. **P10.5 — Query-key factories per domain.** Add per-domain query-key factories (e.g. `api/<domain>.keys.ts` or in each domain module) so keys are defined once; migrate hooks off inline key arrays. Verify: `npm run typecheck`; invalidations target the factory keys (spot-check a mutation invalidates the right query).
6. **P10.6 — One WS-event→invalidation map.** Create ONE map (e.g. `hooks/useWsInvalidation.ts`) importing the 6-name event enum from `api/events.ts` and mapping each event → the query keys to invalidate; remove the scattered per-hook invalidation. Verify: `npx vitest run` covers a WS event triggering the mapped invalidation; the event-name enum is imported from `events.ts`, not re-declared.
7. **P10.7 — Shared decision mutations.** Consolidate resolve/dismiss/search-override mutations with one invalidation set. Verify: `npx vitest run frontend/src/hooks/useDecisions.test.tsx` green; the three mutations share the invalidation set.
8. **P10.8 — Green (frontend + backend).** Run `npm run lint && npm run typecheck && npx vitest run` and `make lint && make test && make check`. Verify: all green; no OpenAPI change (this phase is TS-only — `schema.d.ts` untouched).

## Non-goals

- Do not change any component's rendered output/layout (realign rule — pixels unchanged). Only
  the data layer moves; JSX stays.
- Do not decompose the god components (SchemaForm/Config/…) — that is P11.
- Do not regenerate `schema.d.ts` or change any backend route (no OpenAPI drift this phase).
- Do not add `lint:ds` violations; keep design-system lint clean (checked in P11's full mobile
  audit and CI).

## Commit

```
refactor(solidify): one OpenAPI type-helper module; split api/client.ts into per-domain modules
refactor(solidify): lib/format.ts single owner for relativeTime/formatDate/formatSize
feat(solidify): hooks/useRunToCompletion + query-key factories + one WS-invalidation map
```

Phase-gate commit:

```
chore(solidify): phase 10 gate — frontend data kit (api split, hooks, formatters)
```
