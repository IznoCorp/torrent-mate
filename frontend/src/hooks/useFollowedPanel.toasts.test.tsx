/**
 * useFollowedPanel — X3 mutation-feedback tests.
 *
 * The unfollow / toggle / cadence mutations used to be fire-and-forget: a
 * failure snapped the UI back with no explanation and a success said nothing.
 * These tests pin the new contract: every outcome toasts in French, naming the
 * action (errors are owned by the useAcquisition hooks and carry the backend
 * detail — covered in ``useAcquisition.test.tsx``).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { type ReactElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { toastSuccess, toastError } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

import type { FollowedSeriesItem } from "@/api/acquisition";
import { useFollowedPanel } from "@/hooks/useFollowedPanel";

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

/**
 * Route the shared fetch mock: the hook's useSchedulers query needs a
 * schedulers-shaped body, every mutation call gets ``mutationBody``.
 */
function routeFetch(mutationStatus: number, mutationBody: unknown): void {
  fetchMock.mockImplementation((input) => {
    // The api client always calls fetch with a string URL.
    const url = typeof input === "string" ? input : "";
    return Promise.resolve(
      url.includes("/api/maintenance/schedulers")
        ? buildResponse(200, { schedulers: [] })
        : buildResponse(mutationStatus, mutationBody),
    );
  });
}

/** Fresh QueryClient wrapper (retries off) per test. */
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

beforeEach(() => {
  fetchMock.mockReset();
  toastSuccess.mockReset();
  toastError.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("useFollowedPanel — X3 success toasts", () => {
  it("toasts « Suivi retiré. » once the unfollow lands", async () => {
    routeFetch(204, null);

    const { result } = renderHook(() => useFollowedPanel(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.handleUnfollow(5);
    });

    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith("Suivi retiré.");
    });
  });

  it("toasts pause / réactivation when the toggle write lands", async () => {
    routeFetch(200, {});

    const { result } = renderHook(() => useFollowedPanel(), {
      wrapper: createWrapper(),
    });

    act(() => {
      result.current.handleToggleActive(5, false);
    });
    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith("Suivi mis en pause.");
    });

    act(() => {
      result.current.handleToggleActive(5, true);
    });
    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith("Suivi réactivé.");
    });
  });

  it("toasts « Cadence mise à jour. » and closes the dialog on save", async () => {
    routeFetch(200, {});

    const { result } = renderHook(() => useFollowedPanel(), {
      wrapper: createWrapper(),
    });

    const item = {
      id: 7,
      cadence: { interval_minutes: 60 },
    } as unknown as FollowedSeriesItem;

    act(() => {
      result.current.openEditCadence(item);
    });
    act(() => {
      result.current.handleSaveCadence();
    });

    await waitFor(() => {
      expect(toastSuccess).toHaveBeenCalledWith("Cadence mise à jour.");
    });
    expect(result.current.editTarget).toBeNull();
  });
});
