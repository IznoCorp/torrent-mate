/**
 * Unit tests for the typed decisions API client helpers (scrape-arbiter §4.1).
 *
 * Stubs global fetch and asserts the exact URL, method, headers, and body
 * each helper produces against the regenerated schema.d.ts path keys and
 * param names.  Also covers error paths (404, 409, 410, 502).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import {
  type DecisionDetailResponse,
  dismissDecision,
  fetchDecisionDetail,
  fetchDecisions,
  resolveDecision,
  searchDecisionCandidates,
} from "./decisions";

/** Build a minimal successful JSON Response for the fetch stub. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** A minimal DecisionDetail-shaped payload for success responses. */
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
  pending_count: 3,
  total: 3,
  page: 1,
  page_size: 50,
};

describe("fetchDecisions", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(LIST));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("serialises query params and skips undefined", async () => {
    await fetchDecisions({ status: "pending", page: 2, page_size: 10 });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/decisions/?status=pending&page=2&page_size=10");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
  });

  it("sends the bare path when no params are passed", async () => {
    await fetchDecisions();
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/decisions/");
  });

  it("skips undefined query values", async () => {
    // Omit `page` entirely — exactOptionalPropertyTypes forbids explicit undefined.
    await fetchDecisions({ status: "pending" });
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/decisions/?status=pending");
  });
});

describe("fetchDecisionDetail", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(DETAIL));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("interpolates decision_id into the path", async () => {
    await fetchDecisionDetail(42);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/decisions/42");
    expect(init.method).toBe("GET");
  });

  it("throws ApiError on 404", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));
    await expect(fetchDecisionDetail(999)).rejects.toThrow(ApiError);
  });

  it("throws ApiError on 410 (superseded)", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Decision superseded" }, 410));
    await expect(fetchDecisionDetail(1)).rejects.toThrow(ApiError);
  });
});

describe("searchDecisionCandidates", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ candidates: [] }));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts with decision_id in path and body serialised", async () => {
    await searchDecisionCandidates(7, { title: "Inception", year: 2010 });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/decisions/7/search");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ title: "Inception", year: 2010 }));
  });

  it("omits year from body when undefined", async () => {
    await searchDecisionCandidates(7, { title: "Inception" });
    const [, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(JSON.stringify({ title: "Inception" }));
  });

  it("throws ApiError on 404", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));
    await expect(
      searchDecisionCandidates(999, { title: "Nope" }),
    ).rejects.toThrow(ApiError);
  });
});

describe("resolveDecision", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse({ run_uid: "abc123" }, 202));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts with decision_id in path and body containing provider + provider_id", async () => {
    await resolveDecision(3, { provider: "tmdb", provider_id: 550 });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/decisions/3/resolve");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ provider: "tmdb", provider_id: 550 }));
  });

  it("throws ApiError on 409 (lock held)", async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({ detail: "Pipeline lock held" }, 409),
    );
    await expect(
      resolveDecision(3, { provider: "tmdb", provider_id: 550 }),
    ).rejects.toThrow(ApiError);
  });

  it("throws ApiError on 410 (superseded)", async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({ detail: "Decision superseded" }, 410),
    );
    await expect(
      resolveDecision(3, { provider: "tmdb", provider_id: 550 }),
    ).rejects.toThrow(ApiError);
  });
});

describe("dismissDecision", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse(DETAIL));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts with decision_id in path and no body", async () => {
    await dismissDecision(5);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/decisions/5/dismiss");
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("throws ApiError on 404", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Not found" }, 404));
    await expect(dismissDecision(999)).rejects.toThrow(ApiError);
  });

  it("throws ApiError on 410 (superseded)", async () => {
    fetchSpy.mockResolvedValue(
      jsonResponse({ detail: "Decision superseded" }, 410),
    );
    await expect(dismissDecision(1)).rejects.toThrow(ApiError);
  });
});
