// THE CATALOGUE'S OWN HOLDS — what two variants promise each other.
//
// A variant is normally held by what it DRAWS, on the page, by the oracle or
// by a harness rule. This file holds something neither of those can see: a
// relationship between two entries of the catalogue, which is true or false in
// the source and nowhere else.
import { describe, expect, it } from "vitest";
import {
  actionButton, cardStrip, disclosure, drawerEntryCount, iconButton, loadErrorAction, loadFooterAction, moreButton,
  segmentCount, segmentTab, stripDot, stripStep, tabBarBadge, viewSwitchButton,
} from "./variants";
import { cardMarkup } from "./card-markup";

/** The utilities that set a control's SIZE, as opposed to its mood. */
const SIZE = /^(min-h-|py-|px-|p-|text-\d|w-full$)/;

describe("the button system's sizes", () => {
  // THE SET IS CLOSED, AND THE TYPE IS WHAT CLOSES IT. The operator asked for
  // buttons that do not accept every size — « les boutons de l'interface
  // doivent être des composants qui n'autorisent pas toutes les tailles ». A
  // convention cannot deliver that; a union can, and this hold is the proof
  // that it does.
  //
  // THE ASSERTION IS A TYPE, NOT A CALL, and it had to become one: the obvious
  // spelling is the compiler directive that expects an error, and this tree
  // counts every such directive as a typing escape against a floor of hard
  // zero — the guard reads them in comments too, so even describing one costs
  // a violation. What is written instead asks the question directly: does an
  // arbitrary string satisfy the size the factory accepts? If it ever does —
  // because the union was widened, or replaced by `string` — the conditional
  // resolves to `never`, nothing can be assigned to it, and `tsc -b` goes red.
  //
  // A RUNTIME ASSERTION COULD NOT SEE THIS AT ALL: the call would simply emit
  // no size class and draw a button with no height, silently.
  it("refuses a size the catalogue does not offer", () => {
    type Offered = NonNullable<Parameters<typeof actionButton>[0]>["size"];
    type UnknownSizeIsRefused = "enormous" extends Offered ? never : true;
    const refused: UnknownSizeIsRefused = true;
    expect(refused).toBe(true);
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
        // An inactive action looks inactive, and every button draws it the same way.
        "disabled:opacity-50",
      ].sort(),
    );
  });
});

describe("the icon button's size", () => {
  // THE SAME CLOSED SET AS THE ACTION BUTTON'S, held the same way: a TYPE that
  // resolves to `never` the day an arbitrary size satisfies the factory, so
  // `tsc` goes red where a runtime assertion would see a button with no size
  // and pass.
  it("refuses a size the catalogue does not offer", () => {
    type Offered = NonNullable<Parameters<typeof iconButton>[0]>["size"];
    type UnknownSizeIsRefused = "enormous" extends Offered ? never : true;
    const refused: UnknownSizeIsRefused = true;
    expect(refused).toBe(true);
  });

  // ONE SIZE, AND ITS DRAWING WITH IT: the box a finger aims at and the drawing
  // inside it, so no wearer depends on a descendant rule to be legible.
  it("offers one size, a 32 px box with a 16 px drawing", () => {
    for (const step of ["w-[32px]", "h-[32px]", "[&>svg]:w-[16px]", "[&>svg]:h-[16px]"]) {
      expect(iconButton()).toContain(step);
    }
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

describe("the card strip counts its cells", () => {
  // THE STRIP KNOWS NO DOMAIN: it is told how many cells it carries, and a
  // ladder of eight is its first consumer of more than five. Written for five,
  // its grid drew an eighth cell on a second row.
  it("lays an eight-cell strip on eight columns, and a five-cell one unchanged", () => {
    expect(cardStrip({ cells: 8 })).toContain("grid-cols-[repeat(8,minmax(0,1fr))]");
    expect(cardStrip({ cells: 5 })).toBe(cardStrip());
    expect(cardStrip()).toContain("grid-cols-[repeat(5,minmax(0,1fr))]");
  });

  it("draws no label for a cell that has none", () => {
    const markup = cardMarkup({
      title: "x",
      side: { folderIcon: "", folderLabel: "", attributes: {} },
      body: {},
      strip: [{ state: "done", label: "a" }, { state: "now" }],
    });
    expect(markup.match(/class="l /g)?.length).toBe(1);
    expect(markup).toContain("grid-cols-[repeat(2,minmax(0,1fr))]");
  });

  // Two states beyond where the journey stands: held behind something else,
  // and put aside by the operator. Each wears a tone of the scale — a token,
  // never a raw colour (invariant 3) — and neither reads as the other.
  it("knows a waiting cell and an aside cell, each in a tone of the scale", () => {
    const waiting = stripDot({ state: "waiting" });
    const aside = stripDot({ state: "aside" });
    expect(waiting).toContain("bg-waiting");
    expect(aside).toContain("bg-neutral-signal");
    for (const drawn of [waiting, aside, stripStep({ state: "waiting" }), stripStep({ state: "aside" })]) {
      expect(drawn).not.toMatch(/#[0-9a-f]{3,8}\b|rgb\(|oklch\(/i);
    }
    expect(waiting).not.toBe(stripDot({ state: "pending" }));
    expect(aside).not.toBe(stripDot({ state: "pending" }));
  });
});

describe("one drawing per need, placed or sized", () => {
  // THE FINGER'S FLOOR IS THE TAB'S OWN: a page that draws a tab bar cannot
  // forget it, because no page declares it.
  it("puts the 44 px floor inside the tab and the « more » button", () => {
    expect(segmentTab()).toContain("min-h-[44px]");
    expect(moreButton()).toContain("w-[44px] h-[44px]");
  });

  // THREE BADGES WERE THREE DRAWINGS; one fill, one size, one type now, and
  // only where it sits differs.
  it("draws every count badge from one base, three placements apart", () => {
    const base = ["h-[18px]", "min-w-[18px]", "bg-primary", "text-primary-foreground", "text-2", "font-semibold"];
    for (const badge of [tabBarBadge(), drawerEntryCount(), segmentCount()]) {
      for (const utility of base) expect(badge).toContain(utility);
    }
    expect(tabBarBadge()).toContain("absolute");
    expect(drawerEntryCount()).toContain("ml-auto");
    expect(segmentCount()).toContain("ml-2");
  });

  it("sizes the segmented choice for an icon or for a word", () => {
    expect(viewSwitchButton()).toContain("w-[32px] h-[28px]");
    expect(viewSwitchButton({ size: "text" })).toContain("px-6");
    expect(viewSwitchButton({ size: "text" })).toContain("aria-pressed:bg-background");
  });

  // ONE CHEVRON, whatever the fold: the kinds change the summary, never it.
  it("wears the same chevron in every kind of fold", () => {
    const chevron = "[&>summary::before]:content-['›']";
    expect(disclosure()).toContain(chevron);
    expect(disclosure({ kind: "season" })).toContain(chevron);
    expect(disclosure()).not.toContain("▸");
  });
});
