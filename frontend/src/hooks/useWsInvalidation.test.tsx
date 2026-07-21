/**
 * Unit tests for {@link useWsInvalidation} — the one WS-event → invalidation
 * map. Asserts that a mapped event invalidates the mapped keys, an unmapped
 * event does not, a matching event buried in a BATCHED burst is still caught
 * (the fresh-slice guarantee the retired newest-only idiom lacked), and that
 * independent rules fire independently. Follows the EventStreamContext wrapper
 * pattern from ``usePipelineStatus.test.tsx``.
 */

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
import { useWsInvalidation } from "@/hooks/useWsInvalidation";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

interface TestEvent {
  readonly id: string;
  readonly type: string;
  readonly data: Record<string, unknown>;
}

/** Monotonic id source so appended test events carry distinct stream ids. */
let idSeq = 0;

/** Handle to append one or more events from inside a test. */
const PushContext = createContext<{
  push: (types: string | readonly string[]) => void;
} | null>(null);

function usePush(): { push: (types: string | readonly string[]) => void } {
  const ctx = useContext(PushContext);
  if (ctx === null) {
    throw new Error("usePush must be used inside the test wrapper.");
  }
  return ctx;
}

/** Wrapper providing a controllable event ring over the given QueryClient. */
function makeWrapper(
  client: QueryClient,
): (props: { children: ReactNode }) => ReactElement {
  return function Wrapper({ children }: { children: ReactNode }): ReactElement {
    const [events, setEvents] = useState<readonly TestEvent[]>([]);
    const state: EventStreamState = {
      events,
      connectionState: "connected",
      buildCommit: "test-commit",
      lastEventId: null,
    };
    const push = (types: string | readonly string[]): void => {
      const list = typeof types === "string" ? [types] : types;
      setEvents((prev) => [
        ...prev,
        ...list.map((type) => {
          idSeq += 1;
          return { id: `${String(idSeq)}-0`, type, data: {} };
        }),
      ]);
    };
    return (
      <QueryClientProvider client={client}>
        <EventStreamContext.Provider value={state}>
          <PushContext.Provider value={{ push }}>
            {children}
          </PushContext.Provider>
        </EventStreamContext.Provider>
      </QueryClientProvider>
    );
  };
}

/** Sleep for *ms* using a real timer (to observe that nothing was invalidated). */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

beforeEach(() => {
  idSeq = 0;
});

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useWsInvalidation", () => {
  it("invalidates every mapped key when a matching event arrives", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => {
        const { push } = usePush();
        useWsInvalidation([
          { types: new Set(["StepCompleted"]), keys: [["a"], ["b"]] },
        ]);
        return { push };
      },
      { wrapper: makeWrapper(client) },
    );

    // Ignore the inert mount pass (empty ring → no invalidation).
    spy.mockClear();

    act(() => {
      result.current.push("StepCompleted");
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: ["a"] });
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: ["b"] });
  });

  it("does not invalidate for an unmapped event", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => {
        const { push } = usePush();
        useWsInvalidation([
          { types: new Set(["StepCompleted"]), keys: [["a"]] },
        ]);
        return { push };
      },
      { wrapper: makeWrapper(client) },
    );

    spy.mockClear();

    act(() => {
      result.current.push("PipelineLogLine");
    });

    await sleep(50);
    expect(spy).not.toHaveBeenCalled();
  });

  it("catches a matching event buried in a batched burst (fresh-slice)", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => {
        const { push } = usePush();
        useWsInvalidation([
          { types: new Set(["PipelineEnded"]), keys: [["stages"]] },
        ]);
        return { push };
      },
      { wrapper: makeWrapper(client) },
    );

    spy.mockClear();

    // A synchronous burst where the match is NOT the newest event — the retired
    // newest-only idiom would have dropped it.
    act(() => {
      result.current.push(["Noise", "PipelineEnded", "MoreNoise"]);
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: ["stages"] });
    });
  });

  it("applies independent rules independently", async () => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => {
        const { push } = usePush();
        useWsInvalidation([
          { types: new Set(["A"]), keys: [["ka"]] },
          { types: new Set(["B"]), keys: [["kb"]] },
        ]);
        return { push };
      },
      { wrapper: makeWrapper(client) },
    );

    spy.mockClear();

    act(() => {
      result.current.push("B");
    });

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: ["kb"] });
    });
    expect(spy).not.toHaveBeenCalledWith({ queryKey: ["ka"] });
  });
});
