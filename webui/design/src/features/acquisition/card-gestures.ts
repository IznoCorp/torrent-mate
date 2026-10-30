// THE TWO GESTURES DÉCOUVRIR OFFERS, bound where what they mean is known.
//
// In the LIST and on the DECK alike (the operator's Q7): a travel to the LEFT
// PASSES — the suggestion leaves, no notification, and comes round again at the
// back of the one order both views read; a travel to the RIGHT REJECTS — it
// leaves, and the notification offers « Annuler ». The deck is animated rather
// than rebuilt so the card underneath rises instead of appearing, and keeps its
// own pile here; the list is the design system's commit row, its mechanics in
// `lib/commit-swipe.ts` — what each side MEANS for a suggestion stays here, this
// feature's own business and nobody else's.
//
// THEY CLAIM THEIR AXIS in `touch-action` (`pan-y` on the row and on the deck),
// which is what keeps the browser from taking the gesture and cancelling it at
// the first pixel — the reason the pull gesture, inside the scrollport, cannot
// use the pointer path at all.
import i18next from "i18next";
import { advanceDeck, dismissSug, fillSug, forgetDrawnFeed, passerSug, refreshDeck, sugFoot } from "./discover-feed";
import { installCommitSwipe } from "../../lib/commit-swipe";
import type { Suggestion } from "./discover-cards";
import { suggestions } from "./queries";
import { store } from "../../lib/store-access";
import { toast } from "../../lib/shell-doors";

/** How far a finger travels before either gesture commits to an axis. */
const AXIS_DEAD_ZONE_PIXELS = 6;

/** How much more a drag must travel to the SIDE than down to be a swipe. */
const SIDE_OVER_DOWN = 1.2;

/** How far a deck drag travels before its hint appears at all. */
const HINT_DEAD_ZONE_PIXELS = 20;

/** Over how many further pixels the hint reaches full strength. */
const HINT_OVER_PIXELS = 70;

/** How far a DECK card must travel to leave the pile. */
const DECK_TRAVEL_PIXELS = 88;

/** How many pixels of travel turn the deck card by one degree. */
const DECK_PIXELS_A_DEGREE = 26;

/** The class a card being dragged carries — `ui/variants/card.ts` reads it. */
const DRAG_MARK = "dragging";

const WRAP = '[data-part="suggestion/wrap"]';
const DECK_CARD = '[data-part="deck/card"]';

type Drag = {
  /** The element the finger landed in — the deck card itself. */
  held: HTMLElement;
  card: HTMLElement;
  x: number;
  y: number;
  axis: "x" | "y" | null;
  offset: number;
};

/**
 * Reads the axis a drag has committed to, the first time it travels far enough.
 *
 * @param drag The drag in flight.
 * @param deltaX How far the finger has travelled across.
 * @param deltaY How far it has travelled down.
 * @returns Whether the drag is a horizontal one, and may be drawn.
 */
function takesTheAxis(drag: Drag, deltaX: number, deltaY: number): boolean {
  if (drag.axis === null) {
    if (Math.abs(deltaX) < AXIS_DEAD_ZONE_PIXELS && Math.abs(deltaY) < AXIS_DEAD_ZONE_PIXELS)
      return false;
    drag.axis = Math.abs(deltaX) > Math.abs(deltaY) * SIDE_OVER_DOWN ? "x" : "y";
    if (drag.axis === "x") drag.card.classList.add(DRAG_MARK);
  }
  return drag.axis === "x";
}

/**
 * « Passer », from the list: the suggestion goes to the back of the one order,
 * and the list is drawn again from it — no notification, it comes round again.
 *
 * @param row The row thrown to the left.
 */
function passListRow(row: HTMLElement): void {
  passerSug(Number(row.dataset.dismissable));
  forgetDrawnFeed();
  fillSug();
  sugFoot();
}

/**
 * Binds the two swipes Découvrir offers, inside one element.
 *
 * @param frame The element the surfaces are drawn inside.
 */
