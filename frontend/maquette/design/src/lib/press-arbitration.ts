// HOW A PRESS, A DRAG AND A SCROLL ARE TOLD APART.
//
// This is VOCABULARY (invariant 10): the arbitration itself, knowing nothing of
// panels, media or pages. What stays with a surface is WHICH gesture it offers
// — which element a press addresses and what opening it means — and that is the
// whole of what the two callbacks below carry.
//
// IT WAS MOVED HERE FROM `engine/legacy.js`, NOT REWRITTEN AND NOT REPLACED BY A
// LIBRARY. The behaviour is the engine's, proved by R55 against a real thumb
// before the move and after it; what changed is where it lives. D5's rule is
// that the engine dies by SUBTRACTION, so nothing was added to it — the block
// left, and the engine now imports what it used to define.
//
// ─────────────────────────────────────────────────────────────────────────────
// THE THREE THINGS A THUMB TAUGHT THAT A MOUSE NEVER DOES. Each one is a defect
// that shipped, and each is why the corresponding line is not simpler.
//
// 1. A THUMB IS NEVER STILL. Cancelling on the first `pointermove` cancelled
//    every press a real hand ever made; the timer only fired under a mouse,
//    which does hold still. It tolerates 12px. Measured: a drift of ±10px
//    holds, ±20px does not — and at ±20px the compositor claims the gesture
//    anyway, which is the right answer, because that is a scroll.
//
//    `pointercancel` is an ALLY here, not the enemy it is for a drag: the
//    compositor fires it only once the finger has really travelled, so it says
//    « this became a scroll » and the press must die. That is the OPPOSITE of a
//    drag, where it arrives on the first move and kills a gesture that was never
//    going to be a scroll — which is why one rule cannot serve both, and why
//    this module arbitrates a press and `drawer-gesture.ts` a drag.
//
// 2. THE TOLERANCE MUST LIVE ON THE POINTER STREAM. Chrome delivers NO
//    `touchmove` at all for a drift this small, only `pointermove`. A tolerance
//    written on the touch stream would never run. (The converse is equally
//    load-bearing and belongs to the drag: a pointer-only DRAG passes under a
//    real mouse and does nothing under a real thumb, because the compositor
//    stops delivering `pointermove` the moment it claims the gesture.)
//
// 3. THE CLICK IS SWALLOWED BY ITS POINT — not by a delay, and not by a target.
//    The panel opens UNDER the finger, so the click that follows the lift lands
//    on whatever is now there. On a 204px tile the panel's primary action sits
//    exactly under the thumb, and a long press on a follow fired « Récupérer
//    maintenant » before the panel had finished appearing.
//
//    The lift lands within the press's own tolerance of where it started —
//    beyond that the press was cancelled — so the click this press caused is
//    exactly the one that matches, and a deliberate tap somewhere else never
//    does. Measured: the click arrives 1 ms after the lift, which is why no
//    timer can tell them apart.
//
//    THAT SECOND HALF IS A REQUIREMENT AND NOT A SIDE EFFECT: an implementation
//    that swallowed every click after a press would satisfy « the lift does not
//    fire the panel » and break every deliberate tap. It is held separately.

import { feedback } from "./feedback";

/** The mark a press being ARMED writes. Read by `styles/base.css`. */
const PRESSING_ATTRIBUTE = "data-pressing";

/** How long the finger must stay down before a press is a press. */
const PRESS_MILLISECONDS = 480;

/** How far the finger may drift and still be pressing rather than scrolling. */
const PRESS_TOLERANCE_PIXELS = 12;

/** A point in client coordinates — where a finger landed or a click arrived. */
type Point = { readonly x: number; readonly y: number };

/** A press in flight: what it addresses, where it began, and its timer. */
type PressInFlight = {
  readonly element: Element;
  readonly x: number;
  readonly y: number;
  readonly pollTimer: number;
};

/**
 * What the caller must tell the arbitration, and it is only ever these two.
 *
 * Both are the SURFACE's business, which is why they are parameters rather than
 * knowledge this module holds: invariant 10 puts « which gesture a surface
 * offers » with the surface and « how a press, a drag and a scroll are told
 * apart » here.
 */
export type PressArbitrationOptions = {
  /**
   * Which element, if any, a press starting on `target` addresses.
   *
   * Returning `null` means « nothing here answers a press », and no timer is
   * armed. The caller decides what that means — a mode in which pressing is
   * disabled, a surface that already opens on a plain tap, or simply markup
   * that offers no press.
   */
  readonly resolveTarget: (target: Element) => Element | null;
  /** What opening the press means, once the finger has held long enough. */
  readonly onPress: (element: Element) => void;
};

/**
 * What the arbitration exposes about its own state, read live.
 *
 * The engine publishes these on `window` for the harness, which is a DRIVING
 * surface rather than a bridge between two worlds. They are getters because the
 * values are reassigned: a copy taken at install time would report the first
 * state forever.
 */
export type PressArbitration = {
  /** The press in flight, or `null` between gestures. */
  readonly press: PressInFlight | null;
  /** The point of a click that must be swallowed, or `null`. */
  readonly swallowClick: Point | null;
  /** Cancels a press in flight. Exposed because the engine's callers had it. */
  readonly cancelPress: () => void;
  /** Feeds a pointer position to a press in flight. */
  readonly followPress: (point: Point) => void;
};

/**
 * Installs the press arbitration on the document.
 *
 * Bound to `document`, not to the phone frame or the scrollport. Every layer
 * above the scrollport — sheet, screen, drawer, dialog — sits OUTSIDE it, and a
 * refusal bound to the scrollport left every card and poster drawn in one of
 * them offering the browser's own menu; eight named states draw one. `document`
 * is the one ancestor guaranteed either way, and both handlers already gate on
 * the target, so the wider root changes nothing for content that was never meant
 * to answer a press.
 *
 * Args:
 *     options: What the surface knows — which element a press addresses, and
 *         what opening it means.
 *
 * Returns:
 *     A live view of the arbitration's state, for a driving surface to publish.
 */
