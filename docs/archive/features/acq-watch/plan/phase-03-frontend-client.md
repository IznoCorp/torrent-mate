# Phase 3 — Frontend Typed Client + Hooks

## Gate

- [ ] `cd frontend && npm run lint` — zero errors
- [ ] `cd frontend && npm run typecheck` — zero errors
- [ ] `cd frontend && npx vitest run` — all tests pass
- [ ] Commit with `chore(acq-watch): phase 3 gate — frontend typed client + hooks`

## Prerequisites

- Phase 1 SHIPPED — `make openapi` regenerated `frontend/src/api/schema.d.ts`
  with the 4 acquisition GET endpoints (followed, wanted, obligations, status)
  and Phase 2 regen added the POST/PATCH/DELETE request/response shapes.
- The `schema.d.ts` now contains typed `paths["/api/acquisition/followed"]["get"]`
  etc. — this phase binds to those types.

## Objectives

1. Create `frontend/src/api/acquisition.ts` — typed `apiFetch` wrappers for all
   7 acquisition endpoints (4 reads + 3 writes).

2. Create `frontend/src/hooks/useAcquisition.ts` — TanStack Query hooks:
   `useFollowed`, `useWanted`, `useObligations`, `useAcquisitionStatus`, and
   mutations `useFollow`, `useUpdateFollow`, `useUnfollow`.

3. Vitest: client functions (typed params, URL building) + hooks (renderHook
   with QueryClientProvider, mock apiFetch).

## DESIGN gotchas

- **No new watcher route on the frontend** — the toggle calls the existing
  `setWatcher` from `api/client.ts` (`POST /api/pipeline/watcher`). The
  acquisition client does NOT wrap this; the page imports `setWatcher` directly.
- **queryKeys convention** — follow the existing pattern (`["acquisition",
"followed", {active}]` etc.) matching `useMaintenanceKeys.ts` / `useConfigKeys.ts`.
- **R13 new-events-only ref pattern** — the hooks themselves do NOT filter
  events. They expose `queryKey` factories so Phase 4's `AcquisitionPage` can
  call `queryClient.invalidateQueries({queryKey: ...})` when the
  `useEventStreamContext` ring contains relevant events.
- **XRW header on all mutations** — reuse `XRW_HEADERS` from `api/client.ts`.
- **No `any` types** — follow the existing strict TypeScript pattern with
  `apiFetch` generic binding to `paths`.

## Files to create

| File                                         | Purpose                                  |
| -------------------------------------------- | ---------------------------------------- |
| `frontend/src/api/acquisition.ts`            | Typed apiFetch wrappers + response types |
| `frontend/src/api/acquisition.test.ts`       | Vitest for client functions              |
| `frontend/src/hooks/useAcquisition.ts`       | TanStack Query hooks (reads + mutations) |
| `frontend/src/hooks/useAcquisition.test.tsx` | Vitest for hooks                         |

## api/acquisition.ts — typed client

