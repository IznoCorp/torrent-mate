/**
 * Unit tests for useLastPipelineRun (control-medias §C4/C5 / T#7).
 *
 * Mocks fetch and asserts the hook surfaces the correct runUid, counts,
 * stepReasons (queue-step exclusion), isLoading, and isError.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useLastPipelineRun } from "@/hooks/useLastPipelineRun";

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

/** Resolve the request target to its URL string. */
function urlOf(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

const HISTORY_RESPONSE = {
  runs: [
    {
      run_uid: "run-abc123",
      kind: "pipeline",
      trigger: "web",
      started_at: "2026-07-17T10:00:00Z",
      ended_at: "2026-07-17T10:05:00Z",
      outcome: "completed",
      queued_at: "2026-07-17T10:00:00Z",
      paused: false,
    },
  ],
  total: 1,
};

const DETAIL_RESPONSE = {
  run_uid: "run-abc123",
  kind: "pipeline",
  trigger: "web",
  started_at: "2026-07-17T10:00:00Z",
  ended_at: "2026-07-17T10:05:00Z",
  outcome: "completed",
  paused: false,
  steps: [
    {
      name: "ingest",
      label: "Récupération",
      state: "done",
      success_count: 2,
      error_count: 0,
      skip_count: 3,
      queued_count: 0,
      running_count: 0,
      reasons: ["Film X : espace disque insuffisant"],
      started_at: null,
      ended_at: null,
      paused: false,
    },
    {
      name: "queue",
      label: "File d'attente",
      state: "done",
      success_count: 0,
      error_count: 0,
      skip_count: 0,
      queued_count: 0,
      running_count: 0,
      reasons: ["queue reason should be excluded"],
      started_at: null,
      ended_at: null,
      paused: false,
    },
    {
      name: "scrape",
      label: "Recherche métadonnées",
      state: "done",
      success_count: 1,
      error_count: 0,
      skip_count: 0,
      queued_count: 0,
      running_count: 0,
      reasons: [],
      started_at: null,
      ended_at: null,
      paused: false,
    },
  ],
};

const fetchMock = vi.fn<typeof fetch>();

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function createWrapper(): (props: { children: ReactNode }) => ReactElement {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
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
  fetchMock.mockImplementation((input) => {
    const url = urlOf(input);
    if (url.includes("/api/pipeline/history") && !url.includes("/run-")) {
      return Promise.resolve(buildResponse(200, HISTORY_RESPONSE));
    }
    if (url.includes("/api/pipeline/history/run-")) {
      return Promise.resolve(buildResponse(200, DETAIL_RESPONSE));
    }
    return Promise.resolve(buildResponse(200, {}));
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useLastPipelineRun", () => {
  it("surfaces the run_uid from the history list", async () => {
    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.runUid).toBe("run-abc123");
    });
  });

  it("surfaces the trigger, startedAt, endedAt, outcome", async () => {
    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.trigger).toBe("web");
    });
    expect(result.current.startedAt).toBe("2026-07-17T10:00:00Z");
    expect(result.current.endedAt).toBe("2026-07-17T10:05:00Z");
    expect(result.current.outcome).toBe("completed");
  });

  it("computes totalProcessed and totalSkipped across steps", async () => {
    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.totalProcessed).toBe(3);
    });
    expect(result.current.totalSkipped).toBe(3);
  });

  it("excludes queue step from stepReasons (T#7)", async () => {
    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.stepReasons.length).toBeGreaterThan(0);
    });

    const steps = result.current.stepReasons.map((s) => s.step);
    expect(steps).not.toContain("queue");
    expect(steps).toContain("ingest");
    // scrape step has empty reasons → excluded
  });

  it("excludes steps with empty reasons from stepReasons", async () => {
    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      // The scrape step has reasons=[], so it should be excluded
      const steps = result.current.stepReasons.map((s) => s.step);
      expect(steps).not.toContain("scrape");
    });
  });

  it("returns null runUid when history is empty", async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((input) => {
      const url = urlOf(input);
      if (url.includes("/api/pipeline/history") && !url.includes("/run-")) {
        return Promise.resolve(buildResponse(200, { runs: [], total: 0 }));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.runUid).toBeNull();
    });
    expect(result.current.trigger).toBeNull();
  });

  it("exposes isError when the history query fails (T#7)", async () => {
    fetchMock.mockReset();
    fetchMock.mockRejectedValue(new Error("Network Error"));

    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it("exposes isError when the detail query fails", async () => {
    fetchMock.mockReset();
    fetchMock.mockImplementation((input) => {
      const url = urlOf(input);
      if (url.includes("/api/pipeline/history") && !url.includes("/run-")) {
        return Promise.resolve(buildResponse(200, HISTORY_RESPONSE));
      }
      // Detail query fails
      if (url.includes("/api/pipeline/history/run-")) {
        return Promise.reject(new Error("Detail fetch failed"));
      }
      return Promise.resolve(buildResponse(200, {}));
    });

    const { result } = renderHook(() => useLastPipelineRun(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
