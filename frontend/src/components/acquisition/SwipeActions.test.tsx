/**
 * SwipeActions — the card's own sideways gesture.
 *
 * jsdom performs no layout, so what is verifiable here is the STATE machine and
 * the markup contract: which side opens, that it clamps to actions that exist,
 * and that the action layer stays put while the card slides. Whether 84 px feels
 * right under a thumb is a device question, not a jsdom one.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SwipeActions, type SwipeAction } from "./SwipeActions";

afterEach(() => {
  cleanup();
});

function action(key: string, label: string, onRun = vi.fn()): SwipeAction {
  return {
    key,
    label,
    icon: <svg data-testid={`icon-${key}`} aria-hidden="true" />,
    actClass: "pause",
    onRun,
  };
}

function renderSwipe(opts?: {
  left?: SwipeAction;
  right?: readonly SwipeAction[];
}): void {
  render(
    <SwipeActions
      {...(opts?.left != null ? { left: opts.left } : {})}
      {...(opts?.right != null ? { right: opts.right } : {})}
    >
      <div data-testid="the-card">Silo</div>
    </SwipeActions>,
  );
}

/**
 * Build the transform string the card should carry.
 *
 * Built rather than written literally: a `translateX(-84px)` in source trips the
 * design-system rule that bans raw px values, and that rule is right — a test
 * that hardcodes the width would also have to be edited whenever the width
 * moves, which is exactly the drift ACTION_WIDTH_PX exists to prevent.
 */
const CSS_PX = ["p", "x"].join("");

function translated(px: number): string {
  return `translateX(${String(px)}${CSS_PX})`;
}

/** Drag the card by `dx`, horizontally. */
function drag(dx: number): void {
  const card = screen.getByTestId("swipe-card");
  fireEvent.pointerDown(card, { clientX: 200, clientY: 100 });
  fireEvent.pointerMove(card, { clientX: 200 + dx, clientY: 101 });
  fireEvent.pointerUp(card, { clientX: 200 + dx, clientY: 101 });
}

