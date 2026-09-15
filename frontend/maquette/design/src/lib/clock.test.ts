// The clock's two answers: the real date before the boot freezes it, the frozen
// day after.
//
// WHAT MAKES THIS NON-VACUOUS. The first answer is asserted against the real
// date computed here, and the frozen day chosen is one the real date can never
// be (a day in the past), so a clock that ignored the freeze, or one that
// ignored the real date, fails one of the two.
import { describe, expect, it } from "vitest";
import { freezeClock, today } from "./clock";

describe("today", () => {
  it("answers the real date until the boot freezes it, then the frozen day", () => {
    expect(today()).toBe(new Date().toISOString().slice(0, 10));
    freezeClock("2026-08-10");
    expect(today()).toBe("2026-08-10");
  });
});
