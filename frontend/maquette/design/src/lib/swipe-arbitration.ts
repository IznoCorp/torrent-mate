// THE SWIPE — a drag born on a row belongs to the row.
//
// The shape of the gesture is vocabulary and vocabulary is not the engine's
// (invariant 10): the axis decision, the two drawers' travel, where a released
// row rests, and the click that must not follow a drag. What SURFACE offers a
// swipe, and what its actions do, is the feature's — this module is handed the
// element to listen on and knows nothing else.
//
// IT RUNS BOTH WAYS. The right drawer holds what one does TO a medium — pause
// it, drop it — and the left one holds the single thing the row is FOR, the
// action its footer already names. A row with no left drawer does not travel
// that way rather than opening an empty one.
//
// ONLY ONE ROW IS OPEN AT A TIME. Two open drawers ask which one an action
// belongs to, and the answer is never on screen, so a drag beginning anywhere
// puts the previous row back first.
//
// IT LISTENS ON THE FRAME, not the scrollport: every layer above it — the sheet,
// the screen, the drawer — sits outside, and a row drawn in one of them would
// answer no gesture at all.
//
// THE ANCHORS IT READS ARE IDENTITIES, never class names: `data-part="swipe"`
// for the row, `data-part="swipe/side"` with its `data-side` for a drawer, and
// `data-part="swipe/action"` for what a drawer holds. A class is a drawing
// decision and may change with the paint; an identity is a contract (R77).
//
// THE ONE CLASS IT WRITES IS `dragging`, and that one IS the contract: the
// card's variant carries `[&.dragging]:transition-none` (`ui/variants/card.ts`),
// so a row follows the finger without easing and eases again when released. A
// state the drawing reads by class is written by class.

/**
 * How wide one action is, in pixels.
 *
 * READ FROM THE DRAWING, and it cannot be measured instead: a drawer sits
 * behind the row at full height with its actions laid out inside, so its own
 * box is the row's width whatever it holds. The number is the `w-[84px]` the
 * action's variant paints, and the two move together.
 */
const ACTION_WIDTH_PIXELS = 84;

/** How far a finger travels before the gesture commits to an axis. */
const AXIS_DEAD_ZONE_PIXELS = 6;

/** How much more a drag must travel to the SIDE than down to be a swipe. */
const SIDE_OVER_DOWN = 1.2;

/** The fraction of a drawer's width past which a released row rests open. */
const OPEN_AT = 1 / 2.4;

/** The fraction of its own travel a row must come back before it closes. */
const CLOSE_AT = 2 / 3;

/** How far the FINGER must travel for the release's click to be swallowed. */
const DRAG_TRAVEL_PIXELS = 4;

/** How near that release a click must land to be the drag's own. */
const SWALLOW_RADIUS_PIXELS = 24;

/** The class a row being dragged carries — `ui/variants/card.ts` reads it. */
const DRAG_MARK = "dragging";

/** The row, its drawers and what a drawer holds, by identity. */
const ROW = '[data-part="swipe"]';
const CARD = '[data-part="card"]';
const SIDE = '[data-part="swipe/side"]';
const ACTION = '[data-part="swipe/action"]';

type Drag = {
  row: HTMLElement;
  card: HTMLElement;
  x: number;
  y: number;
  /** Where the row already rested when the finger landed on it. */
  from: number;
  axis: "x" | "y" | null;
  offset: number;
  lastX?: number;
  lastY?: number;
};

let drag: Drag | null = null;
let openCard: HTMLElement | null = null;
let openCardOffset = 0;
let clickAfterDrag: { x: number; y: number } | null = null;

/** The row resting open right now, if any — published for the harness. */
export function openRow(): HTMLElement | null {
  return openCard;
}

/** Whether a click is being swallowed as a drag's own — published for the harness. */
export function swallowClickMark(): { x: number; y: number } | null {
  return clickAfterDrag;
}

/** Puts the open row back, from a verb that has just acted on it. */
export function collapseOpenRow(): void {
  if (!openCard) return;
  openCard.style.transform = "";
  openCard = null;
  openCardOffset = 0;
}

/**
 * How wide the drawer on one side of a row is.
 *
 * @param row The swipe row.
 * @param direction Negative for the drawer uncovered by travelling left.
 * @returns Its width in pixels, zero when that side holds nothing.
 */
function drawerWidth(row: HTMLElement, direction: number): number {
  const side = row.querySelector(
    `${SIDE}[data-side="${direction < 0 ? "right" : "left"}"]`,
  );
  return side ? side.querySelectorAll(ACTION).length * ACTION_WIDTH_PIXELS : 0;
}

/**
 * Starts answering swipes on rows drawn inside one element.
 *
 * @param frame The element the rows are drawn inside — the frame, never the
 *     scrollport, so a row inside a layer is answered too.
 */
