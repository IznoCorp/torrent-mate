// THE ROWS A LIST DRAWS AROUND ITS CARDS, AS TYPED VARIANTS — the swipe row and
// the selection row.
//
// EVERY FACTORY KEEPS ITS IDENTITY CLASS AT THE FRONT. The swipe gesture finds
// its row by `.swipe` and measures a drawer through `.side.right` and
// `.side.left`; the selection is read off `.selrow`.
//
// EVERY BRANCH IS ONE STRING LITERAL: `residue.py` reads a branch through its
// literals, one branch per literal, and a branch split in two is read as two.
import { cva } from "../cva";

/**
 * A row that slides aside to uncover its actions. It CLAIMS the vertical pan and
 * leaves the horizontal axis to its own gesture: without `pan-y` the browser owns
 * both axes, decides a drag is a pan and cancels the touch, and the swipe works
 * only under synthetic events. Declared on the row, not on an ancestor, because
 * `touch-action` intersects down the whole chain. And it selects no text: a mouse
 * drag would otherwise select what it passes over, and the selection swallows
 * the gesture.
 */
export const swipeRow = cva("swipe relative overflow-hidden rounded-3 touch-pan-y select-none");

/** The drawers under a swipe row, filling it edge to edge. */
export const swipeActions = cva("actions absolute inset-0 flex items-stretch justify-end");

/** One drawer: its actions side by side, the right one pushed to its edge. */
export const swipeSide = cva("side flex flex-[0_0_auto]", {
  variants: { edge: { left: "left", right: "right ml-auto" } },
});

/**
 * A row in selection mode: the card's anatomy with a check in front. A mode of
 * the list, not a variant of the card, and its pressed state is its own border.
 */
export const selectionRow = cva(
  "selrow flex items-center gap-5 w-full border border-border bg-card rounded-3 p-4 text-left " +
    "[&>.poster]:block aria-pressed:border-primary aria-pressed:[box-shadow:0_0_0_1px_var(--color-primary)]",
);

/** The selection row's title and sub-line, taking the room the check and the poster leave. */
export const selectionRowText = cva("rowtxt min-w-0 flex-1");
