import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useContinueMedia } from "@/hooks/useContinueMedia";

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

const MOCK_CONTINUE_RESPONSE = {
  ok: true,
  media_id: "abc123",
  run_uid: "run-001",
  deferred: false,
  detail: "Pipeline relancé",
};

const fetchMock = vi.fn<typeof fetch>();

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

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
// Tests
// ---------------------------------------------------------------------------

describe("useContinueMedia", () => {
  it("calls continueMedia and resolves on 200", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, MOCK_CONTINUE_RESPONSE));

    const { result } = renderHook(() => useContinueMedia(), {
      wrapper: createWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync("abc123");
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(MOCK_CONTINUE_RESPONSE);
  });

  it("surfaces ApiError on non-OK response", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(422, { detail: "Media is not yet identified" }),
    );

    const { result } = renderHook(() => useContinueMedia(), {
      wrapper: createWrapper(),
    });

    // Use mutate (not mutateAsync) so the error lands on the mutation state.
    result.current.mutate("abc123");

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});
