// A PULL FROM THE TOP OF A SCROLLPORT — and it knows nothing of what refreshes.
//
// VOCABULARY (invariant 10). `MODEL.md` Part 8 places it exactly: « a gesture on
// `#port` that knows nothing of what refreshes — it moves with the gesture
// vocabulary in L12 ». What stays with the surface is what a completed pull
// MEANS: drawing an indicator, asking a server, saying « Actualisé ». This
// module decides only whether the finger is pulling, how far, and whether it
// travelled far enough.
//
// MOVED FROM `engine/legacy.js`, NOT REWRITTEN. Its behaviour is the engine's
// and R55 proves it against a real touch stream on seven surfaces, before the
// move and after it. D5: the engine dies by SUBTRACTION, so nothing was added
// to it — the block left and an import took its place.
//
// ─────────────────────────────────────────────────────────────────────────────
// WHY IT READS TOUCH EVENTS AND POINTER EVENTS BOTH, and it is the same lesson
// `drawer-gesture.ts` records at length.
//
// The compositor takes gestures away: the moment it decides a drag is a scroll
// it fires `pointercancel` and stops delivering `pointermove` for that pointer
// — measured on this very gesture, in the engine's own note: one move
// delivered, then cancel, while ten `touchmove` keep arriving for the same
// finger. So a pointer-only implementation works perfectly under synthetic
// events, which are never cancelled, and does NOTHING at all under a real
// thumb.
//
// A mouse, meanwhile, produces no touch events at all. Hence both, with the
// pointer path ignoring `pointerType === "touch"` so the same finger is not
// counted twice — reading it twice would double every delta.
//
// THE AXIS IS CLAIMED ONCE, at 8px, and never revised. A gesture that re-decided
// its axis mid-travel would flicker between scrolling and pulling on any
// diagonal movement, which is most of them.

import { feedback } from "./feedback";

/** How far the finger must travel before the gesture commits to an axis. */
const AXIS_DECISION_PIXELS = 8;

/** The iOS back-swipe dead zone at the left edge, which is not ours to take. */
const EDGE_DEAD_ZONE_PIXELS = 30;

/** How far the pull may travel, however far the finger does. */
const PULL_CAP_PIXELS = 72;

/** How much of the finger's travel the pull follows — the gesture's weight. */
const PULL_DAMPING = 0.45;

/** How far the pull must come before releasing it means anything. */
const PULL_ARM_PIXELS = 44;

/** A pull in flight. */
type PullInFlight = {
  readonly x: number;
  readonly y: number;
  axis: "x" | "y" | null;
  readonly atTop: boolean;
};

/** What the surface tells the gesture, and what it wants told back. */
export type PullGestureOptions = {
  /** The scrollport the gesture lives on. */
  readonly port: HTMLElement;
  /**
   * Whether a gesture starting on `target` belongs to something else.
   *
   * The SURFACE's business, not this module's: a drag born on a deck card
   * belongs to the card, and without this the page handler fires too and
   * navigates away mid-gesture.
   */
  readonly isExcluded: (target: Element) => boolean;
  /** How far the pull has come, and whether that is far enough. */
  readonly onPull: (pulled: number, armed: boolean) => void;
  /** The finger lifted. `armed` says whether it travelled far enough. */
  readonly onRelease: (armed: boolean) => void;
};

/** What the caller keeps, so a surface can put the gesture back to rest. */
export type PullGesture = {
  /**
   * Abandons a pull in flight without releasing it.
   *
   * A refresh in flight outlives a change of state, so a measurement would
   * otherwise inherit the previous one's gesture — which is exactly how a first
   * pass at this reported it working on half the surfaces and broken on the
   * other half, in alternation.
   */
  readonly reset: () => void;
};

/**
 * Installs the pull gesture on a scrollport.
 *
 * Args:
 *     options: The port, what to ignore, and what to do as the pull travels
 *         and when it is released.
 *
 * Returns:
 *     A handle carrying `reset`.
 */
