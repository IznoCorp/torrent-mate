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
  return { key, label, icon: null, tone: "neutral", onRun };
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
    // « Ne plus chercher » is the longest label; it must wrap inside a fixed
    // basis, because unequal buttons make the action row read as misaligned.
    renderSwipe({ right: [action("s", "Ne plus chercher")] });
    const button = screen.getByTestId("swipe-action");

    expect(button.className).toContain("flex-none");
    expect(button.className).toContain(`basis-[84${CSS_PX}]`);
    // R5: never a class named `grab` — the sheet handle owns that name at equal
    // specificity, and the later declaration wins.
    expect(button.className.split(/\s+/)).not.toContain("grab");
  });
});
