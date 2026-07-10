/**
 * Unit tests for the registry status TanStack Query hook (reg-health Phase 3).
 *
 * Mocks fetch and asserts query keys, success responses, and error surfaces.
 * Follows the wrapper pattern established by ``useDecisions.test.tsx``.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { type ReactElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useRegistryStatus } from "@/hooks/useRegistryStatus";
import { registryKeys } from "@/api/registry";

import type { RegistryStatusResponse } from "@/api/registry";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal ``Response``-shaped object the API client can consume. */
function buildResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "",
    json: () => Promise.resolve(body),
  } as unknown as Response;
}

const fetchMock = vi.fn<typeof fetch>();

/** A minimal RegistryStatusResponse-shaped payload. */
const STATUS: RegistryStatusResponse = {
  providers: [
    {
      provider_name: "tmdb",
      circuit_state: "closed",
      failure_count_recent: 0,
      last_success_at: 1719792000.0,
      last_failure_at: null,
      last_latency_ms: 42.5,
      live: true,
    },
  ],
};

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

/**
 * Create a wrapper providing a fresh QueryClient (retries disabled) so each
 * test starts with a clean cache.
 */
function createWrapper(): (props: { children: ReactNode }) => ReactElement {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests — query keys
// ---------------------------------------------------------------------------

describe("registryKeys", () => {
  it("all returns ['registry']", () => {
    expect(registryKeys.all).toEqual(["registry"]);
  });

  it("status() returns ['registry', 'status']", () => {
    expect(registryKeys.status()).toEqual(["registry", "status"]);
  });
});

// ---------------------------------------------------------------------------
// Tests — useRegistryStatus
// ---------------------------------------------------------------------------

describe("useRegistryStatus", () => {
  it("returns loading state initially", () => {
    fetchMock.mockReturnValue(new Promise<Response>(() => undefined));
    const { result } = renderHook(() => useRegistryStatus(), {
      wrapper: createWrapper(),
    });
    expect(result.current.isLoading).toBe(true);
  });

  it("returns provider data on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, STATUS));

    const { result } = renderHook(() => useRegistryStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(STATUS);
    // Guards narrow the type so individual-field assertions don't need ``!``.
    const data = result.current.data;
    if (data) {
      const first = data.providers[0];
      if (first) {
        expect(first.provider_name).toBe("tmdb");
        expect(first.circuit_state).toBe("closed");
        expect(first.live).toBe(true);
      }
    }
  });

  it("surfaces fetch errors", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useRegistryStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
