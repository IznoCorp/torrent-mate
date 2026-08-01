/**
 * Unit tests for the acquisition TanStack Query hooks (acq-watch feature).
 *
 * Mocks fetch and asserts query keys, success responses, mutation
 * invalidation behaviour, and error surfaces (401, 404, 409 as
 * :class:`ApiError`).  Follows the wrapper pattern established by
 * ``useDecisions.test.tsx``.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, renderHook, waitFor } from "@testing-library/react";
import { type ReactElement, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// X3: every acquisition mutation toasts its failure — spy on sonner.
const { toastSuccess, toastError, toastInfo } = vi.hoisted(() => ({
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  toastInfo: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    success: toastSuccess,
    error: toastError,
    warning: vi.fn(),
    info: toastInfo,
  },
}));

import {
  useAcquisitionStatus,
  useFollow,
  useFollowed,
  useObligations,
  useUnfollow,
  useUpdateFollow,
  useWanted,
} from "@/hooks/useAcquisition";
import { acqKeys } from "@/api/acquisition";
import { ApiError } from "@/api/client";

import type { FollowedResponse } from "@/api/acquisition";

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

/** A minimal FollowedResponse-shaped payload. */
const FOLLOWED: FollowedResponse = {
  items: [
    {
      id: 1,
      title: "Test Show",
      active: true,
      added_at: 1_750_000_000,
      wanted_pending: 3,
      wanted_grabbed: 0,
      kind: "show",
      status: "a_recuperer",
      priming_running: false,
      tvdb_unresolved: false,
      media_ref: {
        tvdb_id: 123,
        tmdb_id: null,
        imdb_id: null,
      },
      cadence: null,
      quality_profile: null,
    },
  ],
};

/** A minimal paginated wanted response. */
const WANTED = {
  items: [
    {
      id: 1,
      title: "Test Show",
      kind: "tv",
      season: 1,
      episode: 2,
      status: "pending",
      attempts: 0,
      enqueued_at: 1_750_000_000,
      last_search_at: null,
    },
  ],
  total: 1,
  page: 1,
  page_size: 50,
};

/** A minimal obligations response. */
const OBLIGATIONS = {
  items: [
    {
      info_hash: "abc123def456",
      source_tracker: "lacale",
      min_ratio: 1.0,
      min_seed_time_s: 86400,
      added_at: 1_750_000_000,
      observed_ratio: null,
      accumulated_seed_time_s: null,
      dispatched_path: null,
      released_at: null,
      satisfied_at: null,
      breached_at: null,
      hnr_count: null,
    },
  ],
};

/** A minimal acquisition status response. */
const STATUS = {
  watcher_enabled: true,
  last_successful_run_at: 1_750_000_000,
  recent_runs: [],
};

/** A minimal FollowedSeriesItem for create/update responses. */
const FOLLOWED_ITEM = FOLLOWED.items[0];

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
  toastSuccess.mockReset();
  toastError.mockReset();
  toastInfo.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

// ---------------------------------------------------------------------------
// Tests — query keys
// ---------------------------------------------------------------------------

describe("acqKeys", () => {
  it("all returns ['acquisition']", () => {
    expect(acqKeys.all).toEqual(["acquisition"]);
  });

  it("followed() wraps active param", () => {
    expect(acqKeys.followed({ active: "all" })).toEqual([
      "acquisition",
      "followed",
      { active: "all" },
    ]);
  });

  it("followed() defaults to empty params", () => {
    expect(acqKeys.followed()).toEqual(["acquisition", "followed", {}]);
  });

  it("wanted() wraps status/page/page_size params", () => {
    expect(
      acqKeys.wanted({ status: "pending", page: 2, page_size: 25 }),
    ).toEqual([
      "acquisition",
      "wanted",
      { status: "pending", page: 2, page_size: 25 },
    ]);
  });

  it("obligations() wraps status param", () => {
    expect(acqKeys.obligations({ status: "breached" })).toEqual([
      "acquisition",
      "obligations",
      { status: "breached" },
    ]);
  });

  it("status() returns ['acquisition', 'status']", () => {
    expect(acqKeys.status()).toEqual(["acquisition", "status"]);
  });
});

