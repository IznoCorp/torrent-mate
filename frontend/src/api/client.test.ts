/**
 * Unit tests for the fetch-core error normalisation (ApiError).
 *
 * The per-domain apiFetch param plumbing (URL interpolation, query
 * serialisation, mutating headers) is covered by the domain test files
 * (pipeline.test.ts, maintenance.test.ts, config.test.ts). This file keeps the
 * transport-agnostic ApiError behaviour that lives in client.ts.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  DEFAULT_TIMEOUT_MS,
  SLOW_PATH_TIMEOUT_MS,
  apiFetch,
  timeoutFor,
} from "./client";

describe("ApiError", () => {
  it("maps the staging read-only 403 to a friendly consultation message", () => {
    const readOnly = new ApiError(403, "read-only");
    expect(readOnly.isReadOnly).toBe(true);
    expect(readOnly.message).toContain("consultation");
    expect(readOnly.message).not.toContain("403");
    // A non-read-only error keeps the raw "status: detail" message.
    const other = new ApiError(409, "Pipeline lock held");
    expect(other.isReadOnly).toBe(false);
    expect(other.message).toBe("409: Pipeline lock held");
  });
});

describe("apiFetch — budget de requête", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("chaque requête part avec un signal qui EXPIRE", async () => {
    // `fetch` has no default timeout: a stalled socket (a phone waking from
    // background, a wifi handoff, a proxy gone quiet) hangs forever and every
    // waiter hangs with it — the pull-to-refresh spinner among them.
    let seen: RequestInit | undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        seen = init;
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { "content-type": "application/json" },
          }),
        );
      }),
    );

    await apiFetch("/api/version", { method: "get" });

    expect(seen?.signal).toBeInstanceOf(AbortSignal);
    expect(seen?.signal?.aborted).toBe(false);
  });

  it("une recherche live a un budget PLUS LARGE qu'une lecture locale", () => {
    // A tracker round-trip legitimately takes seconds; a local read does not.
    // Same rule for both: FINITE.
    expect(timeoutFor("/api/acquisition/followed")).toBe(DEFAULT_TIMEOUT_MS);
    expect(timeoutFor("/api/acquisition/search")).toBe(SLOW_PATH_TIMEOUT_MS);
    expect(timeoutFor("/api/maintenance/actions/{name}/run")).toBe(
      SLOW_PATH_TIMEOUT_MS,
    );
    // No path escapes with an unbounded budget.
    for (const p of [
      "/api/version",
      "/api/acquisition/wanted",
      "/api/pipeline/stages",
    ]) {
      expect(Number.isFinite(timeoutFor(p))).toBe(true);
      expect(timeoutFor(p)).toBeGreaterThan(0);
    }
  });
});
