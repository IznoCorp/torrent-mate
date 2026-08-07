/**
 * gestures — the arbitration rules for the acquisition views.
 *
 * These are the decisions a pointer handler would otherwise bury: which axis a
 * drag belongs to, whether a drag may start at all, and where it lands. jsdom
 * synthesises no real touch, so keeping them as pure functions is what makes
 * them verifiable at all — the handler wiring is exercised on a device, not here.
 */

import { describe, expect, it } from "vitest";

import {
  EDGE_DEAD_ZONE_PX,
  PULL_MAX_PX,
  PULL_THRESHOLD_PX,
  lockAxis,
  pullArmed,
  pullHeight,
  shouldRefresh,
  shouldStartViewSwipe,
  viewSwipeResult,
} from "./gestures";

describe("shouldStartViewSwipe", () => {
  it("ignores a drag born in the left edge band — iOS reserves it for back", () => {
    expect(shouldStartViewSwipe(12, 0)).toBe(false);
    expect(shouldStartViewSwipe(31, 0)).toBe(true);
  });

  it("measures the band from the container, not from the screen", () => {
    // A pager inset from the viewport must not treat its own left edge as safe
    // just because the page coordinate is large.
    const inset = 100;
    expect(shouldStartViewSwipe(inset + 5, inset)).toBe(false);
    expect(shouldStartViewSwipe(inset + EDGE_DEAD_ZONE_PX, inset)).toBe(true);
  });
});

describe("lockAxis", () => {
  it("locks nothing below the noise floor", () => {
    expect(lockAxis(3, 4)).toBeNull();
  });

  it("gives the drag to its dominant axis", () => {
    expect(lockAxis(12, 3)).toBe("x");
    expect(lockAxis(3, 12)).toBe("y");
  });

  it("resolves a perfect diagonal to the horizontal pager, not to both", () => {
    // A tie must not leave the drag driving the scroller AND the pager.
    expect(lockAxis(12, 12)).toBe("x");
  });
});

describe("viewSwipeResult", () => {
  it("springs back when the drag was too short to be a decision", () => {
    expect(viewSwipeResult(-40, 390, "maintenant")).toBe("maintenant");
  });

  it("commits once the drag clears the threshold", () => {
    expect(viewSwipeResult(-140, 390, "maintenant")).toBe("suivis");
    expect(viewSwipeResult(140, 390, "suivis")).toBe("maintenant");
  });

  it("does not wrap past the last view", () => {
    // Two views only: a hard flick must land where the operator aimed, not
    // carousel around to the other end.
    expect(viewSwipeResult(-300, 390, "suivis")).toBe("suivis");
    expect(viewSwipeResult(300, 390, "maintenant")).toBe("maintenant");
  });

  it("stays put when the width is unknown", () => {
    // Before first layout the width is 0; a ratio against it would make every
    // drag commit, so an unmeasured pager must not move at all.
    expect(viewSwipeResult(-999, 0, "maintenant")).toBe("maintenant");
  });
});

describe("pullHeight / pullArmed (maquette damping)", () => {
  it("amortit à 0.55 et plafonne à THRESH+16", () => {
    expect(pullHeight(100)).toBeCloseTo(55);
    expect(pullHeight(400)).toBe(PULL_MAX_PX);
  });

  it("s'arme à 62 % du seuil, en hauteur amortie", () => {
    expect(pullArmed(PULL_THRESHOLD_PX * 0.62)).toBe(true);
    expect(pullArmed(PULL_THRESHOLD_PX * 0.62 - 0.1)).toBe(false);
  });
});

describe("shouldRefresh", () => {
  it("commits sur la hauteur AMORTIE armée, pas sur la distance brute", () => {
    // Maquette: h = 0.55·dy doit atteindre 64×0.62 ≈ 39.68 → dy ≥ ~72.15.
    // Un dy de 64 (l'ancien seuil brut) n'amortit qu'à 35.2 : pas de refresh.
    expect(shouldRefresh(73, true)).toBe(true);
    expect(shouldRefresh(72, true)).toBe(false);
    expect(shouldRefresh(PULL_THRESHOLD_PX, true)).toBe(false);
  });

  it("never refreshes mid-list — that pull is a scroll", () => {
    expect(shouldRefresh(PULL_THRESHOLD_PX * 3, false)).toBe(false);
  });
});
