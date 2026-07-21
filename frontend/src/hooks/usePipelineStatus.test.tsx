import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import {
  type ReactElement,
  type ReactNode,
  createContext,
  useContext,
  useState,
} from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EventStreamContext } from "@/hooks/useEventStreamContext";
import type { EventStreamState } from "@/hooks/useEventStream";
import { pipelineKeys } from "@/api/pipeline";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";

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

/** A running-pipeline status payload. */
const RUNNING_STATUS = {
  state: "running",
  run_uid: "run-001",
  step: "sort",
  paused: false,
  watcher_enabled: true,
  pid: 12345,
};

const fetchMock = vi.fn<typeof fetch>();

// ---------------------------------------------------------------------------
// Wrapper helpers
// ---------------------------------------------------------------------------

/** Context for mutating the wrapper's events from inside a test. */
const WrapperStateContext = createContext<{
  pushEvent: (type: string) => void;
} | null>(null);

/** Read the wrapper-state handle (only valid inside the test wrapper). */
function useWrapperState(): {
  pushEvent: (type: string) => void;
} {
  const ctx = useContext(WrapperStateContext);
  if (ctx === null) {
    throw new Error("useWrapperState must be called inside the test wrapper.");
  }
  return ctx;
}

/**
 * Create a wrapper that provides both QueryClientProvider and
 * EventStreamContext so the hook can read events.
 */
function createWrapper(): (props: { children: ReactNode }) => ReactElement {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    const [events, setEvents] = useState<
      readonly { id: string; type: string; data: Record<string, unknown> }[]
    >([]);

    const streamState: EventStreamState = {
      events,
      connectionState: "connected",
      buildCommit: "test-commit",
      lastEventId: null,
    };

    const pushEvent = (type: string): void => {
      setEvents((prev) => [
        ...prev,
        {
          id: `${String(Date.now())}-0`,
          type,
          data: {},
        },
      ]);
    };

    return (
      <QueryClientProvider client={client}>
        <EventStreamContext.Provider value={streamState}>
          <WrapperStateContext.Provider value={{ pushEvent }}>
            {children}
          </WrapperStateContext.Provider>
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
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("pipelineKeys", () => {
  it("expose une clé de requête stable ['pipeline', 'status']", () => {
    expect(pipelineKeys.status).toEqual(["pipeline", "status"]);
  });
});

describe("usePipelineStatus", () => {
  it("renvoie le statut idle tant que la première requête est en vol", () => {
    // Never resolve — the hook should still yield the default snapshot.
    fetchMock.mockReturnValue(new Promise<never>(() => undefined));

    const { result } = renderHook(() => usePipelineStatus(), {
      wrapper: createWrapper(),
    });

    expect(result.current.snapshot.state).toBe("idle");
    expect(result.current.snapshot.run_uid).toBeNull();
    expect(result.current.snapshot.paused).toBe(false);
    expect(result.current.isLoading).toBe(true);
  });

  it("renvoie le statut pipeline après résolution de la requête", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, RUNNING_STATUS));

    const { result } = renderHook(() => usePipelineStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.snapshot).toEqual({
      state: "running",
      run_uid: "run-001",
      step: "sort",
      paused: false,
      watcher_enabled: true,
      pid: 12345,
    });
  });

  it("reste sur le snapshot par défaut quand data est undefined", async () => {
    // Return a 500 so the query errors — data stays undefined.
    fetchMock.mockResolvedValue(buildResponse(500, { detail: "boom" }));

    const { result } = renderHook(() => usePipelineStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    // The snapshot should still be the default, not crash.
    expect(result.current.snapshot.state).toBe("idle");
    expect(result.current.snapshot.paused).toBe(false);
  });

  it("invalide le cache quand un événement PipelineStarted arrive sur le flux", async () => {
    let callCount = 0;
    fetchMock.mockImplementation(() => {
      callCount += 1;
      return Promise.resolve(buildResponse(200, RUNNING_STATUS));
    });

    const { result } = renderHook(
      () => {
        const { pushEvent } = useWrapperState();
        return { status: usePipelineStatus(), pushEvent };
      },
      { wrapper: createWrapper() },
    );

    // Wait for the initial query to settle.
    await waitFor(() => {
      expect(result.current.status.isSuccess).toBe(true);
    });
    const initialCount = callCount;
    expect(initialCount).toBeGreaterThanOrEqual(1);

    // Push a PipelineStarted event — should trigger an invalidation → refetch.
    act(() => {
      result.current.pushEvent("PipelineStarted");
    });

    await waitFor(() => {
      expect(callCount).toBeGreaterThan(initialCount);
    });
  });

  it("n'invalide PAS le cache pour un événement non-pertinent", async () => {
    let callCount = 0;
    fetchMock.mockImplementation(() => {
      callCount += 1;
      return Promise.resolve(buildResponse(200, RUNNING_STATUS));
    });

    const { result } = renderHook(
      () => {
        const { pushEvent } = useWrapperState();
        return { status: usePipelineStatus(), pushEvent };
      },
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.status.isSuccess).toBe(true);
    });
    const initialCount = callCount;

    // Push a non-state-changing event (e.g. a log line) — no invalidation.
    act(() => {
      result.current.pushEvent("PipelineLogLine");
    });

    // Let any async work settle.
    await new Promise((resolve) => {
      setTimeout(resolve, 200);
    });

    expect(callCount).toBe(initialCount);
  });

  it("invalide le cache pour StepCompleted", async () => {
    let callCount = 0;
    fetchMock.mockImplementation(() => {
      callCount += 1;
      return Promise.resolve(buildResponse(200, RUNNING_STATUS));
    });

    const { result } = renderHook(
      () => {
        const { pushEvent } = useWrapperState();
        return { status: usePipelineStatus(), pushEvent };
      },
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(result.current.status.isSuccess).toBe(true);
    });
    const initialCount = callCount;

    act(() => {
      result.current.pushEvent("StepCompleted");
    });

    await waitFor(() => {
      expect(callCount).toBeGreaterThan(initialCount);
    });
  });
});
