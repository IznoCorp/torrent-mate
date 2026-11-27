// `sugGone` and `sugOrder` hold POSITIONS into the reserve, and a re-read of the deck moves them.
//
// WHAT MAKES THIS NON-VACUOUS. A re-read that drops a rejected card shifts every card after it by
// one: each case checks that the position held still names the SAME card, told by its id.
import { describe, expect, it } from "vitest";
import { isReplaced, remapPositions } from "./reserve-positions";

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
