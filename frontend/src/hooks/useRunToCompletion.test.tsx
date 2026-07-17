/**
 * Unit tests for {@link useRunToCompletion} — the shared launch-202 → poll →
 * terminal machine. Covers a 202 → poll → done cycle, a persistent-failure
 * cycle (SF1 stop-on-error guard), and unmount cleanup, plus the
 * {@link isTerminalRunOutcome} predicate. Uses a short real-timer poll interval
 * + ``waitFor`` so a resolved fetch propagates through to the settle effect.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { type ReactElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  isTerminalRunOutcome,
  useRunToCompletion,
} from "@/hooks/useRunToCompletion";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** A minimal run-detail-shaped payload the isTerminal predicate reads. */
interface RunLike {
  readonly outcome: string | null;
}

/** A short poll cadence so the tests run fast under real timers. */
const FAST_POLL_MS = 20;

/** Fresh QueryClient (retries disabled) per test so the cache starts clean. */
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

/** Sleep for *ms* using a real timer (to observe that a poll has stopped). */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// isTerminalRunOutcome
// ---------------------------------------------------------------------------

describe("isTerminalRunOutcome", () => {
  it("is true only for success / error / killed", () => {
    expect(isTerminalRunOutcome("success")).toBe(true);
    expect(isTerminalRunOutcome("error")).toBe(true);
    expect(isTerminalRunOutcome("killed")).toBe(true);
    expect(isTerminalRunOutcome("running")).toBe(false);
    expect(isTerminalRunOutcome(null)).toBe(false);
    expect(isTerminalRunOutcome(undefined)).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// useRunToCompletion
// ---------------------------------------------------------------------------

describe("useRunToCompletion", () => {
  it("polls until terminal, fires onTerminal once, then stops (202 → poll → done)", async () => {
    let calls = 0;
    const queryFn = vi.fn<() => Promise<RunLike>>(() => {
      calls += 1;
      return Promise.resolve(
        calls < 2 ? { outcome: null } : { outcome: "success" },
      );
    });
    const onTerminal = vi.fn<(data: RunLike) => void>();

    renderHook(
      () =>
        useRunToCompletion<RunLike>({
          queryKey: ["pipeline", "history", "run-done"],
          queryFn,
          isTerminal: (d) => isTerminalRunOutcome(d?.outcome),
          intervalMs: FAST_POLL_MS,
          onTerminal,
        }),
      { wrapper: createWrapper() },
    );

    // The running run is polled until a terminal outcome lands.
    await waitFor(() => {
      expect(onTerminal).toHaveBeenCalledTimes(1);
    });
    expect(onTerminal).toHaveBeenCalledWith({ outcome: "success" });
    expect(calls).toBeGreaterThanOrEqual(2);

    // Poll has stopped: no further fetches after the terminal outcome.
    const settledCalls = calls;
    await sleep(FAST_POLL_MS * 5);
    expect(calls).toBe(settledCalls);
    expect(onTerminal).toHaveBeenCalledTimes(1);
  });

  it("stops on a persistent error and fires onError once (SF1 guard)", async () => {
    const queryFn = vi.fn<() => Promise<RunLike>>(() =>
      Promise.reject(new Error("404 — run row never written")),
    );
    const onTerminal = vi.fn<(data: RunLike) => void>();
    const onError = vi.fn<() => void>();

    renderHook(
      () =>
        useRunToCompletion<RunLike>({
          queryKey: ["pipeline", "history", "run-err"],
          queryFn,
          isTerminal: (d) => isTerminalRunOutcome(d?.outcome),
          intervalMs: FAST_POLL_MS,
          retry: false,
          stopOnError: true,
          onTerminal,
          onError,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(onError).toHaveBeenCalledTimes(1);
    });
    expect(onTerminal).not.toHaveBeenCalled();

    // The poll halted on the settled error — no further fetches, single onError.
    const settledCalls = queryFn.mock.calls.length;
    await sleep(FAST_POLL_MS * 5);
    expect(queryFn.mock.calls.length).toBe(settledCalls);
    expect(onError).toHaveBeenCalledTimes(1);
  });

  it("stops polling after unmount (no fetch fires post-teardown)", async () => {
    const queryFn = vi.fn<() => Promise<RunLike>>(() =>
      Promise.resolve({ outcome: null }),
    );

    const { unmount } = renderHook(
      () =>
        useRunToCompletion<RunLike>({
          queryKey: ["pipeline", "history", "run-unmount"],
          queryFn,
          isTerminal: (d) => isTerminalRunOutcome(d?.outcome),
          intervalMs: FAST_POLL_MS,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(queryFn).toHaveBeenCalledTimes(1);
    });

    unmount();
    const settledCalls = queryFn.mock.calls.length;

    // Well past several poll intervals — the unmounted query must not refetch.
    await sleep(FAST_POLL_MS * 5);
    expect(queryFn.mock.calls.length).toBe(settledCalls);
  });
});