export function installPressArbitration(
  options: PressArbitrationOptions,
): PressArbitration {
  let press: PressInFlight | null = null;
  let swallowClick: Point | null = null;

  function cancelPress(): void {
    if (!press) return;
    clearTimeout(press.pollTimer);
    press.element.removeAttribute(PRESSING_ATTRIBUTE);
    press = null;
  }

  function armPress(point: Point, target: Element): void {
    const element = options.resolveTarget(target);
    if (!element) return;
    cancelPress();
    // THE PRESS ACKNOWLEDGEMENT'S STATE (operator, 2026-08-31). A long press
    // arms for 480ms before anything happens, and until now the interface said
    // nothing for that whole time. The element it armed on is marked, and the
    // stylesheet decides what that looks like — the name lives there, as every
    // drawing decision does (D9 rule 1).
    //
    // IT IS A THIRD MOMENT, and the three do not overlap: `:active` is the
    // finger being down at all (phase 5, CSS, no JavaScript), `data-feedback`
    // is the acknowledgement AFTER a gesture commits, and this is the span
    // between them — the press being armed. It is written by the arbitration
    // because the arbitration is the only thing that knows a press is arming;
    // that is a fact about the GESTURE, not about the surface, so it stays
    // vocabulary.
    element.setAttribute(PRESSING_ATTRIBUTE, "");
    press = {
      element,
      x: point.x,
      y: point.y,
      pollTimer: window.setTimeout(() => {
        // RELEASED AS THE PANEL ARRIVES, which is the gesture's own shape: the
        // tile is held down while the press arms and lets go the moment the
        // layer answers.
        element.removeAttribute(PRESSING_ATTRIBUTE);
        press = null;
        swallowClick = { x: point.x, y: point.y };
        // THROUGH THE SEAM, before the surface acts. Every gesture in the
        // interface passes through `feedback()` — one call site, so haptics
        // are one file's change the day the platform allows them (D9).
        //
        // ITS VISUAL HALF DOES NOT LAND HERE, AND THAT IS CORRECT. `onPress`
        // opens the panel, which re-renders the pressed surface: the marked
        // node is detached within the same frame — measured, `isConnected`
        // false while the mark still reads `commit`. So the mark is written and
        // never seen.
        //
        // It is not moved to a surviving ancestor, because THE PANEL APPEARING
        // UNDER THE FINGER IS THIS GESTURE'S ACKNOWLEDGEMENT. A pulse on top of
        // it would be a second answer to one gesture. What the call is FOR here
        // is the haptic half: this is exactly the gesture that should buzz, and
        // D9's whole point is that the day it can, one file changes.
        //
        // The rule holds it accordingly — that the seam is CALLED on a real
        // press, observed as the mark being set, rather than that a pulse is
        // visible where nothing should pulse.
        feedback("commit", element);
        options.onPress(element);
      }, PRESS_MILLISECONDS),
    };
  }

  function followPress(point: Point): void {
    if (!press) return;
    const distance = Math.hypot(point.x - press.x, point.y - press.y);
    if (distance > PRESS_TOLERANCE_PIXELS) cancelPress();
  }

  document.addEventListener(
    "pointerdown",
    (event) => {
      // A new gesture clears any mark the previous one left unconsumed.
      swallowClick = null;
      if (event.isPrimary && event.target instanceof Element) {
        armPress({ x: event.clientX, y: event.clientY }, event.target);
      }
    },
    { passive: true },
  );
  document.addEventListener(
    "pointermove",
    (event) => followPress({ x: event.clientX, y: event.clientY }),
    { passive: true },
  );
  // The mark is NEVER cleared on pointerup: for a real finger the click comes
  // 1 ms later, in a later task, so clearing there — even deferred by a
  // macrotask — clears it before the click it exists for.
  window.addEventListener("pointerup", cancelPress);
  window.addEventListener("pointercancel", () => {
    // The compositor claimed the gesture: it is a scroll, not a press — and no
    // click will follow it, so nothing is left waiting to be swallowed.
    cancelPress();
    swallowClick = null;
  });

  // The browser's own menu is refused wherever the interface answers a press.
  //
  // `user-select: none` stops a selection and `-webkit-touch-callout: none`
  // answers iOS Safari, and neither touches the menu Android raises: that one
  // comes from `contextmenu`, and nothing was refusing it. A long press on a
  // poster therefore offered « copier l'image » on top of — or instead of — the
  // panel the same press was opening.
  //
  // A text field keeps its menu: pasting into one has no other route, and the
  // interface offers nothing there of its own.
  document.addEventListener("contextmenu", (event) => {
    const target = event.target;
    if (
      target instanceof Element &&
      target.closest("input, textarea, [contenteditable]")
    ) {
      return;
    }
    event.preventDefault();
  });

  // A press that opened the panel must not ALSO fire what the lift lands on.
  document.addEventListener(
    "click",
    (event) => {
      if (!swallowClick) return;
      const distance = Math.hypot(
        event.clientX - swallowClick.x,
        event.clientY - swallowClick.y,
      );
      swallowClick = null;
      if (distance > PRESS_TOLERANCE_PIXELS) return;
      event.preventDefault();
      event.stopPropagation();
    },
    { capture: true },
  );

  return {
    get press() {
      return press;
    },
    get swallowClick() {
      return swallowClick;
    },
    cancelPress,
    followPress,
  };
}
