// A local account's PROVISIONAL password, as the layer judges it (the operator,
// 2026-10-03: « A » — the Admin sets it at creation in « Comptes » and may reset
// it; the account then changes it in Profil).
//
// WHAT MAKES THIS NON-VACUOUS. Each leg asks the route the interface asks, as the
// owner (Admin), and reads the status and the code the layer answers: a local
// account created without one is refused, a linked e-mail is created without
// one, and a reset is refused by the account's kind — never the owner's
// fallback password, never a Plex-linked account's.
import { beforeEach, describe, expect, it } from "vitest";
import ACCOUNTS from "./seeds/accounts.json";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { identityDials } from "./identity";

type Answer = { status?: number; coded?: { code: string; params?: Record<string, unknown> }; signInKind?: string; ok?: boolean };

/**
 * Asks one route the way the interface does.
 *
 * @param path The address, under the contract's base.
 * @param body What is sent.
 * @returns What the layer answered: the result, or its refusal.
 */
function post(path: string, body: Record<string, unknown>): Answer {
  const found = resolve(routes(), "POST", path);
  if (found === null) throw new Error(`no route answers POST ${path}`);
  return found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body }) as Answer;
}

const LONG = "A provisional one 1";

describe("a local account's provisional password", () => {
  beforeEach(() => resetMockState());

  it("is required when a local account is created", () => {
    const answer = post("/accounts", { name: "Nina", email: "nina@example.invalid", role: "local-guest" });
    expect([answer.status, answer.coded?.code]).toEqual([400, "password.required"]);
  });

  it("is refused shorter than the minimum, which the refusal names", () => {
    const answer = post("/accounts", { name: "Nina", email: "nina@example.invalid", role: "local-guest", password: "court" }); // french-ok: a typed password
    expect([answer.status, answer.coded?.code]).toEqual([400, "password.too_short"]);
    expect(answer.coded?.params).toEqual({ minimum: ACCOUNTS.passwordMinimum });
  });

  it("creates a local account when given", () => {
    const answer = post("/accounts", { name: "Nina", email: "nina@example.invalid", role: "local-guest", password: LONG });
    expect(answer.signInKind).toBe("local");
  });

  it("is not asked of an e-mail the server links to Plex", () => {
    const answer = post("/accounts", { name: "Maya", email: ACCOUNTS.plexUsers[0], role: "local-guest" });
    expect(answer.signInKind).toBe("plex");
  });
});

describe("a provisional password reset", () => {
  beforeEach(() => resetMockState());

  it("is set on a local account", () => {
    expect(post("/accounts/local-account/password", { password: LONG }).ok).toBe(true);
  });

  it("is refused short, empty, or for an account nobody holds", () => {
    expect(post("/accounts/local-account/password", { password: "court" }).coded?.code).toBe("password.too_short"); // french-ok: a typed password
    expect(post("/accounts/local-account/password", { password: "" }).coded?.code).toBe("password.required");
    expect(post("/accounts/nobody/password", { password: LONG }).status).toBe(404);
  });

  it("refuses a caller who is not Admin first, before the account is looked up (OPEN-3 B)", () => {
    identityDials.setIdentity("household-member");
    const unknown = post("/accounts/nobody/password", { password: LONG });
    expect([unknown.status, unknown.coded?.code]).toEqual([403, "password.reset_admin_only"]);
  });

  it("never touches the owner's fallback password, nor a Plex-linked account", () => {
    // ASKED BY A SECOND ADMIN: the owner naming its own account is refused
    // earlier, `password.reset_own` (`accounts-rules.test.ts`).
    identityDials.setAccountRole("local-account", "admin");
    identityDials.setIdentity("local-account");
    const owner = post("/accounts/izno/password", { password: LONG });
    expect([owner.status, owner.coded?.code]).toEqual([403, "password.held_by_cli"]);
    const linked = post("/accounts/household-member/password", { password: LONG });
    expect([linked.status, linked.coded?.code]).toEqual([403, "auth.plex_only"]);
  });
});