export function installSwipeArbitration(frame: HTMLElement): void {
  frame.addEventListener(
    "pointerdown",
    (event) => {
      clickAfterDrag = null;
      const row = (event.target as HTMLElement).closest?.(ROW);
      if (!(row instanceof HTMLElement) || !event.isPrimary) return;
      const card = row.querySelector(CARD);
      if (!(card instanceof HTMLElement)) return;
      // A new gesture anywhere puts the previously opened row back.
      if (openCard && openCard !== card) collapseOpenRow();
      drag = {
        row,
        card,
        x: event.clientX,
        y: event.clientY,
        from: openCard === card ? openCardOffset : 0,
        axis: null,
        offset: 0,
      };
    },
    { passive: true },
  );

  frame.addEventListener(
    "pointermove",
    (event) => {
      if (!drag) return;
      const deltaX = event.clientX - drag.x;
      const deltaY = event.clientY - drag.y;
      if (drag.axis === null) {
        if (Math.abs(deltaX) < AXIS_DEAD_ZONE_PIXELS && Math.abs(deltaY) < AXIS_DEAD_ZONE_PIXELS)
          return;
        drag.axis = Math.abs(deltaX) > Math.abs(deltaY) * SIDE_OVER_DOWN ? "x" : "y";
        if (drag.axis === "x") drag.card.classList.add(DRAG_MARK);
      }
      if (drag.axis !== "x") return;
      const asked = drag.from + deltaX;
      drag.lastX = event.clientX;
      drag.lastY = event.clientY;
      /* AN OPEN ROW CAN ONLY BE CLOSED by a drag. Its travel is clamped between
         where it rests and zero, so a swipe the other way settles it back
         rather than crossing rest and opening the opposite drawer within the
         same gesture. Reaching the other side is a second, deliberate swipe —
         the row has to have come back first. */
      drag.offset = drag.from
        ? Math.min(Math.max(asked, Math.min(drag.from, 0)), Math.max(drag.from, 0))
        : Math.max(
            -drawerWidth(drag.row, -1),
            Math.min(drawerWidth(drag.row, 1), asked),
          );
      drag.card.style.transform = `translateX(${drag.offset}px)`;
    },
    { passive: true },
  );

  const release = (): void => {
    if (!drag) return;
    const released = drag;
    drag = null;
    if (released.axis !== "x") return;
    released.card.classList.remove(DRAG_MARK);
    const left = drawerWidth(released.row, 1);
    const right = drawerWidth(released.row, -1);
    let rest = 0;
    if (released.from) {
      // Closing an open row takes a third of its own travel, so a thumb
      // brushing past one does not shut what it came to use.
      rest = Math.abs(released.offset) > Math.abs(released.from) * CLOSE_AT ? released.from : 0;
    } else if (released.offset < -right * OPEN_AT) rest = -right;
    else if (released.offset > left * OPEN_AT) rest = left;
    released.card.style.transform = rest ? `translateX(${rest}px)` : "";
    openCard = rest ? released.card : null;
    openCardOffset = rest;
    /* ARMED ON WHAT THE FINGER TRAVELLED, never on what the row moved.

       The guard exists to tell a drag from a tap, and that distinction belongs
       to the pointer: a row is free to refuse to move — a list with no left
       drawer does exactly that — and measuring its displacement turns every
       such drag into a tap. Both ways in were measured: a right drag on a row
       with no left drawer has always ended at zero, and an open row dragged
       further the same way ends where it started. Both armed nothing, so the
       click went through and the panel opened over the row.

       Only a MOUSE ever showed it: after a touch drag the browser suppresses
       the click itself, so every finger measurement was green over the hole —
       which is why the hold asserts the click was actively SWALLOWED rather
       than that no panel appeared. */
    const travelled = Math.hypot(
      (released.lastX ?? released.x) - released.x,
      (released.lastY ?? released.y) - released.y,
    );
    clickAfterDrag =
      travelled > DRAG_TRAVEL_PIXELS
        ? { x: released.lastX ?? released.x, y: released.lastY ?? released.y }
        : null;
  };
  window.addEventListener("pointerup", release);
  window.addEventListener("pointercancel", release);

  /* THE CLICK THAT ENDS A DRAG IS NOT A TAP, and saying so takes
     `stopImmediatePropagation`.

     `stopPropagation` stops the listeners on other NODES, and that was enough
     while the taps it had to outrun were answered by one delegation in the
     BUBBLE phase. They are answered by the tap registry now (`lib/verbs.ts`),
     which listens in CAPTURE on this very node — a listener BESIDE this one,
     which propagation does not reach. Registered first, this one stops it; and
     it stops nothing else, because it only ever fires on the click that lands
     where a drag was just released. */
  document.addEventListener(
    "click",
    (event) => {
      if (!clickAfterDrag) return;
      const mark = clickAfterDrag;
      clickAfterDrag = null;
      if (Math.hypot(event.clientX - mark.x, event.clientY - mark.y) > SWALLOW_RADIUS_PIXELS)
        return;
      event.preventDefault();
      event.stopImmediatePropagation();
    },
    { capture: true },
  );
}