export function installPullGesture(options: PullGestureOptions): PullGesture {
  const { port } = options;
  let pull: PullInFlight | null = null;

  // The same driving surface the press arbitration publishes, for the same
  // reason: a rule that re-types 44 is a second source of truth.
  window.__gestures = {
    ...(window.__gestures ?? {}),
    pull: {
      armPixels: PULL_ARM_PIXELS,
      capPixels: PULL_CAP_PIXELS,
      damping: PULL_DAMPING,
    },
  };
  // How far the pull has actually come, damped and capped. The release reads
  // it rather than recomputing from the finger: one arithmetic, one place.
  let travelled = 0;

  // Where the finger stands NOW, on the vertical axis. `travelled` is a
  // high-water mark; this is a direction, and the release needs both.
  let lastDeltaY = 0;

  function start(point: { clientX: number; clientY: number }, target: Element): void {
    if (options.isExcluded(target)) {
      pull = null;
      return;
    }
    // The left edge belongs to the platform's own back gesture.
    if (point.clientX - port.getBoundingClientRect().left < EDGE_DEAD_ZONE_PIXELS) {
      pull = null;
      return;
    }
    travelled = 0;
    lastDeltaY = 0;
    pull = {
      x: point.clientX,
      y: point.clientY,
      axis: null,
      // READ AT THE START, not at the release. A pull that begins at the top
      // and scrolls away is not a pull, and asking at the end would answer
      // about wherever the finger finished.
      atTop: port.scrollTop <= 0,
    };
  }

  function advance(point: { clientX: number; clientY: number }): void {
    if (!pull) return;
    const deltaX = point.clientX - pull.x;
    const deltaY = point.clientY - pull.y;
    if (pull.axis === null) {
      if (
        Math.abs(deltaX) < AXIS_DECISION_PIXELS &&
        Math.abs(deltaY) < AXIS_DECISION_PIXELS
      ) {
        return;
      }
      pull.axis = Math.abs(deltaX) > Math.abs(deltaY) ? "x" : "y";
    }
    // THE FINGER'S CURRENT DIRECTION IS REMEMBERED, not just its furthest
    // travel. A pull that goes down and comes back UP past where it started is
    // not a pull any more, and releasing it must refresh nothing.
    //
    // The engine checked exactly this at the release — `drag.dy > 0` on the
    // FINAL delta, beside the armed class — and the first version of this
    // module dropped it: `travelled` kept whatever the deepest point had set,
    // because the guard below returns early without touching it, so a pull
    // dragged back up still released armed. Caught by reading the code this
    // replaced against the code that replaced it.
    lastDeltaY = deltaY;
    if (pull.axis !== "y" || !pull.atTop || deltaY <= 0) return;
    travelled = Math.min(PULL_CAP_PIXELS, deltaY * PULL_DAMPING);
    options.onPull(travelled, travelled >= PULL_ARM_PIXELS);
  }

  function end(): void {
    const finished = pull;
    pull = null;
    if (!finished) return;
    // A HORIZONTAL GESTURE RELEASES NOTHING. There is no horizontal page
    // gesture and its absence is the decision: swiping the scrollport used to
    // change tab or lens and fired by accident constantly — every horizontal
    // component of a vertical scroll, every aborted row swipe.
    if (finished.axis !== "y") return;
    const armed = lastDeltaY > 0 && travelled >= PULL_ARM_PIXELS;
    // THROUGH THE SEAM, like every other gesture — one call site, so haptics
    // are one file's change the day the platform allows them (D9). This gesture
    // was the one that never joined it: `check-feedback-seam` named the press,
    // the drawer and the sheet, and « one call site ALL gestures pass through »
    // was false from the day the guard shipped.
    //
    // NO ELEMENT, and that is the honest form rather than an omission: the
    // pull's visible acknowledgement is the indicator the surface draws, and a
    // second mark on the scrollport would be a second answer to one gesture —
    // the same reasoning the press records at its own call. What crosses here
    // is the haptic half.
    if (armed) feedback("commit");
    options.onRelease(armed);
    travelled = 0;
    lastDeltaY = 0;
  }

  port.addEventListener(
    "touchstart",
    (event) => {
      if (event.touches.length !== 1) {
        pull = null;
        return;
      }
      const target = event.target;
      if (target instanceof Element) start(event.touches[0], target);
    },
    { passive: true },
  );
  port.addEventListener(
    "touchmove",
    (event) => {
      if (event.touches.length !== 1) return;
      advance(event.touches[0]);
    },
    { passive: true },
  );
  port.addEventListener(
    "pointerdown",
    (event) => {
      // The same finger also arrives as a pointer event. Reading it twice
      // would double every delta.
      if (event.pointerType === "touch") return;
      if (!event.isPrimary) {
        pull = null;
        return;
      }
      if (event.target instanceof Element) start(event, event.target);
    },
    { passive: true },
  );
  port.addEventListener(
    "pointermove",
    (event) => {
      if (event.pointerType === "touch") return;
      advance(event);
    },
    { passive: true },
  );
  // THE LIFT IS READ ON THE WINDOW, not the port. A finger that leaves the
  // scrollport still ends the gesture, and a release nobody heard leaves the
  // indicator hanging half-open.
  window.addEventListener("touchend", end);
  window.addEventListener("touchcancel", end);
  window.addEventListener("pointerup", (event) => {
    if (event.pointerType !== "touch") end();
  });
  // `pointercancel` IS IGNORED FOR A FINGER, AND THAT IS THE WHOLE POINT.
  //
  // It arrives as soon as the browser claims the pan — one move in — while the
  // touch stream carrying the gesture keeps running. Ending on it would undo
  // the very thing that makes this gesture work under a real thumb, and it is
  // the OPPOSITE of the press arbitration next door, where `pointercancel` is
  // an ally because the compositor only fires it once the finger has really
  // travelled. One rule cannot serve both, which is why there are two modules.
  //
  // Carried over verbatim from the engine, where it was written down after the
  // gesture had been lost to exactly this. A first draft of this module
  // cancelled on it unconditionally and would have shipped that loss back.
  window.addEventListener("pointercancel", (event) => {
    if (event.pointerType !== "touch") {
      // RELEASED, NOT MERELY FORGOTTEN — and the difference is visible on
      // screen. Clearing the three variables ends the gesture's BOOKKEEPING and
      // tells the surface nothing, so the indicator stays at the height the
      // cancelled pull left it, with its transition suppressed and its armed
      // state on: a mouse or a stylus cancelled mid-pull hung the indicator
      // open until the next gesture. The engine called its release here, which
      // is why this module claimed to carry the behaviour over verbatim and did
      // not.
      //
      // Zeroing the last delta BEFORE releasing is what makes the release
      // unarmed: a cancelled gesture is not a gesture the reader completed, so
      // it commits nothing. `end()` clears the rest.
      lastDeltaY = 0;
      end();
    }
  });

  return {
    reset: () => {
      pull = null;
      travelled = 0;
      lastDeltaY = 0;
    },
  };
}
