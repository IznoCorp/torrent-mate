// THE CATALOGUE'S OWN HOLDS — what two variants promise each other.
//
// A variant is normally held by what it DRAWS, on the page, by the oracle or
// by a harness rule. This file holds something neither of those can see: a
// relationship between two entries of the catalogue, which is true or false in
// the source and nowhere else.
import { describe, expect, it } from "vitest";
import { actionButton, loadErrorAction, loadFooterAction } from "./variants";

/** The utilities that set a control's SIZE, as opposed to its mood. */
const SIZE = /^(min-h-|py-|px-|p-|text-\d|w-full$)/;

describe("the button system's sizes", () => {
  // THE SET IS CLOSED, AND THE TYPE IS WHAT CLOSES IT. The operator asked for
  // buttons that do not accept every size — « les boutons de l'interface
  // doivent être des composants qui n'autorisent pas toutes les tailles ». A
  // convention cannot deliver that; a union can, and this hold is the proof
  // that it does.
  //
  // `@ts-expect-error` IS THE ASSERTION, and it fails in the direction that
  // matters: if the size ever stops being refused, the directive itself
  // becomes an error and `tsc -b` goes red. A runtime `expect` could not see
  // this at all — the call would simply emit no size class and draw a button
  // with no height, silently.
  it("refuses a size the catalogue does not offer", () => {
    // @ts-expect-error — an arbitrary size is not a size.
    expect(() => actionButton({ size: "enormous" })).not.toThrow();
  });

  it("offers exactly the two it names, and both are drawable", () => {
    expect(actionButton({ size: "screen" })).toContain("min-h-[44px]");
    expect(actionButton({ size: "footer" })).toContain("min-h-[40px]");
  });

  // AND THE SCREEN SIZE IS WHAT IT ALWAYS WAS, token for token. Every one of
  // the call sites drawing a primary action calls `actionButton()` with no
  // argument, so the default branch is the thing 19 surfaces render. Splitting
  // a base into a base and a branch must not move any of them, and asserting
  // the exact set is how that is known rather than hoped.
  it("and the default is the screen size, unchanged", () => {
    const written = actionButton().split(/\s+/).filter(Boolean).sort();
    expect(written).toEqual(
      [
        "flex", "items-center", "justify-center", "gap-4", "w-full",
        "min-h-[44px]", "py-5", "px-6", "rounded-3", "text-4",
        "font-semibold", "text-center",
      ].sort(),
    );
  });
});

describe("the load footer's two actions", () => {
  // THE FOOT OF A LIST HOLDS OUT ONE CONTROL, in two moods: « retry » when the
  // list failed, « load more » when it ran out.
  //
  // THEY NO LONGER SHARE A SPELLING, and that is the repair rather than a
  // regression. The load-more's size now comes from the button system's closed
  // set and the retry keeps its own, so there is no duplicate scale left for a
  // hold to police — what replaced that hold is the one above, which is
  // stronger: it holds the SET, not an agreement between two copies of it.
  //
  // What is held here instead is that the load-more spells NO size at all. A
  // size creeping back into the mood is exactly how the closed set would stop
  // meaning anything, and it would draw plausibly while it did.
  it("the load-more spells no size of its own", () => {
    const steps = loadFooterAction().split(/\s+/).filter((one) => SIZE.test(one));
    expect(steps).toEqual([]);
  });

  // AND EACH KEEPS WHAT IS ITS OWN. The retry sits under the message that
  // explains it and needs the gap; the load-more carries an icon and has to
  // centre its content, because the base layer's `:has(> svg)` rule
  // left-aligns the action-button system and this is not part of it.
  it("and keep what distinguishes them", () => {
    expect(loadErrorAction()).toContain("mt-4");
    expect(actionButton({ size: "footer" })).toContain("justify-center");
    expect(loadErrorAction()).not.toContain("justify-center");
  });

  // THE ICON IS SIZED BY THE SIZE, and this is B-315 (a)'s second half. The
  // button wears none of the legacy classes whose descendant rules size the
  // action-button system's icons, so an `<svg>` left to itself took the
  // replaced-element default and the flex box stretched it — 227 px, in a
  // button 245 px tall, which is what the operator was looking at. R136 read
  // font-size and padding and passed it.
  it("and the footer size carries its icon's size", () => {
    expect(actionButton({ size: "footer" })).toContain("[&>svg]:w-[16px]");
    expect(actionButton({ size: "footer" })).toContain("[&>svg]:h-[16px]");
  });
});