export function installDiscoverSwipe(frame: HTMLElement): void {
  let deckDrag: Drag | null = null;

  // THE LIST: the design system's commit row, each side meaning what it means here.
  installCommitSwipe(frame, {
    rows: WRAP,
    onLeft: passListRow,
    onRight: (row) => dismissSug(Number(row.dataset.dismissable)),
  });

  frame.addEventListener(
    "pointerdown",
    (event) => {
      const target = event.target as HTMLElement;
      const deckCard = target.closest?.(DECK_CARD);
      if (deckCard instanceof HTMLElement && event.isPrimary)
        deckDrag = {
          held: deckCard,
          card: deckCard,
          x: event.clientX,
          y: event.clientY,
          axis: null,
          offset: 0,
        };
    },
    { passive: true },
  );

  frame.addEventListener(
    "pointermove",
    (event) => {
      if (!deckDrag) return;
      const deltaX = event.clientX - deckDrag.x;
      const deltaY = event.clientY - deckDrag.y;
      if (!takesTheAxis(deckDrag, deltaX, deltaY)) return;
      deckDrag.offset = deltaX;
      // The card TURNS as it travels, so what leaves the pile reads as a card
      // being pulled off a deck rather than a panel sliding.
      deckDrag.card.style.transform =
        `translateX(${deltaX}px) rotate(${deltaX / DECK_PIXELS_A_DEGREE}deg)`;
      /* THE TWO HINTS ARE READ BY THEIR OWN CLASSES, and that is not a lapse:
         `deckHint` (this feature's `variants.ts`) paints `dhint` with `l` and
         `r` for the sides, and this module is the same feature reading its own
         drawing. Nothing crosses a layer here. */
      const left = deckDrag.card.querySelector(".dhint.l");
      const right = deckDrag.card.querySelector(".dhint.r");
      /* ONE HINT AT A TIME, and it appears only once the travel is past the
         dead zone: a hint fading in under 20px of movement reads as a flicker
         rather than an answer. The other side is cleared outright, so a drag
         that changes its mind never shows both verbs. */
      const shown = String(
        Math.min(1, Math.max(0, (Math.abs(deltaX) - HINT_DEAD_ZONE_PIXELS) / HINT_OVER_PIXELS)),
      );
      if (left instanceof HTMLElement) left.style.opacity = deltaX < 0 ? shown : "0";
      if (right instanceof HTMLElement) right.style.opacity = deltaX > 0 ? shown : "0";
    },
    { passive: true },
  );

  const releaseDeck = (): void => {
    if (!deckDrag) return;
    const released = deckDrag;
    deckDrag = null;
    released.card.classList.remove(DRAG_MARK);
    if (released.axis !== "x") return;
    const position = Number(released.card.dataset.deck);
    if (Math.abs(released.offset) > DECK_TRAVEL_PIXELS) {
      if (released.offset > 0) {
        /* THE PILE IS ANIMATED, NOT REBUILT: `advanceDeck` moves the existing
           nodes, which is the only way the card underneath can rise rather than
           appear. The state is updated alongside, and the bump is explicit so
           the components learn the card left the deck. */
        (store.read().state.sugGone as Set<number>).add(position);
        store.touch();
        advanceDeck(position, 1);
        const gone = (suggestions?.() ?? [])[position] as Suggestion | undefined;
        toast?.show({
          message: i18next.t("discover.dismissed", { title: gone?.title ?? "" }),
          undo: () => {
            (store.read().state.sugGone as Set<number>).delete(position);
            store.touch();
            refreshDeck();
          },
        });
      } else {
        passerSug(position);
        advanceDeck(position, -1);
      }
      return;
    }
    released.card.style.transform = "";
    released.card
      .querySelectorAll(".dhint")
      .forEach((hint) => ((hint as HTMLElement).style.opacity = "0"));
  };

  window.addEventListener("pointerup", releaseDeck);
  window.addEventListener("pointercancel", releaseDeck);
}
