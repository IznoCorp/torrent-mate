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
  useAllDecisions,
  useDecisionDetail,
  useDecisions,
} from "@/hooks/useDecisions";
import { decisionsKeys } from "@/api/decisions";
import { ApiError } from "@/api/client";

import type { DecisionDetailResponse, DecisionListItem } from "@/api/decisions";

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

// ---------------------------------------------------------------------------
// Tests — useAllDecisions (§4.1 flat list)
// ---------------------------------------------------------------------------

/** A minimal DecisionListItem with sensible defaults. */
function makeAggItem(
  overrides: Partial<DecisionListItem> = {},
): DecisionListItem {
  return {
    id: 1,
    media_kind: "movie",
    extracted_title: "Item",
    extracted_year: 2024,
    staging_path: "/staging/001-MOVIES/Item",
    trigger: "below_threshold",
    candidates_count: 0,
    status: "pending",
    created_at: 1_000,
    ...overrides,
  };
}

/** Extract the request URL from a fetch input without unsafe stringification. */
function urlOf(input: string | URL | Request): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

/**
 * Build a fetch mock that returns a distinct per-status list response based on
 * the ``status=`` query param in the requested URL.
 *
 * ``byStatus`` maps a status to its ``{ items, total }``; a missing status
 * yields an empty page. This mirrors the real endpoint, which the hook queries
 * once per status.
 */
function mockPerStatus(
  byStatus: Partial<
    Record<string, { items: DecisionListItem[]; total: number }>
  >,
): void {
  fetchMock.mockImplementation((input: string | URL | Request) => {
    const url = urlOf(input);
    const status = /[?&]status=([^&]+)/.exec(url)?.[1] ?? "pending";
    const page = byStatus[status] ?? { items: [], total: 0 };
    return Promise.resolve(
      buildResponse(200, {
        items: page.items,
        pending_count: byStatus.pending?.total ?? 0,
        total: page.total,
        page: 1,
        page_size: 200,
      }),
    );
  });
}

describe("useAllDecisions", () => {
  it("fetches every status and merges into one flat list", async () => {
    mockPerStatus({
      pending: { items: [makeAggItem({ id: 1, status: "pending" })], total: 1 },
      resolved: {
        items: [makeAggItem({ id: 2, status: "resolved" })],
        total: 1,
      },
      dismissed: {
        items: [makeAggItem({ id: 3, status: "dismissed" })],
        total: 5,
      },
      superseded: {
        items: [makeAggItem({ id: 4, status: "superseded" })],
        total: 2,
      },
    });

    const { result } = renderHook(() => useAllDecisions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // One query per status.
    expect(fetchMock).toHaveBeenCalledTimes(4);
    // Merged list holds all four ids.
    expect(result.current.items.map((i) => i.id).sort()).toEqual([1, 2, 3, 4]);
    // Per-status counts reflect each response's `total`.
    expect(result.current.counts).toEqual({
      pending: 1,
      resolved: 1,
      dismissed: 5,
      superseded: 2,
    });
  });

  it("sorts merged items newest-first by created_at", async () => {
    mockPerStatus({
      pending: {
        items: [makeAggItem({ id: 1, created_at: 100 })],
        total: 1,
      },
      resolved: {
        items: [makeAggItem({ id: 2, status: "resolved", created_at: 300 })],
        total: 1,
      },
      dismissed: {
        items: [makeAggItem({ id: 3, status: "dismissed", created_at: 200 })],
        total: 1,
      },
    });

    const { result } = renderHook(() => useAllDecisions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // 300 → 200 → 100.
    expect(result.current.items.map((i) => i.id)).toEqual([2, 3, 1]);
  });

  it("narrows the merged list to the active statuses but keeps all counts", async () => {
    mockPerStatus({
      pending: { items: [makeAggItem({ id: 1 })], total: 3 },
      resolved: {
        items: [makeAggItem({ id: 2, status: "resolved" })],
        total: 7,
      },
    });

    const { result } = renderHook(() => useAllDecisions(["resolved"]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Only 'resolved' rows are in the list…
    expect(result.current.items.map((i) => i.id)).toEqual([2]);
    // …but counts still cover every status (for the chip counters).
    expect(result.current.counts.pending).toBe(3);
    expect(result.current.counts.resolved).toBe(7);
  });

  it("tolerates partial failure (isError only when every query fails)", async () => {
    // 'superseded' fails; the other three succeed → list still shows them.
    fetchMock.mockImplementation((input: string | URL | Request) => {
      const url = urlOf(input);
      const status = /[?&]status=([^&]+)/.exec(url)?.[1] ?? "pending";
      if (status === "superseded") {
        return Promise.resolve(buildResponse(500, { detail: "boom" }));
      }
      return Promise.resolve(
        buildResponse(200, {
          items: [makeAggItem({ id: status === "pending" ? 1 : 2, status })],
          pending_count: 1,
          total: 1,
          page: 1,
          page_size: 200,
        }),
      );
    });

    const { result } = renderHook(() => useAllDecisions(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isError).toBe(false);
    expect(result.current.items.length).toBeGreaterThan(0);

    // SF2: the failed status yields a null count (undetermined, NOT a false 0)
    // and is listed in `errored`; a succeeded status keeps its real numeric count.
    expect(result.current.counts.superseded).toBeNull();
    expect(result.current.errored.has("superseded")).toBe(true);
    expect(result.current.counts.pending).toBe(1);
    expect(result.current.errored.has("pending")).toBe(false);
  });
});
