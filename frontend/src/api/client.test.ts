/**
 * Unit tests for the fetch-core error normalisation (ApiError).
 *
 * The per-domain apiFetch param plumbing (URL interpolation, query
 * serialisation, mutating headers) is covered by the domain test files
 * (pipeline.test.ts, maintenance.test.ts, config.test.ts). This file keeps the
 * transport-agnostic ApiError behaviour that lives in client.ts.
 */

import { describe, expect, it } from "vitest";

import { ApiError } from "./client";

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
