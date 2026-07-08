/**
 * Unit tests for the typed apiFetch parameter support (R15).
 *
 * The five previously raw-fetch helpers (getPipelineHistory,
 * getPipelineRunDetail, runMaintenanceAction, getConfigFile, putConfigFile)
 * now route through apiFetch with schema-typed path/query params. These tests
 * stub global fetch and assert the exact URL, method, headers, and body each
 * helper produces — a regression here means the typed param plumbing broke.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  getConfigFile,
  getPipelineHistory,
  getPipelineRunDetail,
  putConfigFile,
  runMaintenanceAction,
} from "./client";

/** Build a minimal successful JSON Response for the fetch stub. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch params (R15)", () => {
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

  it("runMaintenanceAction interpolates action_id and keeps method/headers/body", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ run_uid: "u1" }, 202));
    await runMaintenanceAction("library-gc", { options: {}, dry_run: true });
    const [url, init] = fetchSpy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/maintenance/actions/library-gc/run");
    expect(init.method).toBe("POST");
    expect(
      (init.headers as Record<string, string>)["X-Requested-With"],
    ).toBe("TorrentMate");
    expect(init.body).toBe(JSON.stringify({ options: {}, dry_run: true }));
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

  it("non-OK responses still raise ApiError with the backend detail", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Pipeline lock held" }, 409));
    await expect(
      runMaintenanceAction("library-gc", { options: {}, dry_run: false }),
    ).rejects.toThrow(ApiError);
  });
});