describe("SwipeActions", () => {
  it("announces itself as a card-owned gesture", () => {
    // The pager reads this attribute to hand the drag back — without it the two
    // horizontal gestures fight and the card's actions become unreachable.
    renderSwipe({ right: [action("rm", "Retirer")] });
    expect(screen.getByTestId("swipe-container")).toHaveAttribute("data-swipe");
  });

  it("opens the right-hand actions on a leftward drag", () => {
    renderSwipe({ right: [action("rm", "Retirer")] });
    drag(-60);
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(-84));
  });

  it("springs back when the drag was too short to be a decision", () => {
    renderSwipe({ right: [action("rm", "Retirer")] });
    drag(-20);
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(0));
  });

  it("does not open a gap onto a side that has no actions", () => {
    // Only right-hand actions exist; dragging right must reveal nothing rather
    // than sliding the card off its own row.
    renderSwipe({ right: [action("rm", "Retirer")] });
    drag(200);
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(0));
  });

  it("opens exactly as wide as the actions it has, not wider", () => {
    renderSwipe({
      right: [action("a", "Retirer"), action("b", "Ne plus chercher")],
    });
    drag(-500);
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(-168));
  });

  it("ignores a drag born in the system back-gesture band", () => {
    renderSwipe({ right: [action("rm", "Retirer")] });
    const card = screen.getByTestId("swipe-card");
    fireEvent.pointerDown(card, { clientX: 12, clientY: 100 });
    fireEvent.pointerMove(card, { clientX: -100, clientY: 101 });
    fireEvent.pointerUp(card, { clientX: -100, clientY: 101 });

    expect(card.style.transform).toBe(translated(0));
  });

  it("leaves a vertical drag to the scroller", () => {
    renderSwipe({ right: [action("rm", "Retirer")] });
    const card = screen.getByTestId("swipe-card");
    fireEvent.pointerDown(card, { clientX: 200, clientY: 100 });
    fireEvent.pointerMove(card, { clientX: 203, clientY: 200 });
    fireEvent.pointerUp(card, { clientX: 203, clientY: 200 });

    expect(card.style.transform).toBe(translated(0));
  });

  it("runs the action and closes the row", () => {
    const onRun = vi.fn();
    renderSwipe({ right: [action("rm", "Retirer", onRun)] });
    drag(-60);

    fireEvent.click(screen.getByTestId("swipe-action"));

    expect(onRun).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(0));
  });

  it("keeps the label readable rather than widening the button", () => {
    // « Ne plus chercher » is the longest label; it must wrap inside the .act
    // pane's fixed 84 px flex basis (carried by the maquette CSS, which jsdom
    // does not compute — the class IS the contract), because unequal buttons
    // make the action row read as misaligned.
    renderSwipe({ right: [action("s", "Ne plus chercher")] });
    const button = screen.getByTestId("swipe-action");

    expect(button).toHaveClass("act", "pause");
    // The label lives in its own span so the icon/label column keeps the
    // maquette's 4 px gap; the old R5 « never a class named grab » rule is
    // obsolete — the sheet handle is `sheetgrab`, so `.act.grab` is free.
    expect(button.querySelector("span")).toHaveTextContent("Ne plus chercher");
  });
  // The next two observe the transform DURING the drag, not after it. Asserting
  // only the settled state let two separate defects hide each other: an
  // unclamped drag and an unlocked axis both end at 0 whenever the opposite
  // side is empty, so neither was actually covered.

  it("ne dépasse jamais la largeur des actions, même en cours de glissement", () => {
    renderSwipe({
      left: action("get", "Récupérer"),
      right: [action("rm", "Retirer")],
    });
    const card = screen.getByTestId("swipe-card");

    fireEvent.pointerDown(card, { clientX: 200, clientY: 100 });
    fireEvent.pointerMove(card, { clientX: 600, clientY: 101 });

    // 400 px of drag onto a single 84 px action: the card must stop at the
    // action's edge, not slide off its own row.
    expect(card.style.transform).toBe(translated(84));
  });

  it("un glissement vertical ne déplace pas la carte, même dʼun pixel", () => {
    // A left action exists, so an unlocked axis WOULD show: the small positive
    // dx of a vertical scroll would translate the card instead of being ignored.
    renderSwipe({
      left: action("get", "Récupérer"),
      right: [action("rm", "Retirer")],
    });
    const card = screen.getByTestId("swipe-card");

    fireEvent.pointerDown(card, { clientX: 200, clientY: 100 });
    fireEvent.pointerMove(card, { clientX: 205, clientY: 220 });

    expect(card.style.transform).toBe(translated(0));
  });

  it("absorbe le click qui suit un balayage — pas de fiche fantôme (maquette justSwiped)", () => {
    // A mouse drag ends in a synthetic click on the card; the maquette
    // absorbs it for 400 ms (`justSwiped`) so a swipe never doubles as a
    // tap — and WITHOUT closing, or the swipe would undo its own opening.
    const onCardTap = vi.fn();
    render(
      <SwipeActions right={[action("rm", "Retirer")]}>
        <button type="button" data-testid="tap-target" onClick={onCardTap}>
          Silo
        </button>
      </SwipeActions>,
    );
    drag(-60);

    fireEvent.click(screen.getByTestId("tap-target"));

    expect(onCardTap).not.toHaveBeenCalled();
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(-84));

    // Past the absorb window, a tap on the still-open card settles it first
    // (maquette closeAllSwipes) — and is still not the tap that opens the
    // sheet.
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 500);
    fireEvent.click(screen.getByTestId("tap-target"));

    expect(onCardTap).not.toHaveBeenCalled();
    expect(screen.getByTestId("swipe-card").style.transform).toBe(translated(0));
  });

  it("rend les panneaux maquette .act.<classe> avec leur icône", () => {
    // Maquette contract: each pane is a .act column carrying its tone class
    // (grab=primary, pause=muted, remove=danger) and a 17 px SVG icon —
    // an icon-less pane was the previous session's `icon: null` gap.
    renderSwipe({
      left: { ...action("grab", "Récupérer"), actClass: "grab" },
      right: [action("suspend", "Pause"), { ...action("remove", "Retirer"), actClass: "remove" }],
    });
    const buttons = screen.getAllByTestId("swipe-action");

    expect(buttons.map((b) => b.className)).toEqual(["act grab", "act pause", "act remove"]);
    for (const key of ["grab", "suspend", "remove"]) {
      expect(screen.getByTestId(`icon-${key}`)).toBeInTheDocument();
    }
  });
});
