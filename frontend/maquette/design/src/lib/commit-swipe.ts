// THE COMMIT SWIPE — a row a finger throws to one side, and the act of that side.
//
// The application's second swipe, beside the drawer swipe (`swipe-arbitration.ts`),
// and different on purpose: the drawer swipe OPENS actions and waits for a tap;
// this one DECIDES on release. Past its threshold the row flies out and the side
// it travelled to is committed; short of it, the row comes back. Declared here so
// another surface can reuse it: what each side MEANS is its caller's, this module
// knows no domain (invariant 10).
//
// It CLAIMS ITS AXIS the swipe row's way — `touch-pan-y` on the row, so the
// browser does not take the gesture — and reads the axis once the finger has
// travelled past a dead zone.
//
// THE ONE CLASS IT WRITES IS `dragging`, the card's own contract
// (`ui/variants/card.ts`): a row follows the finger without easing. And it says
// which way the row travels in `data-travel`, so the back shows the word of that
// side alone — the fading card would otherwise let the other side's show through.

/** How far a finger travels before the gesture commits to an axis. */
const AXIS_DEAD_ZONE_PIXELS = 6;

/** How much more a drag must travel to the SIDE than down to be a swipe. */
const SIDE_OVER_DOWN = 1.2;

/** How far a row must travel to commit its side. */
const COMMIT_TRAVEL_PIXELS = 92;

/** How far it flies out once it does. */
const FLIGHT_PIXELS = 420;

/** How faint a dragged row is allowed to become. */
const MIN_OPACITY = 0.35;

/** Over how many pixels of travel it fades to that floor. */
const OPACITY_OVER_PIXELS = 260;

/** The class a card being dragged carries — `ui/variants/card.ts` reads it. */
const DRAG_MARK = "dragging";

/** What a caller binds: which rows answer, and what each side commits. */
export type CommitSwipe = {
  /** The selector of the rows the gesture answers on — the caller's own part. */
  rows: string;
  /** The act of a travel to the LEFT, handed the row. */
  onLeft: (row: HTMLElement) => void;
  /** The act of a travel to the RIGHT, handed the row. */
  onRight: (row: HTMLElement) => void;
};

type Drag = { row: HTMLElement; card: HTMLElement; x: number; y: number; axis: "x" | "y" | null; offset: number };

/**
 * Starts answering commit swipes on rows drawn inside one element.
 *
 * @param frame The element the rows are drawn inside.
 * @param swipe The rows, and what each side commits.
 */
export function installCommitSwipe(frame: HTMLElement, swipe: CommitSwipe): void {
  let drag: Drag | null = null;

  frame.addEventListener(
    "pointerdown",
    (event) => {
      const row = (event.target as HTMLElement).closest?.(swipe.rows);
      if (!(row instanceof HTMLElement) || !event.isPrimary) return;
      const card = row.querySelector('[data-part="card"]');
      if (card instanceof HTMLElement) drag = { row, card, x: event.clientX, y: event.clientY, axis: null, offset: 0 };
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
        if (Math.abs(deltaX) < AXIS_DEAD_ZONE_PIXELS && Math.abs(deltaY) < AXIS_DEAD_ZONE_PIXELS) return;
        drag.axis = Math.abs(deltaX) > Math.abs(deltaY) * SIDE_OVER_DOWN ? "x" : "y";
        if (drag.axis === "x") drag.card.classList.add(DRAG_MARK);
      }
      if (drag.axis !== "x") return;
      drag.offset = deltaX;
      drag.row.dataset.travel = deltaX < 0 ? "left" : "right";
      drag.card.style.transform = `translateX(${deltaX}px)`;
      // IT FADES AS IT GOES, so the gesture says « this is leaving » before the
      // finger has decided it is — never past the floor, because a row one can
      // no longer see is a row one cannot put back.
      drag.card.style.opacity = String(Math.max(MIN_OPACITY, 1 - Math.abs(deltaX) / OPACITY_OVER_PIXELS));
    },
    { passive: true },
  );

  const release = (): void => {
    if (!drag) return;
    const released = drag;
    drag = null;
    if (released.axis !== "x") return;
    released.card.classList.remove(DRAG_MARK);
    if (Math.abs(released.offset) > COMMIT_TRAVEL_PIXELS) {
      const left = released.offset < 0;
      released.card.style.transform = `translateX(${left ? -FLIGHT_PIXELS : FLIGHT_PIXELS}px)`;
      (left ? swipe.onLeft : swipe.onRight)(released.row);
      return;
    }
    released.card.style.transform = "";
    released.card.style.opacity = "";
    delete released.row.dataset.travel;
  };

  window.addEventListener("pointerup", release);
  window.addEventListener("pointercancel", release);
}
