# Phase 3 — Frontend typed client + hook

## Gate

```bash
cd frontend
npm run lint
npm run typecheck
npx vitest run
```

All three must pass with zero errors.

## Objectives

1. Create `frontend/src/api/registry.ts` — typed client mirroring the
   `GET /api/registry/status` endpoint, using the `apiFetch` + generated
   `schema.d.ts` pattern established by `frontend/src/api/decisions.ts`
   (R15 typed path/query params, no raw fetch, no `any`).
2. Create `frontend/src/hooks/useRegistryStatus.ts` — TanStack Query hook
   wrapping the typed client, following the pattern of `useDecisions`.
3. Create `frontend/src/hooks/useRegistryStatus.test.tsx` — Vitest coverage
   for the hook (query key stability, success/error paths).

## Files to create

- `frontend/src/api/registry.ts`
- `frontend/src/hooks/useRegistryStatus.ts`
- `frontend/src/hooks/useRegistryStatus.test.tsx`

## Files to modify

None. This phase is additive — the typed client and hook are new files
consumed by Phase 4 (the page).

## Typed client (`frontend/src/api/registry.ts`)

Follows the exact pattern of `frontend/src/api/decisions.ts`:

```typescript
/**
 * Typed API client helpers for the /api/registry REST endpoints
 * (reg-health, DESIGN §3.3).
 *
 * Every helper routes through {@link apiFetch} with schema-typed path
 * params (R15) — no raw fetch and no ``any``.  Response types are
 * inferred from the regenerated ``schema.d.ts`` so a backend signature
 * change breaks at compile time, not at runtime.
 */

import type { components, paths } from "./schema";
import { apiFetch } from "./client";

// ---------------------------------------------------------------------------
// Re-export schema component types so the UI layer can import from one place.
// ---------------------------------------------------------------------------

/** A single provider's runtime status as returned by GET /api/registry/status. */
export type ProviderStatusItem = components["schemas"]["ProviderStatusItem"];

// ---------------------------------------------------------------------------
// Inline type helper (mirrors decisions.ts)
// ---------------------------------------------------------------------------

/**
 * Extract the ``application/json`` response body from an openapi-typescript
 * response map (200).
 */
type SuccessBody<T> = T extends {
  200: { content: { "application/json": infer B } };
}
  ? B
  : never;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/** Response body for ``GET /api/registry/status``. */
export type RegistryStatusResponse = SuccessBody<
  paths["/api/registry/status"]["get"]["responses"]
>;

// ---------------------------------------------------------------------------
// Stable TanStack Query keys
// ---------------------------------------------------------------------------

/**
 * Stable React-Query keys for the registry domain.
 *
 * Exported so mutations and the event-stream patch can invalidate the exact
 * same cache entries.  Follows the established ``decisionsKeys`` /
 * ``pipelineKeys`` / ``maintenanceKeys`` pattern.
 */
export const registryKeys = {
  /** Root registry key: ``['registry']``. */
  all: ["registry"] as const,

  /** Status query key: ``['registry', 'status']``. */
  status: () => ["registry", "status"] as const,
};

// ---------------------------------------------------------------------------
// Typed endpoint helpers
// ---------------------------------------------------------------------------

/**
 * Fetch the live status of every configured provider.
 *
 * Sends ``GET /api/registry/status`` through the typed {@link apiFetch}
 * (R15).  Read-only — no ``X-Requested-With`` header.
 *
 * Returns:
 *   A {@link RegistryStatusResponse} with a ``providers[]`` of
 *   {@link ProviderStatusItem}.
 */
export function fetchRegistryStatus(): Promise<RegistryStatusResponse> {
  return apiFetch("/api/registry/status", {
    method: "get",
  });
}
```

## TanStack Query hook (`frontend/src/hooks/useRegistryStatus.ts`)

Follows the exact pattern of `frontend/src/hooks/useDecisions.ts`:

