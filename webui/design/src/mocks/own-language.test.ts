// An account's own language, as the layer holds it (the operator, 2026-10-03: FG-1 B — the
// language is the ACCOUNT's, the same on every device).
//
// WHAT MAKES THIS NON-VACUOUS. Each leg asks the route the interface asks and reads the account
// the layer answers next: the choice is the signed-in account's and no other's, it survives what a
// reload does to the layer (a fresh state over the same tab), a reset forgets it, a value outside
// the contract's `Language` is refused, and an account created in « Comptes » starts in the project's
// configured language (the operator, 2026-10-05).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { routes } from "./handlers";
import { resolve } from "./router";
import { resetMockState } from "./state";
import { forgetChosenLanguages, identityDials, signedIn } from "./identity";
import ACCOUNTS from "./seeds/accounts.json";

type Answer = { status?: number; coded?: { code: string }; language?: string; id?: string };

/**
 * Asks one route the way the interface does.
 *
 * @param method The method.
 * @param path The address, under the contract's base.
 * @param body What is sent.
 * @returns What the layer answered: the result, or its refusal.
 */
function ask(method: "PUT" | "POST", path: string, body: Record<string, unknown>): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route answers ${method} ${path}`);
  return found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(), body }) as Answer;
}

/** A tab's session storage, as the browser keeps it across a reload. */
function fakeStorage(): Storage {
  const held = new Map<string, string>();
  return {
    get length() { return held.size; },
    clear: () => held.clear(),
    getItem: (key) => held.get(key) ?? null,
    key: (index) => [...held.keys()][index] ?? null,
    removeItem: (key) => { held.delete(key); },
    setItem: (key, value) => { held.set(key, value); },
  };
}

describe("an account's own language", () => {
  beforeEach(() => {
    vi.stubGlobal("sessionStorage", fakeStorage());
    forgetChosenLanguages();
    resetMockState();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("is the seeded one at rest — French, as the household speaks it", () => {
    expect(signedIn().language).toBe("fr");
  });

  it("is set by the account itself, and answered back in the account", () => {
    const answer = ask("PUT", "/auth/language", { language: "en" });
    expect(answer.language).toBe("en");
    expect(signedIn().language).toBe("en");
  });

  it("is the account's own: another account signed in keeps its own", () => {
    ask("PUT", "/auth/language", { language: "en" });
    identityDials.setIdentity("household-member");
    expect(signedIn().language).toBe("fr");
  });

  it("outlives a reload of the page — a fresh layer over the same tab", () => {
    ask("PUT", "/auth/language", { language: "en" });
    resetMockState();
    expect(signedIn().language).toBe("en");
  });

  it("is forgotten by the layer's reset", () => {
    ask("PUT", "/auth/language", { language: "en" });
    forgetChosenLanguages();
    resetMockState();
    expect(signedIn().language).toBe("fr");
  });

  it.each(["de", "", "EN"])("refuses %j, which is no language the interface speaks", (language) => {
    const answer = ask("PUT", "/auth/language", { language });
    expect([answer.status, answer.coded?.code]).toEqual([400, "request.invalid"]);
    expect(signedIn().language).toBe("fr");
  });

  it("starts an account created in « Comptes » in the project's configured language, French here", () => {
    const created = ask("POST", "/accounts", { name: "Nina", email: "nina@example.invalid", role: "local-guest",
      password: "A provisional one 1!" });
    identityDials.setIdentity(created.id!);
    expect([ACCOUNTS.configuredLanguage, signedIn().language]).toEqual(["fr", "fr"]);
  });
});
