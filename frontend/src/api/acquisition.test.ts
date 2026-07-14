/**
 * Unit tests for the typed acquisition API client helpers (acq-watch feature).
 *
 * Stubs global fetch and asserts the exact URL, method, headers, and body
 * each helper produces against the regenerated schema.d.ts path keys and
 * param names.  Also covers error paths (404, 409).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createFollow,
  deleteFollow,
  getAcquisitionStatus,
  getFollowed,
  getObligations,
  getWanted,
  updateFollow,
} from "./acquisition";
import { ApiError } from "./client";

import type { FollowedResponse } from "./acquisition";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build a minimal successful JSON Response for the fetch stub. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

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
      status: "pending",
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
// getFollowed
// ---------------------------------------------------------------------------

describe("getFollowed", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(FOLLOWED));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serialises query params", async () => {
    await getFollowed({ active: "all" });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed?active=all");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
  });

  it("sends the bare path when no params are passed", async () => {
    await getFollowed();
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/acquisition/followed");
  });

  it("skips undefined query values", async () => {
    // With no explicit params, the URL should stay clean.
    await getFollowed({});
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/acquisition/followed");
  });
});

// ---------------------------------------------------------------------------
// getWanted
// ---------------------------------------------------------------------------

describe("getWanted", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(WANTED));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serialises query params (status, page, page_size)", async () => {
    await getWanted({ status: "pending", page: 2, page_size: 25 });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "/api/acquisition/wanted?status=pending&page=2&page_size=25",
    );
    expect(init.method).toBe("GET");
  });

  it("sends the bare path with default params", async () => {
    await getWanted();
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/acquisition/wanted");
  });
});

// ---------------------------------------------------------------------------
// getObligations
// ---------------------------------------------------------------------------

describe("getObligations", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(OBLIGATIONS));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serialises the status query param", async () => {
    await getObligations({ status: "breached" });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/obligations?status=breached");
    expect(init.method).toBe("GET");
  });

  it("sends the bare path when no params are passed", async () => {
    await getObligations();
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/acquisition/obligations");
  });
});

// ---------------------------------------------------------------------------
// getAcquisitionStatus
// ---------------------------------------------------------------------------

describe("getAcquisitionStatus", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(STATUS));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a bare GET with no params", async () => {
    await getAcquisitionStatus();
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/status");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
  });
});

// ---------------------------------------------------------------------------
// createFollow
// ---------------------------------------------------------------------------

describe("createFollow", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(FOLLOWED_ITEM, 201));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts with body serialised and XRW header", async () => {
    await createFollow({ tvdb_id: 123, title: "Test Show", kind: "show" });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(
      JSON.stringify({ tvdb_id: 123, title: "Test Show", kind: "show" }),
    );
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBe(
      "TorrentMate",
    );
  });

  it("omits undefined fields from body", async () => {
    await createFollow({ tvdb_id: 456, kind: "show" });
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(JSON.stringify({ tvdb_id: 456, kind: "show" }));
  });

  it("throws ApiError on 409 (already followed)", async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({ detail: "Already actively followed" }, 409),
    );
    await expect(
      createFollow({ tvdb_id: 123, kind: "show" }),
    ).rejects.toThrow(ApiError);
  });
});

// ---------------------------------------------------------------------------
// updateFollow
// ---------------------------------------------------------------------------

describe("updateFollow", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(FOLLOWED_ITEM));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("interpolates followed_id into path and sends body + XRW", async () => {
    await updateFollow(5, { active: false });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed/5");
    expect(init.method).toBe("PATCH");
    expect(init.body).toBe(JSON.stringify({ active: false }));
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBe(
      "TorrentMate",
    );
  });

  it("throws ApiError on 404", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));
    await expect(
      updateFollow(999, { active: true }),
    ).rejects.toThrow(ApiError);
  });
});

// ---------------------------------------------------------------------------
// deleteFollow
// ---------------------------------------------------------------------------

describe("deleteFollow", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends DELETE with followed_id in path and XRW header", async () => {
    await deleteFollow(5);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/acquisition/followed/5");
    expect(init.method).toBe("DELETE");
    expect((init.headers as Record<string, string>)["X-Requested-With"]).toBe(
      "TorrentMate",
    );
  });

  it("throws ApiError on 404", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));
    await expect(deleteFollow(999)).rejects.toThrow(ApiError);
  });
});
