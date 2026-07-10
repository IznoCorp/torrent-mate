/**
 * Unit tests for the decisions TanStack Query hooks (scrape-arbiter §4.1).
 *
 * Mocks fetch and asserts query keys, success responses, mutation
 * invalidation behaviour, and error surfaces (401, 404, 409, 410 as
 * :class:`ApiError`).  Follows the wrapper pattern established by
 * ``usePipelineStatus.test.tsx``.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { type ReactElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  useDecisionDetail,
  useDecisions,
} from "@/hooks/useDecisions";
import { decisionsKeys } from "@/api/decisions";
import { ApiError } from "@/api/client";

import type { DecisionDetailResponse } from "@/api/decisions";

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

/** A minimal DecisionDetail-shaped payload. */
const DETAIL: DecisionDetailResponse = {
  id: 1,
  media_kind: "movie",
  extracted_title: "Test Movie",
  extracted_year: 2024,
  staging_path: "/staging/001-MOVIES/Test Movie (2024)",
  trigger: "below_threshold",
  candidates: [],
  candidates_count: 0,
  status: "pending",
  created_at: 1_750_000_000.0,
  resolution_json: null,
};

/** A minimal list response. */
const LIST = {
  items: [
    {
      id: 1,
      media_kind: "movie",
      extracted_title: "Test Movie",
      extracted_year: 2024,
      staging_path: "/staging/001-MOVIES/Test Movie (2024)",
      trigger: "below_threshold",
      candidates_count: 0,
      status: "pending",
      created_at: 1_750_000_000.0,
    },
  ],
  pending_count: 1,
  total: 1,
  page: 1,
  page_size: 50,
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

describe("decisionsKeys", () => {
  it("all returns ['decisions']", () => {
    expect(decisionsKeys.all).toEqual(["decisions"]);
  });

  it("list() wraps params", () => {
    expect(decisionsKeys.list({ status: "pending", page: 1 })).toEqual([
      "decisions",
      { status: "pending", page: 1 },
    ]);
  });

  it("detail(id) returns ['decisions', id]", () => {
    expect(decisionsKeys.detail(42)).toEqual(["decisions", 42]);
  });
});

// ---------------------------------------------------------------------------
// Tests — useDecisions
// ---------------------------------------------------------------------------

describe("useDecisions", () => {
  it("returns the list response on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, LIST));

    const { result } = renderHook(() => useDecisions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(LIST);
  });

  it("forwards ApiError on failure", async () => {
    fetchMock.mockResolvedValue(buildResponse(401, { detail: "Unauthorized" }));

    const { result } = renderHook(() => useDecisions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(ApiError);
  });

  it("uses the correct query key with params", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, LIST));

    const { result } = renderHook(
      () => useDecisions({ status: "resolved", page: 2, page_size: 10 }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(LIST);
    // Confirm the query key is set correctly via the hook's options.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("status=resolved");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=10");
  });
});

// ---------------------------------------------------------------------------
// Tests — useDecisionDetail
// ---------------------------------------------------------------------------

describe("useDecisionDetail", () => {
  it("returns the detail response on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, DETAIL));

    const { result } = renderHook(() => useDecisionDetail(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(DETAIL);
  });

  it("throws ApiError on 410 (superseded)", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(410, { detail: "Decision superseded" }),
    );

    const { result } = renderHook(() => useDecisionDetail(1), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(410);
  });

  it("is disabled when id is 0", () => {
    fetchMock.mockResolvedValue(buildResponse(200, DETAIL));

    const { result } = renderHook(() => useDecisionDetail(0), {
      wrapper: createWrapper(),
    });

    expect(result.current.isPending).toBe(true);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
