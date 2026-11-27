// The layer answers the acquisition's gaps as the contract closes them (K3-G13 to K3-G16).
//
// WHAT MAKES THIS NON-VACUOUS. Each operation is asked the way the interface asks it, and what it
// answers is what a server answers: a deck continued by the cursor it issued, a search whose second
// page is reachable, a completeness named by the follow's key, and a refused reassignment carrying
// the code the contract declares.
import { beforeEach, describe, expect, it } from "vitest";
import FOLLOWS from "./seeds/follows.json";
import INCOMPLETE_SHOWS from "./seeds/incomplete-shows.json";
import SUGGESTIONS from "./seeds/suggestions.json";
import { routes } from "./handlers";
import { resolve, settled } from "./router";
import { followForKey, keyOfMedium } from "./follow-key";
import { mockState, resetMockState } from "./state";
import { heldAccounts, requestersOf } from "./identity";

type Answer = { status: number; payload: any };
type QueueRow = { title: string; kind?: string | null; ids?: unknown; requesters: { id: string }[] };

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

/** A title without its trailing year, as a card and a sheet of one medium share it. */
const bareTitle = (title: string) => title.replace(/\s*\(\d{4}\)\s*$/, "");

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

  it.each(["deck-0", "deck-7", "deck-030", "deck-999999"])(
    "refuses a well-formed cursor it never issued: %s",
    (cursor) => {
      const answer = call("GET", PATH, { cursor });

      expect([answer.status, answer.payload.code]).toEqual([400, "request.invalid"]);
    },
  );
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

  // A SERVER HOLDS NO ACQUISITION UNDER A MEDIUM NOBODY ASKED FOR: a follow is a standing follow,
  // a card is a follow or a card of the queue, and a sheet alone is neither.
  const unfollowed = (medium: { ids?: unknown; kind?: string | null }) => {
    const key = keyOfMedium(medium);
    return key !== null && followForKey(key) === undefined;
  };
  const queueCards = () => {
    const state = mockState();
    return [...state.takeable, ...state.blocked, ...state.inFlight, ...state.inFlightReel, ...state.moving];
  };
  const cardOnly = () => keyOfMedium(queueCards().find(unfollowed)!) as string;
  const bareSheet = () => {
    const carded = new Set(queueCards().map((one) => bareTitle(one.title)));
    const shows = (INCOMPLETE_SHOWS as { title: string; ids: Record<string, unknown> }[])
      .map((one) => ({ ...one, kind: "show" }));
    return keyOfMedium(shows.find((one) => unfollowed(one) && !carded.has(bareTitle(one.title)))!) as string;
  };
  const move = (kind: string, key: string) => {
    const [owner, other] = heldAccounts();
    return call("POST", PATH, {}, { kind, acquisition: key, from: owner.id, to: other.id });
  };

  it("answers 404 acquisition.not_found to a follow asked of a medium only a card holds", () => {
    const answer = move("follow", cardOnly());

    expect([answer.status, answer.payload.code]).toEqual([404, "acquisition.not_found"]);
  });

  it.each(["follow", "card"])("answers 404 acquisition.not_found to a %s nobody asked for, its sheet known", (kind) => {
    const answer = move(kind, bareSheet());

    expect([answer.status, answer.payload.code]).toEqual([404, "acquisition.not_found"]);
  });

  it("moves a card of the queue nobody follows", () => {
    expect(move("card", cardOnly()).status).toBe(200);
  });

  // EVERY CARD THE QUEUE SERVES IS ONE THE INTERFACE OFFERS THE MOVE ON, so the rows are read off
  // the answer, never off the lists the layer composes it from.
  it.each<Record<string, string>>([{}, { scenario: "loaded" }])(
    "moves the requester of every keyed row the queue serves: %o",
    (world) => {
      const rows = (): QueueRow[] => {
        const queue = call("GET", "/acquisition/to-handle", world).payload;
        return ["takeable", "blocked", "inFlight", "arrivals"].flatMap((list) => queue[list]);
      };
      const keyed = rows().filter((row) => keyOfMedium(row) !== null);
      const refusedRows = keyed.flatMap((row) => {
        resetMockState();
        const key = keyOfMedium(row) as string;
        const from = row.requesters[0].id;
        const to = heldAccounts().find((one) => !row.requesters.some((held) => held.id === one.id))!.id;
        const { status } = call("POST", PATH, {}, { kind: "card", acquisition: key, from, to });
        const after = rows().find((one) => one.title === row.title)?.requesters.map((one) => one.id) ?? [];
        return status === 200 && after.includes(to) && !after.includes(from) ? [] : [`${row.title} (${key}): ${status}`];
      });

      expect(keyed.length).toBeGreaterThan(0);
      expect(refusedRows).toEqual([]);
    },
  );

  it("answers 403 acquisition.not_requester when the requester moved did not ask", () => {
    const answer = call("POST", PATH, {}, { kind: "follow", acquisition, from: "nobody", to: holder() });

    expect([answer.status, answer.payload.code]).toEqual([403, "acquisition.not_requester"]);
  });
});
