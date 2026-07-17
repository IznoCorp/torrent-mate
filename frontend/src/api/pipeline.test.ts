/**
 * Unit tests for the typed pipeline-history helpers (R15).
 *
 * ``getPipelineHistory`` and ``getPipelineRunDetail`` route through apiFetch
 * with schema-typed path/query params. These tests stub global fetch and assert
 * the exact URL and method each helper produces — a regression here means the
 * typed param plumbing broke.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getPipelineHistory, getPipelineRunDetail } from "./pipeline";

/** Build a minimal successful JSON Response for the fetch stub. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("pipeline apiFetch params (R15)", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getPipelineHistory serialises query params and skips undefined", async () => {
    await getPipelineHistory({ limit: 5, kind: "maintenance" });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/pipeline/history?limit=5&kind=maintenance");
    expect(init.method).toBe("GET");
    expect(init.credentials).toBe("include");
  });

  it("getPipelineHistory with no params sends the bare path", async () => {
    await getPipelineHistory();
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/pipeline/history");
  });

  it("getPipelineRunDetail interpolates and URI-encodes the path param", async () => {
    await getPipelineRunDetail("abc/../x");
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/pipeline/history/abc%2F..%2Fx");
  });
});
