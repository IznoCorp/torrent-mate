// The layer answers the acquisition's gaps as the contract closes them (K3-G13 to K3-G16).
//
// WHAT MAKES THIS NON-VACUOUS. Each operation is asked the way the interface asks it, and what it
// answers is what a server answers: a deck continued by the cursor it issued, a search whose second
// page is reachable, a completeness named by the follow's key, and a refused reassignment carrying
// the code the contract declares.
import { beforeEach, describe, expect, it } from "vitest";
import FOLLOWS from "./seeds/follows.json";
import SUGGESTIONS from "./seeds/suggestions.json";
import { routes } from "./handlers";
import { resolve, settled } from "./router";
import { keyOfMedium } from "./follow-key";
import { resetMockState } from "./state";
import { requestersOf } from "./identity";

type Answer = { status: number; payload: any };

/**
 * Calls one operation as the interface would.
 *
 * @param method The method.
 * @param path The path, its identifier already encoded.
 * @param query The query, if any.
 * @param body The request body, if any.
 * @returns The answer.
 */
function call(method: string, path: string, query: Record<string, string> = {}, body?: unknown): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route ${method} ${path}`);
  const answer = found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(query), body });
  return settled(200, answer as never) as Answer;
}

beforeEach(() => resetMockState());

describe("the suggestions deck, by cursor (K3-G13)", () => {
  const PATH = "/acquisition/suggestions";

  it("pages the whole deck by the cursor it issues, and ends it with none", () => {
    const seen: string[] = [];
    let cursor: string | null = null;
    let pages = 0;
    do {
      const query: Record<string, string> = cursor === null ? {} : { cursor };
      const answer = call("GET", PATH, query);
      seen.push(...answer.payload.suggestions.map((one: { title: string }) => one.title));
      cursor = answer.payload.nextCursor;
      pages += 1;
    } while (cursor !== null && pages < SUGGESTIONS.length);

    expect(seen).toEqual(SUGGESTIONS.map((one) => one.title));
    expect(pages).toBeGreaterThan(1);
  });

  it("refuses a cursor it never gave, a title among them", () => {
    const answer = call("GET", PATH, { cursor: SUGGESTIONS[0].title });

    expect(answer.status).toBe(400);
    expect(answer.payload.code).toBe("request.invalid");
  });
});

describe("the provider search, by page (K3-G14)", () => {
  const PATH = "/acquisition/search";
  // A word enough of the seeded results carry to cut two pages out of them.
  const WORD = "a";

  it("reaches the results past the first page, under the same total", () => {
    const whole = call("GET", PATH, { query: WORD }).payload;
    const page = call("GET", PATH, { query: WORD, offset: "1", limit: "2" }).payload;

    expect(whole.total).toBeGreaterThan(2);
    expect(page.results).toEqual(whole.results.slice(1, 3));
    expect([page.shown, page.total]).toEqual([2, whole.total]);
  });

  it.each<Record<string, string>>([{ limit: "0" }, { limit: "101" }, { offset: "-1" }, { limit: "two" }])(
    "refuses a page outside the contract's bounds: %o",
    (bounds) => {
      const answer = call("GET", PATH, { query: WORD, ...bounds });

      expect(answer.status).toBe(400);
      expect(answer.payload.code).toBe("request.invalid");
    },
  );
});

describe("a follow's completeness (K3-G15)", () => {
  it("names the follow by its key, for every seeded follow", () => {
    for (const follow of FOLLOWS) {
      const key = keyOfMedium(follow) as string;
      const answer = call("GET", `/acquisition/followed/${encodeURIComponent(key)}/completeness`);

      expect(answer.payload.followedId, follow.title).toBe(key);
    }
  });
});

describe("a refused reassignment (K3-G16)", () => {
  const PATH = "/acquisition/requesters/reassign";
  const [follow] = FOLLOWS;
  const acquisition = keyOfMedium(follow) as string;
  const holder = () => requestersOf(follow.title)[0].id;

  it("answers 404 account.unknown to a target no account carries", () => {
    const answer = call("POST", PATH, {}, { kind: "follow", acquisition, from: holder(), to: "nobody" });

    expect([answer.status, answer.payload.code]).toEqual([404, "account.unknown"]);
  });

  it("answers 404 acquisition.not_found to a key nothing answers to", () => {
    const answer = call("POST", PATH, {}, { kind: "follow", acquisition: "tvdb:0", from: holder(), to: holder() });

    expect([answer.status, answer.payload.code]).toEqual([404, "acquisition.not_found"]);
  });

  it("answers 403 acquisition.not_requester when the requester moved did not ask", () => {
    const answer = call("POST", PATH, {}, { kind: "follow", acquisition, from: "nobody", to: holder() });

    expect([answer.status, answer.payload.code]).toEqual([403, "acquisition.not_requester"]);
  });
});
