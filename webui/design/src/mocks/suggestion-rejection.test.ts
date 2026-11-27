// A rejection is the rejecting account's alone (O-9 A, K3-G7), and the layer answers it as a server.
//
// WHAT MAKES THIS NON-VACUOUS. The deck is read as two accounts: what one rejects leaves its deck
// and stays in the other's, a page past the rejection is still full, and the cursor it hands back
// still continues the deck without showing a card twice or losing one.
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import SUGGESTIONS from "./seeds/suggestions.json";
import { routes } from "./handlers";
import { resolve, settled } from "./router";
import { adoptAccount } from "./identity";
import { resetMockState } from "./state";
import type { components } from "../contract/types";

type Account = components["schemas"]["Account"];
type Answer = { status: number; payload: any };

const OTHER: Account = {
  id: "other-account",
  name: "other",
  email: "other@example.invalid",
  role: { id: "household", name: "Household", kind: "ordinary", rights: ["acquisition.request"] },
  signInKind: "plex",
  language: "fr",
  forbiddenWrites: [],
};

/** Calls one operation as the interface would. */
function call(method: string, path: string, query: Record<string, string> = {}): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route ${method} ${path}`);
  const answer = found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(query), body: undefined });
  return settled(200, answer as never) as Answer;
}

const DECK = "/acquisition/suggestions";
const rejection = (id: string) => `${DECK}/${encodeURIComponent(id)}/rejection`;
const ids = (answer: Answer): string[] => answer.payload.suggestions.map((one: { id: string }) => one.id);

/** Every id the signed-in account's deck answers, page after page. */
function wholeDeck(): string[] {
  const seen: string[] = [];
  let cursor: string | null = null;
  do {
    const query: Record<string, string> = cursor === null ? {} : { cursor };
    const answer = call("GET", DECK, query);
    seen.push(...ids(answer));
    cursor = answer.payload.nextCursor;
  } while (cursor !== null && seen.length <= SUGGESTIONS.length);
  return seen;
}

const SEEDED = SUGGESTIONS.map((one) => one.id);
const FIRST = SEEDED[0];

beforeEach(() => resetMockState());
afterEach(() => adoptAccount(null));

describe("rejecting a suggestion", () => {
  it("gives every seeded card its own handle", () => {
    expect(new Set(SEEDED).size).toBe(SEEDED.length);
    for (const id of SEEDED) expect(id).toMatch(/^(movie|show):[^:]+:.+$/);
  });

  it("takes the card out of the rejecting account's deck and no other's", () => {
    expect(call("POST", rejection(FIRST))).toEqual({ status: 200, payload: { ok: true } });
    expect(wholeDeck()).toEqual(SEEDED.slice(1));
    adoptAccount(OTHER);
    expect(wholeDeck()).toEqual(SEEDED);
  });

  it("fills a page past what was rejected, and its cursor continues the deck", () => {
    call("POST", rejection(FIRST));
    expect(ids(call("GET", DECK))).toEqual(SEEDED.slice(1, 31));
    expect(wholeDeck()).toEqual(SEEDED.slice(1));
  });

  it("answers 200 to a card already rejected", () => {
    call("POST", rejection(FIRST));
    expect(call("POST", rejection(FIRST)).status).toBe(200);
  });

  it("refuses 404 `suggestion.not_found` an id no card bears", () => {
    const answer = call("POST", rejection("movie:tmdb:1"));
    expect([answer.status, answer.payload.code]).toEqual([404, "suggestion.not_found"]);
  });

  it.each(["POST", "DELETE"])("refuses 400 an id that is no card's handle (%s)", (method) => {
    const answer = call(method, rejection("nonsense"));
    expect([answer.status, answer.payload.code]).toEqual([400, "request.invalid"]);
  });
});

describe("undoing a rejection", () => {
  it("brings the card back to its place", () => {
    call("POST", rejection(FIRST));
    expect(call("DELETE", rejection(FIRST))).toEqual({ status: 200, payload: { ok: true } });
    expect(wholeDeck()).toEqual(SEEDED);
  });

  it("refuses 404 what the account did not reject, another account's rejection included", () => {
    call("POST", rejection(FIRST));
    adoptAccount(OTHER);
    const answer = call("DELETE", rejection(FIRST));
    expect([answer.status, answer.payload.code]).toEqual([404, "suggestion.not_found"]);
  });
});
