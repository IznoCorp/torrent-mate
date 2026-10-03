// Every refusal code the contract declares is said in the interface's own words (gap G-1):
// a code without words would fall back to a sentence that says less than the server knew.
import { describe, expect, it } from "vitest";
import contract from "../../../contract/openapi.json";
import FR from "../i18n/fr.json";

const CODES = (contract as unknown as { components: { schemas: { RefusalCode: { enum: string[] } } } })
  .components.schemas.RefusalCode.enum;

/** The words one code owns under `refusals`, or undefined. */
function wordsOf(code: string): unknown {
  return code.split(".").reduce<unknown>(
    (node, part) => (typeof node === "object" && node !== null ? (node as Record<string, unknown>)[part] : undefined),
    (FR as Record<string, unknown>).refusals,
  );
}

describe("every refusal code has its words", () => {
  it.each(CODES)("says %s from fr.json", (code) => {
    expect(typeof wordsOf(code)).toBe("string");
  });

  it("refuses both doors with one code, whatever the cause (O-K1-4 anti-enumeration)", () => {
    expect(CODES).toContain("auth.refused");
    expect(CODES).not.toContain("auth.invalid_credentials");
    expect(CODES).not.toContain("plex.no_server_access");
  });
});

type Operation = { operationId?: string; description?: string; responses: Record<string, { $ref?: string }> };
const SIGN_IN = Object.values((contract as unknown as { paths: Record<string, Record<string, Operation>> }).paths)
  .flatMap((methods) => Object.values(methods))
  .find((operation) => operation.operationId === "signIn") as Operation;

describe("signIn's refusals", () => {
  it("declares the cross-origin 403, whatever the credentials", () => {
    expect(SIGN_IN).toBeDefined();
    expect(SIGN_IN.responses["403"]).toEqual({ $ref: "#/components/responses/Problem" });
    expect(SIGN_IN.description).toContain("request.cross_origin");
  });

  it("reads, in its description, no auth code but auth.refused and auth.rate_limited", () => {
    expect(SIGN_IN).toBeDefined();
    const named = new Set(SIGN_IN.description?.match(/auth\.[a-z_]+/g));
    expect(named.has("auth.refused")).toBe(true);
    expect([...named].filter((code) => !["auth.refused", "auth.rate_limited"].includes(code))).toEqual([]);
  });
});
