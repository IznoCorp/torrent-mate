// The layer's queued search names a run of its own, read running then settled (O-6 B).
//
// WHAT MAKES THIS NON-VACUOUS. The interface follows the run it is named: a layer answering one uid for
// two asks, or never `settled`, would leave a caller reading the wrong run or reading until its bound.
import { beforeEach, describe, expect, it } from "vitest";
import { routes } from "./handlers";
import { resolve, settled } from "./router";
import { keyOfMedium } from "./follow-key";
import { mockState, resetMockState } from "./state";

type Answer = { status: number; payload: any };

/**
 * Calls one operation as the interface would.
 *
 * @param method The method.
 * @param path The path, its identifier already encoded.
 * @param query The query, if any.
 * @returns The answer.
 */
function call(method: string, path: string, query: Record<string, string> = {}): Answer {
  const found = resolve(routes(), method, path);
  if (found === null) throw new Error(`no route ${method} ${path}`);
  const answer = found.route.handle({ path, parameters: found.parameters, query: new URLSearchParams(query), body: undefined });
  return settled(200, answer as never) as Answer;
}

beforeEach(() => resetMockState());

/** Asks a search of one follow; answers the run it names. */
function askSearch(index = 0): string {
  const key = keyOfMedium(mockState().follows[index])!;
  return call("POST", `/acquisition/followed/${encodeURIComponent(key)}/search`).payload.runUid;
}

const stateOf = (runUid: string) => call("GET", "/acquisition/status", { runUid }).payload.runState;

describe("a queued search in the layer", () => {
  it("is read running, then settled", () => {
    const runUid = askSearch();

    expect([stateOf(runUid), stateOf(runUid), stateOf(runUid)]).toEqual(["running", "settled", "settled"]);
  });

  it("names each ask's run apart, across follows too", () => {
    expect(new Set([askSearch(0), askSearch(1), askSearch(0)]).size).toBe(3);
  });

  it("states no run when none is asked about, or the uid names none", () => {
    expect(call("GET", "/acquisition/status").payload.runState).toBeNull();
    expect(stateOf("nothing")).toBeNull();
  });
});
