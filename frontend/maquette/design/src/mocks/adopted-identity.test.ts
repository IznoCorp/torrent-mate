// The mock identity follows the real signed-in account (the operator,
// 2026-10-04; Q5 = A).
//
// WHAT MAKES THIS NON-VACUOUS. The layer is installed over a recording network
// and asked the way the interface asks: an operation still mocked is judged by
// the mock's rights guard against the ADOPTED account — an Admin passes, an
// account without the right is refused 403 — and releasing the adoption puts
// the seed's owner back. On the design host the adoption is driven by what the
// real server answers: a sign-in adopts, a sign-out or any 401 releases.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "../contract/types";

type Account = components["schemas"]["Account"];

/** The real owner, as v1 answers him: an Admin the seed does not know. */
const OWNER: Account = {
  id: "real-owner", name: "owner", email: "owner@example.invalid",
  role: { id: "admin", name: "Admin", kind: "admin", rights: [] }, signInKind: "owner", forbiddenWrites: [],
};

/** An account the real server knows that holds no configuration right. */
const GUEST: Account = {
  ...OWNER, id: "real-guest", signInKind: "plex",
  role: { id: "plex-guest", name: "Guest", kind: "ordinary", rights: ["library.read"] },
};

// An operation v1 does not serve and only an Admin may ask (`configuration.view`).
const ADMIN_ONLY = "/api/v1/config/files";

let answers: Record<string, { status: number; body: unknown }>;

beforeEach(() => {
  vi.resetModules();
  answers = {};
  vi.stubGlobal("fetch", async (input: string) => {
    const found = answers[input] ?? { status: 599, body: {} };
    return new Response(JSON.stringify(found.body), { status: found.status });
  });
  vi.stubGlobal("window", {});
  vi.stubGlobal("location", { origin: "https://tm-design.invalid" });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/**
 * Installs the layer, and hands back the identity module it reads.
 *
 * @returns The identity module the installed layer answers from.
 */
async function layer(): Promise<typeof import("./identity")> {
  const { installMockNetwork } = await import("./index");
  installMockNetwork();
  return import("./identity");
}

/**
 * Asks one address through the installed layer.
 *
 * @param path The address.
 * @param method The method.
 * @returns The status answered.
 */
async function status(path: string, method = "GET"): Promise<number> {
  return (await globalThis.fetch(path, { method })).status;
}

describe("an adopted account", () => {
  it("is judged by the mock's rights guard: an Admin is answered", async () => {
    const identity = await layer();
    identity.adoptAccount(OWNER);
    expect(identity.signedInId()).toBe("real-owner");
    expect(await status(ADMIN_ONLY)).toBe(200);
  });

  it("is judged by the mock's rights guard: an account without the right is refused", async () => {
    const identity = await layer();
    identity.adoptAccount(GUEST);
    expect(identity.signedIn().id).toBe("real-guest");
    expect(await status(ADMIN_ONLY)).toBe(403);
  });

  it("released, gives the seed's owner back", async () => {
    const identity = await layer();
    identity.adoptAccount(GUEST);
    identity.adoptAccount(null);
    expect(identity.signedInId()).toBe("izno");
    expect(await status(ADMIN_ONLY)).toBe(200);
  });

  it("refuses the identity dial while it holds", async () => {
    const identity = await layer();
    identity.adoptAccount(OWNER);
    expect(() => identity.identityDials.setIdentity("household-member")).toThrow(
      "identity follows the signed-in account",
    );
  });
});

describe("on the design host, the real server's answers", () => {
  beforeEach(() => {
    vi.stubGlobal("__DESIGN_HOST__", true);
  });

  it("adopt the account a sign-in answers", async () => {
    answers["/api/v1/auth/login"] = { status: 200, body: GUEST };
    const identity = await layer();
    await status("/api/v1/auth/login", "POST");
    expect(identity.signedInId()).toBe("real-guest");
  });

  it("adopt the account the session reads", async () => {
    answers["/api/v1/auth/me"] = { status: 200, body: OWNER };
    const identity = await layer();
    await status("/api/v1/auth/me");
    expect(identity.signedInId()).toBe("real-owner");
  });

  it("release it on a sign-out", async () => {
    answers["/api/v1/auth/logout"] = { status: 200, body: { signedOut: true } };
    const identity = await layer();
    identity.adoptAccount(GUEST);
    await status("/api/v1/auth/logout", "POST");
    expect(identity.signedInId()).toBe("izno");
  });

  it("release it on any 401", async () => {
    answers["/api/v1/accounts"] = { status: 401, body: { code: "auth.required" } };
    const identity = await layer();
    identity.adoptAccount(GUEST);
    await status("/api/v1/accounts");
    expect(identity.signedInId()).toBe("izno");
  });
});
