// `sugGone` and `sugOrder` hold POSITIONS into the reserve, and a re-read of the deck moves them.
//
// WHAT MAKES THIS NON-VACUOUS. A re-read that drops a rejected card shifts every card after it by
// one: each case checks that the position held still names the SAME card, told by its id. The cache
// is a real one, so what is read is what the listener does with its events.
import { QueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { accountQuery } from "../../lib/account";
import { followReserve, isReplaced, onReserveReplaced, remapPositions } from "./reserve-positions";
import { installSuggestionsLookup, suggestionsQuery } from "./queries";

const held = vi.hoisted(() => ({
  state: { sugGone: new Set<number>(), sugOrder: null as number[] | null },
}));

vi.mock("../../lib/store-access", () => ({
  store: {
    read: () => ({ state: held.state }),
    write: (patch: object) => void Object.assign(held.state, patch),
    touch: () => undefined,
  },
  useUiState: () => held.state,
}));

const page = (...ids: string[]) => ({ suggestions: ids.map((id) => ({ id })), nextCursor: null });
const spent = () => [...held.state.sugGone];

let redrawn = 0;
let client: QueryClient;

beforeEach(() => {
  held.state = { sugGone: new Set(), sugOrder: null };
  redrawn = 0;
  onReserveReplaced(() => void (redrawn += 1));
  client = new QueryClient();
});

afterEach(() => {
  client.clear();
  vi.unstubAllGlobals();
});

describe("a reserve replaced under the positions held", () => {
  it("is not replaced when it only grows at the end", () => {
    expect(isReplaced(["a", "b"], ["a", "b", "c"])).toBe(false);
    expect(isReplaced(["a", "b"], ["a", "b"])).toBe(false);
  });

  it("is replaced when a card leaves or moves", () => {
    expect(isReplaced(["a", "b", "c"], ["a", "c"])).toBe(true);
    expect(isReplaced(["a", "b"], ["b", "a"])).toBe(true);
    expect(isReplaced(["a", "b"], ["a"])).toBe(true);
  });

  it("keeps each spent position on the card it was spent on", () => {
    const moved = remapPositions(["a", "b", "c", "d"], ["b", "c", "d", "e"], new Set([0, 2]), null);
    expect([...moved.gone]).toEqual([1]);
    expect(moved.order).toBeNull();
  });

  it("keeps the order « Passer » arranged, and puts what arrived at its end", () => {
    const moved = remapPositions(["a", "b", "c"], ["b", "c", "d"], new Set(), [2, 0, 1]);
    expect(moved.order).toEqual([1, 0, 2]);
  });
});

describe("the reserve followed in the cache", () => {
  const KEY = ["/api/v1/acquisition/suggestions"];
  const read = (...ids: string[]) => client.setQueryData(KEY, page(...ids));

  beforeEach(() => followReserve(client, KEY));

  it("carries what is spent and the order onto the cards of a shorter page, then draws once", () => {
    read("a", "b", "c");
    const gone = held.state.sugGone;
    gone.add(2);
    held.state.sugOrder = [2, 0, 1];

    read("b", "c");

    expect(held.state.sugGone).toBe(gone);
    expect(spent()).toEqual([1]);
    expect(held.state.sugOrder).toEqual([1, 0]);
    expect(redrawn).toBe(1);
  });

  it("changes nothing when the reserve only grows", () => {
    read("a", "b");
    held.state.sugGone.add(1);

    read("a", "b", "c");

    expect(spent()).toEqual([1]);
    expect(redrawn).toBe(0);
  });

  it("carries the positions onto the page read after the query was evicted", () => {
    read("a", "b", "c");
    held.state.sugGone.add(0);

    client.removeQueries({ queryKey: KEY });
    read("b", "c");

    // « a » left the reserve: neither « b » nor « c » was ever rejected.
    expect(spent()).toEqual([]);
  });
});

describe("another account signing in on the same device", () => {
  const KEY = ["/api/v1/acquisition/suggestions"];
  const read = (...ids: string[]) => client.setQueryData(KEY, page(...ids));
  const signedIn = (id: string, name = id) => client.setQueryData(accountQuery.queryKey, { id, name });

  beforeEach(() => {
    followReserve(client, KEY);
    signedIn("account-a");
    read("a", "b", "c");
    // A rejects « a » and passes « b » to the back.
    held.state.sugGone.add(0);
    held.state.sugOrder = [0, 2, 1];
  });

  it.each(["the account first", "the deck first"])("sees every card the server gives it, %s", async (order) => {
    // The sign-out and the next landing: the cache is reset, then both are read again.
    await client.resetQueries();
    if (order === "the account first") signedIn("account-b");
    read("a", "b", "c");
    if (order === "the deck first") signedIn("account-b");

    expect(spent()).toEqual([]);
    expect(held.state.sugOrder).toBeNull();
    expect(redrawn).toBeGreaterThan(0);
  });

  it("keeps carrying the positions it writes itself", () => {
    signedIn("account-b");
    held.state.sugGone.add(2);

    read("b", "c");

    expect(spent()).toEqual([1]);
  });

  it("keeps the positions of the same account read again, even after a sign-out", async () => {
    await client.resetQueries();
    signedIn("account-a", "renamed");

    expect(spent()).toEqual([0]);
    expect(held.state.sugOrder).toEqual([0, 2, 1]);
    expect(redrawn).toBe(0);
  });
});

describe("the deck's lookup, as the boot installs it", () => {
  it("follows the reserve it publishes", () => {
    // The deck's own first read is left unanswered.
    vi.stubGlobal("fetch", () => new Promise(() => undefined));
    installSuggestionsLookup(client);
    client.setQueryData(suggestionsQuery.queryKey, page("a", "b", "c") as never);
    held.state.sugGone.add(2);

    client.setQueryData(suggestionsQuery.queryKey, page("b", "c") as never);

    expect(spent()).toEqual([1]);
  });
});