```typescript
/**
 * Typed fetch wrappers for the acquisition API (acq-watch feature).
 *
 * Every function binds through {@link apiFetch} so path, method, request body,
 * path params, and query params are all checked against the OpenAPI-generated
 * ``schema.d.ts`` — no ``any`` at any call site.
 *
 * Mutating endpoints carry the ``X-Requested-With`` header (reusing
 * ``XRW_HEADERS`` from client.ts).  Reads are header-free.
 */

import { apiFetch, XRW_HEADERS } from "./client";
import type { paths } from "./schema";
import type { SuccessBody, QueryParamsOf, ResponseBodyOf } from "./client"; // if exported; else redefine inline

// Reuse the type helpers from client.ts — if not already exported, add them.
// For this plan, assume they're importable.

/** Response type for GET /api/acquisition/followed */
export type FollowedResponse = SuccessBody<
  paths["/api/acquisition/followed"]["get"]["responses"]
>;

/** A single FollowedSeriesItem from the array */
export type FollowedSeriesItem = FollowedResponse["items"][number];

/** Query params for GET /api/acquisition/followed */
export type FollowedParams = QueryParamsOf<
  paths["/api/acquisition/followed"]["get"]
>;

/** Response type for GET /api/acquisition/wanted */
export type WantedResponse = SuccessBody<
  paths["/api/acquisition/wanted"]["get"]["responses"]
>;

/** A single WantedItemResponse from the array */
export type WantedItem = WantedResponse["items"][number];

/** Query params for GET /api/acquisition/wanted */
export type WantedParams = QueryParamsOf<
  paths["/api/acquisition/wanted"]["get"]
>;

/** Response type for GET /api/acquisition/obligations */
export type ObligationsResponse = SuccessBody<
  paths["/api/acquisition/obligations"]["get"]["responses"]
>;

/** A single ObligationItem from the array */
export type ObligationItem = ObligationsResponse["items"][number];

/** Query params for GET /api/acquisition/obligations */
export type ObligationsParams = QueryParamsOf<
  paths["/api/acquisition/obligations"]["get"]
>;

/** Response type for GET /api/acquisition/status */
export type AcquisitionStatusResponse = SuccessBody<
  paths["/api/acquisition/status"]["get"]["responses"]
>;

/** Request body for POST /api/acquisition/followed */
export type CreateFollowRequest =
  paths["/api/acquisition/followed"]["post"]["requestBody"]["content"]["application/json"];

/** Request body for PATCH /api/acquisition/followed/{id} */
export type UpdateFollowRequest =
  paths["/api/acquisition/followed/{id}"]["patch"]["requestBody"]["content"]["application/json"];

// ── Read endpoints ──────────────────────────────────────────────────────

/** Fetch followed series list: GET /api/acquisition/followed */
export function getFollowed(
  params: FollowedParams = {},
): Promise<FollowedResponse> {
  return apiFetch("/api/acquisition/followed", {
    method: "get",
    params: { query: params },
  });
}

/** Fetch paginated wanted items: GET /api/acquisition/wanted */
export function getWanted(params: WantedParams = {}): Promise<WantedResponse> {
  return apiFetch("/api/acquisition/wanted", {
    method: "get",
    params: { query: params },
  });
}

/** Fetch seed obligations: GET /api/acquisition/obligations */
export function getObligations(
  params: ObligationsParams = {},
): Promise<ObligationsResponse> {
  return apiFetch("/api/acquisition/obligations", {
    method: "get",
    params: { query: params },
  });
}

/** Fetch acquisition status (watcher state + recent runs): GET /api/acquisition/status */
export function getAcquisitionStatus(): Promise<AcquisitionStatusResponse> {
  return apiFetch("/api/acquisition/status", { method: "get" });
}

// ── Mutating endpoints ──────────────────────────────────────────────────

/** Follow (or reactivate) a series: POST /api/acquisition/followed */
export function createFollow(
  body: CreateFollowRequest,
): Promise<FollowedSeriesItem> {
  return apiFetch("/api/acquisition/followed", {
    method: "post",
    body,
    headers: XRW_HEADERS,
  });
}

/** Update a followed series (active toggle / cadence): PATCH /api/acquisition/followed/{id} */
export function updateFollow(
  id: number,
  body: UpdateFollowRequest,
): Promise<FollowedSeriesItem> {
  return apiFetch("/api/acquisition/followed/{id}", {
    method: "patch",
    body,
    headers: XRW_HEADERS,
    params: { path: { id } },
  });
}

/** Soft-unfollow a series: DELETE /api/acquisition/followed/{id} */
export function deleteFollow(id: number): Promise<void> {
  return apiFetch("/api/acquisition/followed/{id}", {
    method: "delete",
    headers: XRW_HEADERS,
    params: { path: { id } },
  });
}
```

## hooks/useAcquisition.ts — TanStack Query hooks

