/**
 * Unit tests for the typed maintenance action-run helper (R15).
 *
 * ``runMaintenanceAction`` routes through apiFetch with a schema-typed
 * ``action_id`` path param and the mutating ``X-Requested-With`` header. These
 * tests stub global fetch and assert the exact URL, method, headers and body —
 * a regression here means the typed param plumbing broke.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { runMaintenanceAction } from "./maintenance";

/** Build a minimal successful JSON Response for the fetch stub. */
function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("maintenance apiFetch params (R15)", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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

  it("non-OK responses still raise ApiError with the backend detail", async () => {
    fetchSpy.mockResolvedValue(jsonResponse({ detail: "Pipeline lock held" }, 409));
    await expect(
      runMaintenanceAction("library-gc", { options: {}, dry_run: false }),
    ).rejects.toThrow(ApiError);
  });
});
