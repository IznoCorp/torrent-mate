import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook } from "@testing-library/react";
import { type ReactElement, type ReactNode, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventStreamContext } from "@/hooks/useEventStreamContext";
import type { EventStreamState } from "@/hooks/useEventStream";
import { useStagingMedia } from "@/hooks/useStagingMedia";

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

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

/**
 * Create a wrapper that provides both QueryClientProvider and
 * EventStreamContext so the hook can read events (no WS events are pushed
 * in this suite — the empty events array keeps the invalidation effect inert).
 */
function createWrapper(): (props: { children: ReactNode }) => ReactElement {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    const [events] = useState<
      readonly { id: string; type: string; data: Record<string, unknown> }[]
    >([]);

    const streamState: EventStreamState = {
      events,
      connectionState: "connected",
      buildCommit: "test-commit",
      lastEventId: null,
    };

    return (
      <QueryClientProvider client={client}>
        <EventStreamContext.Provider value={streamState}>
          {children}
        </EventStreamContext.Provider>
      </QueryClientProvider>
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
  vi.useRealTimers();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useStagingMedia", () => {
  it("polls at 8 s by default (backward-compat, no queryOptions)", async () => {
    vi.useFakeTimers();
    let callCount = 0;
    fetchMock.mockImplementation(() => {
      callCount += 1;
      return Promise.resolve(
        buildResponse(200, { items: [], counts: { total: 0 } }),
      );
    });

    renderHook(() => useStagingMedia({}), { wrapper: createWrapper() });

    // Flush the initial fetch promise + React effects without triggering the
    // 8 s refetch interval (advance 0 ms only drains microtasks).
    await vi.advanceTimersByTimeAsync(0);
    expect(callCount).toBe(1);

    // Advance 7 s — still only the initial request.
    await vi.advanceTimersByTimeAsync(7_000);
    expect(callCount).toBe(1);

    // Advance to 8 s — the poll interval fires a second request.
    await vi.advanceTimersByTimeAsync(1_000);
    expect(callCount).toBe(2);
  });

  it("respects custom refetchInterval: 1 request before 60 s, a 2nd after", async () => {
    vi.useFakeTimers();
    let callCount = 0;
    fetchMock.mockImplementation(() => {
      callCount += 1;
      return Promise.resolve(
        buildResponse(200, { items: [], counts: { total: 0 } }),
      );
    });

    renderHook(() => useStagingMedia({}, { refetchInterval: 60_000 }), {
      wrapper: createWrapper(),
    });

    // Initial request fires immediately.
    await vi.advanceTimersByTimeAsync(0);
    expect(callCount).toBe(1);

    // Advance 59 s — still only the initial request.
    await vi.advanceTimersByTimeAsync(59_000);
    expect(callCount).toBe(1);

    // Advance to 60 s — the custom interval fires a second request.
    await vi.advanceTimersByTimeAsync(1_000);
    expect(callCount).toBe(2);
  });
});
