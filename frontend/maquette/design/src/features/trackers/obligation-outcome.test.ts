import { describe, expect, it } from "vitest";
import "../../lib/unit-words";
import { messageOf, outcomeOf } from "./obligation-outcome";
import type { Obligation } from "./queries";

// A running obligation, as the seeds hold one: the base each case moves.
const RUNNING: Obligation = {
  infoHash: "66e23ab395c438b7db4f7c855bd451d8bb1f0046",
  sourceTracker: "c411",
  title: "President Curtis S01E10",
  dispatchedPath: null,
  minimumRatio: 1,
  requiredRatio: 1.1,
  minimumSeedTimeSeconds: 259200,
  observedRatio: null,
  accumulatedSeedTimeSeconds: null,
  hitAndRunCount: null,
  addedAt: 1790601605,
  satisfiedAt: null,
  satisfiedBy: null,
  breachedAt: null,
  releasedAt: null,
  releasedBy: null,
  crossSeedOf: null,
};
const MET_AT = 1790860805;
const RELEASED_AT = 1790900000;

describe("outcomeOf — what ended an obligation, and why", () => {
  it("says nothing of an obligation still running, nor of none", () => {
    expect(outcomeOf(RUNNING)).toBeNull();
    expect(outcomeOf(undefined)).toBeNull();
  });

  it("says a met obligation and the arm of the rule that met it", () => {
    expect(outcomeOf({ ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "seedTime" }))
      .toEqual({ outcome: "met", at: MET_AT, reason: "seedTime" });
    expect(outcomeOf({ ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "ratio" }))
      .toEqual({ outcome: "met", at: MET_AT, reason: "ratio" });
  });

  it("says a released obligation, how its torrent left, and whether it had been met first", () => {
    expect(outcomeOf({ ...RUNNING, releasedAt: RELEASED_AT, releasedBy: "goneFromClient" }))
      .toEqual({ outcome: "released", at: RELEASED_AT, reason: "goneFromClient", metAt: null });
    expect(outcomeOf({
      ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "ratio", releasedAt: RELEASED_AT, releasedBy: "removedHere",
    })).toEqual({ outcome: "released", at: RELEASED_AT, reason: "removedHere", metAt: MET_AT });
  });

  it("never blanks a why the layer did not give: it is said unknown", () => {
    expect(outcomeOf({ ...RUNNING, satisfiedAt: MET_AT })).toEqual({ outcome: "met", at: MET_AT, reason: "unknown" });
    expect(outcomeOf({ ...RUNNING, releasedAt: RELEASED_AT }))
      .toEqual({ outcome: "released", at: RELEASED_AT, reason: "unknown", metAt: null });
  });
});

describe("messageOf — the outcome in the interface's words", () => {
  it("names the floor reached: the seed time in hours, the ratio with its margin", () => {
    const byTime = messageOf({ ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "seedTime" });
    expect(byTime?.tone).toBe("success");
    expect(byTime?.why).toContain("72");
    const byRatio = messageOf({ ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "ratio" });
    expect(byRatio?.why).toContain("1,10");
  });

  it("says a release in the tone of information, and an early one as early", () => {
    const beforeMet = messageOf({ ...RUNNING, releasedAt: RELEASED_AT, releasedBy: "goneFromClient" });
    const afterMet = messageOf({
      ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "seedTime", releasedAt: RELEASED_AT, releasedBy: "removedHere",
    });
    expect(beforeMet?.tone).toBe("info");
    expect(beforeMet?.why).not.toBe(afterMet?.why);
    expect(beforeMet?.lead).not.toBe(messageOf({ ...RUNNING, satisfiedAt: MET_AT, satisfiedBy: "seedTime" })?.lead);
  });
});
