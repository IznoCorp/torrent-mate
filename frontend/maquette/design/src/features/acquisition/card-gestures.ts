// THE TWO GESTURES DÉCOUVRIR OFFERS, bound where what they mean is known.
//
// A suggestion in the list is DISMISSED by a swipe either way; a card on the
// deck is dismissed to the left and « passed » to the right, and the pile is
// animated rather than rebuilt so the card underneath rises instead of
// appearing. Both were listeners in the engine, beside the swipe row's; the
// row's SHAPE is vocabulary and lives in `lib/`, but these two are not a shape
// — each one decides what leaving the screen MEANS for a suggestion, which is
// this feature's own business and nobody else's.
//
// THEY CLAIM THEIR AXIS in `touch-action` (`pan-y` on the wrap and on the deck),
// which is what keeps the browser from taking the gesture and cancelling it at
// the first pixel — the reason the pull gesture, inside the scrollport, cannot
// use the pointer path at all.
import i18next from "i18next";
import { advanceDeck, dismissSug, passerSug, refreshDeck } from "./discover-feed";
import type { Suggestion } from "./discover-cards";
import { suggestions } from "./queries";
import { store } from "../../lib/store-access";
import { toast } from "../../lib/shell-doors";

/** How far a finger travels before either gesture commits to an axis. */
const AXIS_DEAD_ZONE_PIXELS = 6;

/** How much more a drag must travel to the SIDE than down to be a swipe. */
const SIDE_OVER_DOWN = 1.2;

/** How far a suggestion in the LIST must travel to be dismissed. */
const LIST_TRAVEL_PIXELS = 92;

/** How far it flies out once it is. */
const LIST_FLIGHT_PIXELS = 420;

/** How faint a dragged suggestion is allowed to become. */
const LIST_MIN_OPACITY = 0.35;

/** Over how many pixels of travel it fades to that floor. */
const LIST_OPACITY_OVER_PIXELS = 260;

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
  /** The element the finger landed in — the wrap, or the deck card itself. */
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
 * Binds the two swipes Découvrir offers, inside one element.
 *
 * ONE INSTALL FOR BOTH, because they share the pointer stream and the axis
 * reading: two installs would each add a `pointermove` listener to the same
 * element and decide the same axis twice.
 *
 * @param frame The element the surfaces are drawn inside.
 */
export function installDiscoverSwipe(frame: HTMLElement): void {
  let listDrag: Drag | null = null;
  let deckDrag: Drag | null = null;

  frame.addEventListener(
    "pointerdown",
    (event) => {
      const target = event.target as HTMLElement;
      const wrap = target.closest?.(WRAP);
      if (wrap instanceof HTMLElement && event.isPrimary) {
        const card = wrap.querySelector('[data-part="card"]');
        if (card instanceof HTMLElement)
          listDrag = { held: wrap, card, x: event.clientX, y: event.clientY, axis: null, offset: 0 };
        return;
      }
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
      if (listDrag) {
        const deltaX = event.clientX - listDrag.x;
        const deltaY = event.clientY - listDrag.y;
        if (!takesTheAxis(listDrag, deltaX, deltaY)) return;
        listDrag.offset = deltaX;
        listDrag.card.style.transform = `translateX(${deltaX}px)`;
        // IT FADES AS IT GOES, so the gesture says « this is leaving » before
        // the finger has decided it is — and never past the floor, because a
        // card one can no longer see is a card one cannot put back.
        listDrag.card.style.opacity = String(
          Math.max(LIST_MIN_OPACITY, 1 - Math.abs(deltaX) / LIST_OPACITY_OVER_PIXELS),
        );
        return;
      }
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

  const releaseList = (): void => {
    if (!listDrag) return;
    const released = listDrag;
    listDrag = null;
    if (released.axis !== "x") return;
    released.card.classList.remove(DRAG_MARK);
    if (Math.abs(released.offset) > LIST_TRAVEL_PIXELS) {
      released.card.style.transform =
        `translateX(${released.offset > 0 ? LIST_FLIGHT_PIXELS : -LIST_FLIGHT_PIXELS}px)`;
      dismissSug(Number(released.held.dataset.dismissable));
    } else {
      released.card.style.transform = "";
      released.card.style.opacity = "";
    }
  };

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

  window.addEventListener("pointerup", releaseList);
  window.addEventListener("pointercancel", releaseList);
  window.addEventListener("pointerup", releaseDeck);
  window.addEventListener("pointercancel", releaseDeck);
}
