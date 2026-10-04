// THE ROWS A LIST DRAWS AROUND ITS CARDS, AS TYPED VARIANTS — the swipe row, the
// commit row and the selection row.
//
// EVERY FACTORY KEEPS ITS IDENTITY CLASS AT THE FRONT. The swipe gesture finds
// its row by `.swipe` and measures a drawer through `.side.right` and
// `.side.left`; the selection is read off `.selrow`.
//
// EVERY BRANCH IS ONE STRING LITERAL: `harness/factories.py` reads a factory's
// base through its literals, and its branches one per literal.
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
export const swipeRow = cva(
  "swipe relative overflow-hidden rounded-3 touch-pan-y select-none [&_img]:[-webkit-user-drag:none]",
);

/**
 * One action a swipe row uncovers: an icon over its word, at the width the
 * gesture measures a drawer by. The gesture finds it through `.act`, and a
 * removal through `.remove`.
 */
export const swipeAction = cva(
  "act [border:0] text-2 font-bold leading-[1.2] flex-none w-[84px] flex flex-col items-center justify-center " +
    "gap-2 py-0 px-2 text-center [&_svg]:w-[17px] [&_svg]:h-[17px]",
  {
    variants: {
      tone: {
        resume: "resume bg-primary text-primary-foreground",
        pause: "pause bg-muted text-foreground",
        remove: "remove bg-danger-fill text-white",
      },
    },
  },
);

/**
 * The drawers under a swipe row, filling it inside the card's rim. ONE PIXEL IN
 * and rounded as the card is: laid edge to edge, the drawer's colour showed
 * through the card's antialiased corners — pink arcs at a follow card's right
 * corners, on Chrome and WebKit alike (the reader of the train, 2026-09-30).
 * The card's opaque border covers the pixel it gives up.
 */
export const swipeActions = cva("actions absolute inset-px rounded-3 overflow-hidden flex items-stretch justify-end");

/** One drawer: its actions side by side, the right one pushed to its edge. */
export const swipeSide = cva("side flex flex-[0_0_auto]", {
  variants: { edge: { left: "left", right: "right ml-auto" } },
});

/**
 * A row a swipe DECIDES on release — the application's second swipe, beside the
 * swipe row, and different on purpose: the swipe row OPENS a drawer of actions
 * and waits for a tap; this one commits the act of the side it travelled to,
 * once past its threshold, and the row leaves. It claims the vertical pan, selects
 * no text and drags no picture, for the swipe row's reasons; a row that leaves
 * collapses before it goes. The gesture finds it by `.commitrow`.
 */
export const commitRow = cva(
  "commitrow relative overflow-hidden rounded-3 touch-pan-y select-none [&_img]:[-webkit-user-drag:none] " +
    "[&.gone]:[transition:height_var(--duration-3)_var(--ease-standard),opacity_var(--duration-2)_var(--ease-standard),margin_var(--duration-3)_var(--ease-standard)] " +
    "[&.gone]:[height:0]! [&.gone]:opacity-0 [&.gone]:mb-[calc(var(--spacing-7)*-1)]",
);

/**
 * What a commit row uncovers as it travels: on each side, the word of the act
 * that travel commits to — the right side read by a travel to the left, the left
 * side by a travel to the right. The words are the caller's.
 */
export const commitRowBack = cva(
  "commitback absolute inset-0 flex items-center justify-between py-0 px-8 rounded-3 bg-muted " +
    "text-muted-foreground text-3 font-bold [&_span]:flex [&_span]:items-center [&_span]:gap-3 " +
    "[&_svg]:w-[16px] [&_svg]:h-[16px] " +
    // THE SIDE THE ROW TRAVELS AWAY FROM IS NOT READ: the gesture writes which
    // way it goes, and the word under the fading card is hidden.
    "[[data-travel=left]>&>[data-side=left]]:invisible [[data-travel=right]>&>[data-side=right]]:invisible",
);

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