// ---------------------------------------------------------------------------
// Tests — useFollowed
// ---------------------------------------------------------------------------

describe("useFollowed", () => {
  it("returns the followed list on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, FOLLOWED));

    const { result } = renderHook(() => useFollowed(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(FOLLOWED);
  });

  it("forwards ApiError on failure", async () => {
    fetchMock.mockResolvedValue(buildResponse(401, { detail: "Unauthorized" }));

    const { result } = renderHook(() => useFollowed(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeInstanceOf(ApiError);
  });

  it("passes active param through to the fetch URL", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, FOLLOWED));

    const { result } = renderHook(() => useFollowed({ active: "inactive" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("active=inactive");
  });
});

// ---------------------------------------------------------------------------
// Tests — useWanted
// ---------------------------------------------------------------------------

describe("useWanted", () => {
  it("returns the wanted list on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, WANTED));

    const { result } = renderHook(() => useWanted({ status: "pending" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(WANTED);
  });

  it("passes query params through to the fetch URL", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, WANTED));

    renderHook(() => useWanted({ status: "pending", page: 2, page_size: 10 }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("status=pending");
    expect(url).toContain("page=2");
    expect(url).toContain("page_size=10");
  });
});

// ---------------------------------------------------------------------------
// Tests — useObligations
// ---------------------------------------------------------------------------

describe("useObligations", () => {
  it("returns the obligations list on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, OBLIGATIONS));

    const { result } = renderHook(() => useObligations(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(OBLIGATIONS);
  });

  it("passes status param through to the fetch URL", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, OBLIGATIONS));

    renderHook(() => useObligations({ status: "breached" }), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("status=breached");
  });
});

// ---------------------------------------------------------------------------
// Tests — useAcquisitionStatus
// ---------------------------------------------------------------------------

describe("useAcquisitionStatus", () => {
  it("returns the status on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, STATUS));

    const { result } = renderHook(() => useAcquisitionStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toEqual(STATUS);
  });

  it("sends a bare GET with no query params", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, STATUS));

    renderHook(() => useAcquisitionStatus(), {
      wrapper: createWrapper(),
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("/api/acquisition/status");
  });
});

// ---------------------------------------------------------------------------
// Tests — useFollow (mutation)
// ---------------------------------------------------------------------------

describe("useFollow", () => {
  it("calls createFollow with the body and invalidates on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(201, FOLLOWED_ITEM));

    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    const wrapper = ({ children }: { children: ReactNode }): ReactElement => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useFollow(), { wrapper });

    await result.current.mutateAsync({
      tvdb_id: 123,
      title: "Test Show",
      kind: "show",
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({ tvdb_id: 123, title: "Test Show", kind: "show" }),
    );

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: acqKeys.all });
    invalidateSpy.mockRestore();
  });

  it("surfaces ApiError on 409 conflict", async () => {
    fetchMock.mockResolvedValue(
      buildResponse(409, { detail: "Already actively followed" }),
    );

    const { result } = renderHook(() => useFollow(), {
      wrapper: createWrapper(),
    });

    await expect(
      result.current.mutateAsync({ tvdb_id: 123, kind: "show" }),
    ).rejects.toThrow(ApiError);
  });

  it("toasts the failure with the backend detail (X3)", async () => {
    // A non-409 failure keeps the error path — the 409 duplicate has its own
    // informational path (NE-DOIT-PAS-3, next test).
    fetchMock.mockResolvedValue(
      buildResponse(422, { detail: "Invalid follow body" }),
    );

    const { result } = renderHook(() => useFollow(), {
      wrapper: createWrapper(),
    });

    await expect(
      result.current.mutateAsync({ tvdb_id: 123, kind: "show" }),
    ).rejects.toThrow(ApiError);

    expect(toastError).toHaveBeenCalledWith(
      "Échec de l'ajout au suivi — Invalid follow body",
    );
    expect(toastInfo).not.toHaveBeenCalled();
  });

  it("toasts the 409 duplicate-follow as information, never as an error (NE-DOIT-PAS-3)", async () => {
    // The duplicate of the SAME action is the one legitimate refusal: it is
    // an information, not a failure — mirrors useFollowedPanel's 409 rule.
    fetchMock.mockResolvedValue(
      buildResponse(409, { detail: "Already actively followed" }),
    );

    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    const wrapper = ({ children }: { children: ReactNode }): ReactElement => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useFollow(), { wrapper });

    await expect(
      result.current.mutateAsync({ tvdb_id: 123, kind: "show" }),
    ).rejects.toThrow(ApiError);

    expect(toastInfo).toHaveBeenCalledWith(
      "Déjà suivi — ce média est déjà dans les suivis.",
    );
    expect(toastError).not.toHaveBeenCalled();
    // The 409 proves the follow already exists — the stale local cache must
    // resync exactly as a success would.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: acqKeys.all });
    invalidateSpy.mockRestore();
  });
});

