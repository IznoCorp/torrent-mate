// « Marquer comme vu » is offered by the right that opens « À traiter » and its
// badge — `acquisition.todo.view` — never by the right to ask for acquisitions
// (the orchestrator's ruling on the lot's open point 1): whoever reads the
// closure in the list may mark it seen; whoever cannot open the list never
// meets the closure.
import { describe, expect, it } from "vitest";
import { rightsOf, type Right } from "../../lib/rights";
import type { Schemas } from "../../lib/contract-schemas";
import { offeredActs } from "./act-rights";

/**
 * An account holding exactly the rights named.
 *
 * @param rights The role's rights.
 * @returns The account's rights.
 */
function holding(rights: Right[]) {
  const role = { id: "r", name: "r", kind: "ordinary", rights } as Schemas["Role"];
  return rightsOf({ id: "a", name: "a", email: "a@example.invalid", avatar: "", role, signInKind: "plex", forbiddenWrites: [] });
}

const MARK_SEEN = [{ target: { "closure-seen": "Silo|S03E07" } }];

describe("« Marquer comme vu »", () => {
  it("is offered to an account that reads « À traiter », whether or not it may ask", () => {
    expect(offeredActs(MARK_SEEN, {}, holding(["library.read", "acquisition.todo.view"]))).toHaveLength(1);
  });

  it("is not offered to one that may ask but not read « À traiter »", () => {
    expect(offeredActs(MARK_SEEN, {}, holding(["library.read", "acquisition.request"]))).toHaveLength(0);
  });
});
