// The clock's two answers: the real date before the boot freezes it, the frozen
// day after; and the moment a « since » names.
//
// WHAT MAKES THIS NON-VACUOUS. The first answer is asserted against the real
// date computed here, and the frozen day chosen is one the real date can never
// be (a day in the past), so a clock that ignored the freeze, or one that
// ignored the real date, fails one of the two.
import { describe, expect, it } from "vitest";
import "./unit-words";
import { freezeClock, momentOf, timeOfDay, today } from "./clock";

describe("today", () => {
  it("answers the real date until the boot freezes it, then the frozen day", () => {
    expect(today()).toBe(new Date().toISOString().slice(0, 10));
    freezeClock("2026-08-10");
    expect(today()).toBe("2026-08-10");
  });
});

describe("momentOf", () => {
  // Read on 1 October 2026 at noon; one instant that morning, one on 12 September.
  const NOW = new Date(2026, 9, 1, 12, 0);
  const THIS_MORNING = new Date(2026, 9, 1, 9, 5).getTime() / 1000;
  const WEEKS_AGO = new Date(2026, 8, 12, 2, 0).getTime() / 1000;

  it("says the time alone on the day it is read", () => {
    expect(momentOf(THIS_MORNING, NOW)).toBe(timeOfDay(THIS_MORNING));
  });

  it("says the day, then the time, before it — never a bare hour a past day shares (M4)", () => {
    // french-ok: the rendered moment the test asserts, from fr.json's words
    expect(momentOf(WEEKS_AGO, NOW)).toBe("le 12 septembre à 02 h 00");
  });
});