// ---------------------------------------------------------------------------
// Tests — useUnfollow (mutation)
// ---------------------------------------------------------------------------

describe("useUnfollow", () => {
  it("calls deleteFollow with the id and invalidates on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(204, null));

    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    const wrapper = ({ children }: { children: ReactNode }): ReactElement => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUnfollow(), { wrapper });

    await result.current.mutateAsync(5);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed/5");
    expect(init.method).toBe("DELETE");

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: acqKeys.all });
    invalidateSpy.mockRestore();
  });

  it("surfaces ApiError on 404", async () => {
    fetchMock.mockResolvedValue(buildResponse(404, { detail: "Not found" }));

    const { result } = renderHook(() => useUnfollow(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync(999)).rejects.toThrow(ApiError);
  });

  it("toasts the failure with the backend detail (X3)", async () => {
    fetchMock.mockResolvedValue(buildResponse(404, { detail: "Not found" }));

    const { result } = renderHook(() => useUnfollow(), {
      wrapper: createWrapper(),
    });

    await expect(result.current.mutateAsync(999)).rejects.toThrow(ApiError);

    expect(toastError).toHaveBeenCalledWith(
      "Échec du retrait du suivi — Not found",
    );
  });
});

// ---------------------------------------------------------------------------
// Tests — useUpdateFollow (mutation)
// ---------------------------------------------------------------------------

describe("useUpdateFollow", () => {
  it("calls updateFollow with id + body and invalidates on success", async () => {
    fetchMock.mockResolvedValue(buildResponse(200, FOLLOWED_ITEM));

    const qc = new QueryClient({
      defaultOptions: { mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");

    const wrapper = ({ children }: { children: ReactNode }): ReactElement => (
      <QueryClientProvider client={qc}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useUpdateFollow(), { wrapper });

    await result.current.mutateAsync({ id: 5, body: { active: false } });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed/5");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ active: false }));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: acqKeys.all });
    invalidateSpy.mockRestore();
  });

  it("surfaces ApiError on 404", async () => {
    fetchMock.mockResolvedValue(buildResponse(404, { detail: "Not found" }));

    const { result } = renderHook(() => useUpdateFollow(), {
      wrapper: createWrapper(),
    });

    await expect(
      result.current.mutateAsync({ id: 999, body: { active: true } }),
    ).rejects.toThrow(ApiError);
  });

  it("toasts the failure with the backend detail (X3)", async () => {
    fetchMock.mockResolvedValue(buildResponse(404, { detail: "Not found" }));

    const { result } = renderHook(() => useUpdateFollow(), {
      wrapper: createWrapper(),
    });

    await expect(
      result.current.mutateAsync({ id: 999, body: { active: true } }),
    ).rejects.toThrow(ApiError);

    expect(toastError).toHaveBeenCalledWith(
      "Échec de la mise à jour du suivi — Not found",
    );
  });
});