```typescript
/**
 * TanStack Query hooks for the acquisition surface (acq-watch feature).
 *
 * Four read hooks + three mutations, bound to the typed client in
 * ``@/api/acquisition``.  Query keys follow the established convention
 * (namespaced arrays, mirroring useMaintenanceKeys / useConfigKeys).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getFollowed,
  getWanted,
  getObligations,
  getAcquisitionStatus,
  createFollow,
  updateFollow,
  deleteFollow,
  type FollowedParams,
  type WantedParams,
  type ObligationsParams,
  type CreateFollowRequest,
  type UpdateFollowRequest,
} from "@/api/acquisition";

// ── Query key factories ─────────────────────────────────────────────────

export const acqKeys = {
  all: ["acquisition"] as const,
  followed: (params: FollowedParams = {}) =>
    [...acqKeys.all, "followed", params] as const,
  wanted: (params: WantedParams = {}) =>
    [...acqKeys.all, "wanted", params] as const,
  obligations: (params: ObligationsParams = {}) =>
    [...acqKeys.all, "obligations", params] as const,
  status: () => [...acqKeys.all, "status"] as const,
};

// ── Read hooks ──────────────────────────────────────────────────────────

export function useFollowed(params: FollowedParams = {}) {
  return useQuery({
    queryKey: acqKeys.followed(params),
    queryFn: () => getFollowed(params),
  });
}

export function useWanted(params: WantedParams = {}) {
  return useQuery({
    queryKey: acqKeys.wanted(params),
    queryFn: () => getWanted(params),
  });
}

export function useObligations(params: ObligationsParams = {}) {
  return useQuery({
    queryKey: acqKeys.obligations(params),
    queryFn: () => getObligations(params),
  });
}

export function useAcquisitionStatus() {
  return useQuery({
    queryKey: acqKeys.status(),
    queryFn: getAcquisitionStatus,
  });
}

// ── Mutation hooks ──────────────────────────────────────────────────────

export function useFollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateFollowRequest) => createFollow(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: acqKeys.all });
    },
  });
}

export function useUpdateFollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UpdateFollowRequest }) =>
      updateFollow(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: acqKeys.all });
    },
  });
}

export function useUnfollow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteFollow(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: acqKeys.all });
    },
  });
}
```

Note on invalidation: all three mutations invalidate `acqKeys.all` (the
entire acquisition namespace). This is a deliberate simplification for S7
— a follow change can affect the wanted queue (new episodes get enqueued)
and the obligations panel. If this proves too coarse (e.g. flickering the
status panel on every follow toggle), scope invalidation down in a follow-up.

## Tests

### api/acquisition.test.ts

Mock `apiFetch` (the actual `fetch` call is inside it). Test:

1. `getFollowed()` calls `apiFetch` with correct path, method, and default query.
2. `getFollowed({active: "all"})` passes query params.
3. `getWanted({status: "pending", page: 2, page_size: 25})` serialises correctly.
4. `createFollow({tvdb_id: 123, title: "Test"})` sends body + XRW headers.
5. `updateFollow(5, {active: false})` interpolates path param `{id}`.
6. `deleteFollow(5)` sends DELETE with XRW headers.
7. `getAcquisitionStatus()` is a bare GET with no params.

### hooks/useAcquisition.test.tsx

Use `renderHook` with `QueryClientProvider` wrapper, mock the API functions:

1. `useFollowed()` — returns data on success, loading state initially.
2. `useWanted({status: "pending"})` — passes params through.
3. `useFollow()` mutation — onSuccess invalidates acqKeys.all (assert via
   `queryClient.getQueryData` clearing or a spy on `invalidateQueries`).
4. `useUnfollow()` — calls `deleteFollow` with the id, invalidates on success.
5. `useUpdateFollow()` — calls `updateFollow` with `{id, body}`, invalidates.
6. Query key stability: `acqKeys.followed({active: "active"})` referentially
   equal across calls with same params.

## Type exports for Phase 4

Phase 4 (AcquisitionPage) imports from these modules:

- `@/api/acquisition`: `FollowedSeriesItem`, `WantedItem`, `ObligationItem`,
  `AcquisitionStatusResponse`, `CreateFollowRequest`, `UpdateFollowRequest`,
  `FollowedParams`, `WantedParams`, `ObligationsParams`.
- `@/hooks/useAcquisition`: `useFollowed`, `useWanted`, `useObligations`,
  `useAcquisitionStatus`, `useFollow`, `useUpdateFollow`, `useUnfollow`,
  `acqKeys`.
- `@/api/client`: `setWatcher` (the existing pipeline watcher toggle — reused,
  no new acquisition-specific watcher hook).
