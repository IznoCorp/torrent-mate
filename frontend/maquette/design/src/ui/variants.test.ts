// THE CATALOGUE'S OWN HOLDS — what two variants promise each other.
//
// A variant is normally held by what it DRAWS, on the page, by the oracle or
// by a harness rule. This file holds something neither of those can see: a
// relationship between two entries of the catalogue, which is true or false in
// the source and nowhere else.
import { describe, expect, it } from "vitest";
import { loadErrorAction, loadFooterAction } from "./variants";

/** The utilities that set a control's SIZE, as opposed to its placement. */
const SCALE = new Set([
  "w-full", "border", "border-border", "bg-transparent", "text-foreground",
  "text-3", "font-semibold", "p-4", "rounded-2",
]);

describe("the load footer's two actions", () => {
  // THE FOOT OF A LIST HOLDS OUT ONE CONTROL, in two moods: « retry » when the
  // list failed, « load more » when it ran out. They are one offer and they
  // are drawn at one scale — and the only reason that is not enforced by a
  // shared constant is that a constant makes both factories unreadable to
  // `residue.py`, which reads a base by its string literals.
  //
  // SO THE SHARING IS HELD HERE INSTEAD, and this is the hold that fails when
  // someone changes one of the two and not the other. Without it the duplicate
  // spelling is a promise nobody checks, which is the state the catalogue
  // exists to prevent.
  it("carry the same scale, token for token", () => {
    const scaleOf = (classes: string) =>
      classes.split(/\s+/).filter((one) => SCALE.has(one)).sort();
    expect(scaleOf(loadFooterAction())).toEqual(scaleOf(loadErrorAction()));
  });

  // AND EACH KEEPS WHAT IS ITS OWN. The retry sits under the message that
  // explains it and needs the gap; the load-more carries an icon and has to
  // centre its content, because the base layer's `:has(> svg)` rule
  // left-aligns the action-button system and this is not part of it. A hold on
  // the scale alone would pass a change that flattened the two into one.
  it("and keep what distinguishes them", () => {
    expect(loadErrorAction()).toContain("mt-4");
    expect(loadFooterAction()).toContain("justify-center");
    expect(loadErrorAction()).not.toContain("justify-center");
  });

  // THE SCALE IS THE FOOTER'S, NOT THE SCREEN'S, and that is B-315 (a): the
  // « load more » button wore the action-button system's step and the operator
  // reported it too big. R136 reads the RENDERED size against the token on the
  // page; this reads the intent in the source, where a step typed by hand
  // instead of taken from the scale would still render plausibly.
  it("and sit one step below the screen's own actions", () => {
    expect(loadFooterAction()).toContain("text-3");
    expect(loadFooterAction()).not.toContain("text-4");
  });
});