```typescript
/**
 * TanStack Query hook for the registry status domain (reg-health §3.4).
 *
 * Thin wrapper over the typed helper in :mod:`@/api/registry`.  Follows
 * the pattern established by {@link useDecisions}: stable query keys from
 * {@link registryKeys}, a single ``useQuery`` hook.
 */

import { useQuery } from "@tanstack/react-query";

import {
  type RegistryStatusResponse,
  fetchRegistryStatus,
  registryKeys,
} from "@/api/registry";

/**
 * Fetch the live registry status snapshot.
 *
 * Query key: ``['registry', 'status']``.
 *
 * Returns:
 *   The TanStack Query result for a {@link RegistryStatusResponse}.
 */
export function useRegistryStatus() {
  return useQuery<RegistryStatusResponse>({
    queryKey: registryKeys.status(),
    queryFn: () => fetchRegistryStatus(),
  });
}
```

## Vitest tests (`frontend/src/hooks/useRegistryStatus.test.tsx`)

Follows the project's existing hook test conventions (see
`frontend/src/hooks/useDecisions.test.tsx` for the pattern — MSW or
mock `apiFetch` + `renderHook` from `@testing-library/react`).

```typescript
/**
 * Vitest tests for the useRegistryStatus hook (reg-health Phase 3).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";

import { useRegistryStatus } from "./useRegistryStatus";

// Mock the typed client — we test the hook integration, not the network.
vi.mock("@/api/registry", async () => {
  const actual = await vi.importActual("@/api/registry");
  return {
    ...actual,
    fetchRegistryStatus: vi.fn(),
  };
});

const { fetchRegistryStatus } = await import("@/api/registry");

function createWrapper(): (props: { children: React.ReactNode }) => ReactElement {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("useRegistryStatus", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns loading state initially", () => {
    vi.mocked(fetchRegistryStatus).mockReturnValue(new Promise(() => {}));
    const { result } = renderHook(() => useRegistryStatus(), {
      wrapper: createWrapper(),
    });
    expect(result.current.isLoading).toBe(true);
  });

  it("returns provider data on success", async () => {
    const mockResponse = {
      providers: [
        {
          provider_name: "tmdb",
          circuit_state: "closed" as const,
          failure_count_recent: 0,
          last_success_at: 1719792000.0,
          last_failure_at: null,
          last_latency_ms: 42.5,
          degraded: false,
        },
      ],
    };
    vi.mocked(fetchRegistryStatus).mockResolvedValue(mockResponse);

    const { result } = renderHook(() => useRegistryStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.data!.providers).toHaveLength(1);
    expect(result.current.data!.providers[0].provider_name).toBe("tmdb");
    expect(result.current.data!.providers[0].circuit_state).toBe("closed");
  });

  it("surfaces fetch errors", async () => {
    vi.mocked(fetchRegistryStatus).mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useRegistryStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it("uses stable query key", () => {
    // The query key is a constant array — must not depend on params.
    const { registryKeys } = require("@/api/registry");
    expect(registryKeys.status()).toEqual(["registry", "status"]);
  });
});
```

## Gotchas

- **typed `apiFetch` pattern (R15)**: params must be typed via `paths["/api/registry/status"]["get"]`,
  not `any`. See `frontend/src/api/decisions.ts` for the canonical shape.

- **No XRW headers**: this is a GET/read, so no `X-Requested-With` header.
  Do NOT import `XRW_HEADERS` from `client.ts`.

- **`apiFetch` handles auth cookies**: the session cookie is auto-attached
  by the shared `apiFetch` wrapper — no manual cookie handling in this
  module.

- **`registryKeys` pattern**: export the query key factory so the Phase 4
  page can invalidate it on WS event arrival (TanStack Query `queryClient.invalidateQueries`).
  Follow the `decisionsKeys` / `pipelineKeys` convention exactly.

- **Frontend CI runs eslint separately**: run `npm run lint` AND
  `npm run typecheck` before committing. eslint is a separate gate from
  the TypeScript compiler (feedback_frontend_ci_eslint_gate).
