// ↑/↓ move by where the items are drawn, not by document order (DECIDED 6 = B).
//
// WHAT MAKES THIS NON-VACUOUS. The gallery is given in document order — a row of three, then the
// next — so a walk by order would land ↓ on the tile beside, not the one below; and the list's
// last row is asked for a ↓, which must stay put rather than wrap to the top.
import { describe, expect, it } from "vitest";
import { type Box, nextItem } from "./keys";

const box = (left: number, top: number, width = 100, height = 150): Box =>
  ({ left, top, right: left + width, bottom: top + height });

describe("nextItem", () => {
  const list = [box(0, 0, 700, 60), box(0, 60, 700, 60), box(0, 120, 700, 60)];

  it("moves to the row below and the row above in a list", () => {
    expect(nextItem(list, 0, 1)).toBe(1);
    expect(nextItem(list, 2, -1)).toBe(1);
  });

  it("stays on the last row on ↓ and on the first on ↑", () => {
    expect(nextItem(list, 2, 1)).toBe(2);
    expect(nextItem(list, 0, -1)).toBe(0);
  });

  it("moves to the tile BELOW in a gallery, not the one beside", () => {
    const grid = [box(0, 0), box(110, 0), box(220, 0), box(0, 160), box(110, 160), box(220, 160)];
    expect(nextItem(grid, 1, 1)).toBe(4);
    expect(nextItem(grid, 5, -1)).toBe(2);
  });

  it("lands on the nearest tile of a shorter last row", () => {
    const grid = [box(0, 0), box(110, 0), box(220, 0), box(0, 160)];
    expect(nextItem(grid, 2, 1)).toBe(3);
  });
});
