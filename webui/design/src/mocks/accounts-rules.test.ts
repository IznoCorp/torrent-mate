// The accounts rules of 2026-10-04, as the layer answers them: a new account's
// role is required; the password policy holds on every door; an Admin never
// resets its own password; only the server's owner gives the Admin role.
//
// WHAT MAKES THIS NON-VACUOUS. Each leg asks the route the interface asks and
// reads the status and the code the layer answers — the very codes the server's
// tests read (`tests/http_v1/test_accounts_routes.py`).
import { beforeEach, describe, expect, it } from "vitest";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { identityDials } from "./identity";

type Answer = { status?: number; coded?: { code: string; params?: Record<string, unknown> }; role?: { kind: string }; ok?: boolean };

/**
 * Asks one route the way the interface does.
 *
 * @param method The method.
 * @param path The address, under the contract's base.
 * @param body What is sent.
 * @returns What the layer answered: the result, or its refusal.
 */
function ask(method: string, path: string, body: Record<string, unknown>): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route answers ${method} ${path}`);
  return found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body }) as Answer;
}

const STRONG = "A provisional one 1!";
const WEAK = "a provisional one";

/**
 * Puts a second account on the Admin role and signs it in: an Admin who is not the owner.
 *
 * @param id The account — local by default; a Plex-linked one proves the owner is told by
 *   its kind, never by having a Plex link at all.
 */
function asSecondAdmin(id = "local-account"): void {
  identityDials.setAccountRole(id, "admin");
  identityDials.setIdentity(id);
}

/** The two Admins who are not the owner: a local account, and a Plex-linked one (a shared user). */
const SECOND_ADMINS = [["local", "local-account"], ["plex-linked", "household-member"]] as const;

describe("a new account's role", () => {
  beforeEach(() => resetMockState());

  it("is required: absent, the request is invalid", () => {
    const answer = ask("POST", "/accounts", { name: "Nina", email: "nina@example.invalid", password: STRONG });
    expect([answer.status, answer.coded?.code]).toEqual([400, "request.invalid"]);
  });

  it("is checked before the e-mail: a body with neither answers request.invalid, as the server does", () => {
    const answer = ask("POST", "/accounts", { name: "Nina", password: STRONG });
    expect([answer.status, answer.coded?.code]).toEqual([400, "request.invalid"]);
  });

  it("is refused when it names no role", () => {
    const answer = ask("POST", "/accounts", { name: "Nina", email: "nina@example.invalid", role: "", password: STRONG });
    expect([answer.status, answer.coded?.code]).toEqual([404, "role.unknown"]);
  });
});

describe("the password policy, on every door", () => {
  beforeEach(() => resetMockState());

  it("refuses a weak provisional password at creation, naming the minimum", () => {
    const answer = ask("POST", "/accounts", { name: "Nina", email: "nina@example.invalid", role: "local-guest", password: WEAK });
    expect([answer.status, answer.coded?.code, answer.coded?.params]).toEqual([400, "password.too_weak", { minimum: 12 }]);
  });

  it("refuses a weak provisional password at a reset", () => {
    expect(ask("POST", "/accounts/local-account/password", { password: WEAK }).coded?.code).toBe("password.too_weak");
  });

  it("refuses a weak new password in Profil", () => {
    identityDials.setIdentity("local-account");
    const answer = ask("PUT", "/auth/password", { currentPassword: STRONG, newPassword: WEAK });
    expect([answer.status, answer.coded?.code]).toEqual([400, "password.too_weak"]);
  });
});

describe("an Admin's own password", () => {
  beforeEach(() => resetMockState());

  it("is never reset from « Comptes »: it changes in Profil, the current one required", () => {
    asSecondAdmin();
    const answer = ask("POST", "/accounts/local-account/password", { password: STRONG });
    expect([answer.status, answer.coded?.code]).toEqual([403, "password.reset_own"]);
  });

  it("is never reset by the owner either: its own account answers reset_own, before its kind's held_by_cli", () => {
    const answer = ask("POST", "/accounts/izno/password", { password: STRONG });
    expect([answer.status, answer.coded?.code]).toEqual([403, "password.reset_own"]);
  });

  it("is checked after the Admin check: a manager still reads reset_admin_only", () => {
    identityDials.setIdentity("household-member");
    expect(ask("POST", "/accounts/household-member/password", { password: STRONG }).coded?.code).toBe("password.reset_admin_only");
  });
});

describe("the Admin role", () => {
  beforeEach(() => resetMockState());

  it("is given by the owner", () => {
    expect(ask("PATCH", "/accounts/local-guest", { role: "admin" }).role?.kind).toBe("admin");
    const created = ask("POST", "/accounts", { name: "Nina", email: "nina@example.invalid", role: "admin", password: STRONG });
    expect(created.role?.kind).toBe("admin");
  });

  it.each(SECOND_ADMINS)("is refused to an Admin who is not the owner (%s), on an account's role and at creation", (_kind, id) => {
    asSecondAdmin(id);
    const promoted = ask("PATCH", "/accounts/local-guest", { role: "admin" });
    expect([promoted.status, promoted.coded?.code]).toEqual([403, "account.admin_owner_only"]);
    const created = ask("POST", "/accounts", { name: "Nina", email: "nina@example.invalid", role: "admin", password: STRONG });
    expect([created.status, created.coded?.code]).toEqual([403, "account.admin_owner_only"]);
  });

  it("never leaves the owner's account, whoever asks — the owner itself, checked before the last Admin", () => {
    const own = ask("PATCH", "/accounts/izno", { role: "household" });
    expect([own.status, own.coded?.code]).toEqual([403, "account.owner_admin"]);
    asSecondAdmin();
    const other = ask("PATCH", "/accounts/izno", { role: "household" });
    expect([other.status, other.coded?.code]).toEqual([403, "account.owner_admin"]);
    expect(ask("PATCH", "/accounts/izno", { role: "admin" }).role?.kind).toBe("admin");
  });

  it("keeps an Admin on Admin for an Admin who is not the owner: nothing is given", () => {
    asSecondAdmin();
    expect(ask("PATCH", "/accounts/local-account", { role: "admin" }).role?.kind).toBe("admin");
  });
});

describe("a role's name", () => {
  beforeEach(() => resetMockState());

  it("compares by Unicode lowercase, as the server does: « STRASSE » and « straße » are two names", () => {
    expect(ask("POST", "/roles", { name: "STRASSE", rights: [] }).status).toBeUndefined();
    expect(ask("POST", "/roles", { name: "straße", rights: [] }).status).toBeUndefined();
    const taken = ask("POST", "/roles", { name: "strasse", rights: [] });
    expect([taken.status, taken.coded?.code]).toEqual([409, "role.name_taken"]);
  });
});
