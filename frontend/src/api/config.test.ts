/**
 * Unit tests for the typed config-file helpers (R15).
 *
 * ``getConfigFile`` and ``putConfigFile`` route through apiFetch with a
 * schema-typed ``name`` path param (and, for the PUT, a JSON body). These tests
 * stub global fetch and assert the exact URL, method and body — a regression
 * here means the typed param plumbing broke.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getConfigFile, putConfigFile } from "./config";

/** Build a minimal successful JSON Response for the fetch stub. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("config apiFetch params (R15)", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("getConfigFile interpolates the name path param", async () => {
    await getConfigFile("paths.json5");
    const [url] = fetchSpy.mock.calls[0] as [string];
    expect(url).toBe("/api/config/files/paths.json5");
  });

  it("putConfigFile interpolates name and sends the PUT body", async () => {
    await putConfigFile("paths.json5", { values: {}, base_sha256: "aa" });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/config/files/paths.json5");
    expect(init.method).toBe("PUT");
    expect(init.body).toBe(JSON.stringify({ values: {}, base_sha256: "aa" }));
  });
});
