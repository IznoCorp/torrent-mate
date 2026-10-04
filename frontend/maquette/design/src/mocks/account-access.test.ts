// An account's access, as the layer judges it (the operator, 2026-10-04: an Admin
// cuts an account's access with a switch, ON by default — Q4 = A, Q5 = A).
//
// WHAT MAKES THIS NON-VACUOUS. Each leg asks the route the interface asks and
// reads the status and the code the layer answers: the Admin check comes first,
// the owner and the caller's own account are refused, a cut ends every session
// of the account at once, and its next sign-in — by password or by Plex — is
// refused once its credentials are proven, until the switch is back on.
import { beforeEach, describe, expect, it } from "vitest";
import ACCOUNT from "./seeds/account.json";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { identityDials, sessionEnded } from "./identity";

type Answer = {
  status?: number;
  coded?: { code: string };
  id?: string;
  signInAllowed?: boolean;
  accounts?: { id: string; signInAllowed: boolean }[];
};

/**
 * Asks one route the way the interface does.
 *
 * @param method The method.
 * @param path The address, under the contract's base.
 * @param body What is sent.
 * @returns What the layer answered: the result, or its refusal.
 */
function ask(method: string, path: string, body?: Record<string, unknown>): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route answers ${method} ${path}`);
  return found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body }) as Answer;
}

const CUT = { signInAllowed: false };
const LOCAL = { id: "local-account", email: "jules@example.invalid" };
const LINKED = "household-member";

describe("the roster says every account's access", () => {
  beforeEach(() => resetMockState());

  it("is allowed by default", () => {
    const roster = ask("GET", "/accounts");
    expect(roster.accounts?.every((one) => one.signInAllowed)).toBe(true);
  });
});

describe("setAccountAccess", () => {
  beforeEach(() => resetMockState());

  it("cuts an account, and the roster says so", () => {
    const answer = ask("PUT", `/accounts/${LINKED}/access`, CUT);
    expect([answer.id, answer.signInAllowed]).toEqual([LINKED, false]);
    expect(ask("GET", "/accounts").accounts?.find((one) => one.id === LINKED)?.signInAllowed).toBe(false);
  });

  it("refuses a caller who is not Admin first, before the account is looked up", () => {
    identityDials.setIdentity(LINKED);
    for (const target of [LOCAL.id, "nobody"]) {
      const answer = ask("PUT", `/accounts/${target}/access`, CUT);
      expect([answer.status, answer.coded?.code]).toEqual([403, "account.access_admin_only"]);
    }
  });

  it("answers an unknown account 404 to an Admin", () => {
    expect(ask("PUT", "/accounts/nobody/access", CUT).coded?.code).toBe("account.unknown");
  });

  it("never cuts the owner, nor the acting Admin's own account", () => {
    const owner = ask("PUT", `/accounts/${ACCOUNT.id}/access`, CUT);
    expect([owner.status, owner.coded?.code]).toEqual([403, "account.owner_access"]);
    identityDials.setAccountRole(LOCAL.id, "admin");
    identityDials.setIdentity(LOCAL.id);
    const own = ask("PUT", `/accounts/${LOCAL.id}/access`, CUT);
    expect([own.status, own.coded?.code]).toEqual([403, "account.own_access"]);
  });

  it("refuses a body that does not say the access", () => {
    expect(ask("PUT", `/accounts/${LINKED}/access`, {}).status).toBe(400);
  });
});

describe("a cut account", () => {
  beforeEach(() => resetMockState());

  it("has every session ended at once", () => {
    ask("PUT", `/accounts/${LOCAL.id}/access`, CUT);
    identityDials.setIdentity(LOCAL.id);
    expect(sessionEnded()).toBe(true);
  });

  it("is refused its password sign-in once the credentials are proven", () => {
    ask("PUT", `/accounts/${LOCAL.id}/access`, CUT);
    const answer = ask("POST", "/auth/login", { email: LOCAL.email, password: "a password" });
    expect([answer.status, answer.coded?.code]).toEqual([403, "auth.access_disabled"]);
  });

  it("keeps the one anti-enumeration refusal for a Plex-linked account's password", () => {
    ask("PUT", `/accounts/${LINKED}/access`, CUT);
    const answer = ask("POST", "/auth/login", { email: "lea@example.invalid", password: "a password" });
    expect([answer.status, answer.coded?.code]).toEqual([401, "auth.refused"]);
  });

  it("tells nothing to an unknown e-mail while the account dialled is cut", () => {
    ask("PUT", `/accounts/${LOCAL.id}/access`, CUT);
    identityDials.setIdentity(LOCAL.id);
    const answer = ask("POST", "/auth/login", { email: "nobody@example.invalid", password: "a password" });
    expect([answer.status, answer.coded?.code]).toEqual([401, "auth.refused"]);
  });

  it("is refused its Plex sign-in", () => {
    ask("PUT", `/accounts/${LINKED}/access`, CUT);
    identityDials.setIdentity(LINKED);
    const answer = ask("POST", "/auth/plex", { pinId: 1 });
    expect([answer.status, answer.coded?.code]).toEqual([403, "auth.access_disabled"]);
  });

  it("signs in again once the switch is back on, and its session is open", () => {
    ask("PUT", `/accounts/${LOCAL.id}/access`, CUT);
    ask("PUT", `/accounts/${LOCAL.id}/access`, { signInAllowed: true });
    identityDials.setIdentity(LOCAL.id);
    // TURNED BACK ON, THE OLD SESSIONS STAY ENDED: only a sign-in opens one.
    expect(sessionEnded()).toBe(true);
    expect(ask("POST", "/auth/login", { email: LOCAL.email, password: "a password" }).id).toBe(LOCAL.id);
    expect(sessionEnded()).toBe(false);
  });
});
