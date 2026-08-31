// THE MENU CLOSES ON A LEFTWARD SWIPE FROM ITS RIGHT EDGE (E-002).
//
// Requested by the operator on 2026-08-28 as a hand-drawn mark on a 1200x2670
// screenshot: a band ending exactly on the drawer's right edge, about a quarter
// of its width. The drawer is `w-[288px]`, so the band is written as 72px — an
// arbitrary value, because a grip zone is not a spacing step and the scale
// stops at 24px (`styles/theme.css`).
//
// WHY THIS IS NOT A D5 VIOLATION, and it is the reason the file exists at all.
// `index.html` declares `<aside class="drawer …" id="drawer">` EMPTY; the dying
// engine fills it, opens it and closes it. Writing the gesture into
// `legacy.js` would be an ADDITION, and D5 allows only subtraction. So this
// installs from the React side against the node as it stands — the same posture
// `installFocusManager()` takes, which watches `data-open` on `#drawer` and
// « asks nothing of the engine: it watches the attribute both worlds already
// emit ». ZERO LINES ARE ADDED TO THE ENGINE.
//
// CLOSING GOES THROUGH THE SEAM THE SCRIM ALREADY USES. `window.__closeLayers`
// is published by the engine and called by `ui/sheet.tsx`'s scrim; the layer
// ladder is drawer → screen → sheet, so with the drawer open it closes the
// drawer. A second closing path would be a second navigation history.
//
// THE FINGER IS READ FROM TOUCH EVENTS AND EVERYTHING ELSE FROM POINTER EVENTS,
// and one implementation serves both. This is not a preference — a pointer-only
// version of this gesture was written first, it PASSED under a real mouse, and
// it did nothing at all under a real touch stream. R98 caught it because it
// drives `Input.dispatchTouchEvent` rather than `mouse.move`, and the trace is
// unambiguous: `pointerdown`, ONE `pointermove`, then `pointercancel`, while
// the `touchmove` events kept arriving for the same finger.
//
// The engine had already paid for this and written it down, three thousand
// lines into `legacy.js`, about its own pull-to-refresh: « the moment it decides
// a drag is a scroll it fires `pointercancel` and stops delivering
// `pointermove` for that pointer — measured: one move delivered, then cancel,
// while ten `touchmove` arrive for the same finger. A pointer-only
// implementation therefore works under synthetic events, which are never
// cancelled, and does nothing at all under a real thumb. » Neither
// `touch-action: pan-y` nor `touch-none` on the drawer changed it, measured
// both ways.
//
// `touch-pan-y` stays on the drawer in `index.html` all the same: the menu may
// grow long enough to scroll, and the band claims the horizontal only. Being
// compositor-facing, `check-compositor-css.py` is what holds it.
//
// TWO MORE THINGS RIDE THAT SAME CLASS, and both were missing until an
// adversarial review measured them in a browser.
//
// The transition is neutralised inline. The class this file used to add was
// written to cancel it « exactly as the sheet's does », and cancelled
// nothing: the sheet has a rule in `legacy.css` and the drawer had none,
// so the 300 ms transition stayed in force for the whole drag. Measured: the
// drawer lagged 40 to 53 px behind the finger and never caught up — 38 %. The
// comment described a mechanism that did not exist, which is worse than no
// comment, and « the drawer FOLLOWS THE FINGER » was false as shipped.
//
// `select-none` and `-webkit-user-drag:none` on its links. All six `<a>` of the
// menu cover the band, and a mouse drag beginning on one starts the browser's
// own link-drag: `pointerdown`, one `pointermove`, `dragstart`, `pointercancel`
// — the SAME signature as the touch failure above, from a different cause, and
// the gesture died on five sixths of the band. The engine had paid for this one
// too and written the remedy down (`legacy.css:578-587`, about dragging a
// picture): « it swallows the pointer stream outright … invisible to a touch
// test, fatal to a mouse one. » R98 stayed green because its mouse hold drags at
// the drawer's vertical middle, which happens to fall in the gap between two
// links — one coordinate, chosen geometrically, and the only one that worked.
//
// THE TOUCH LISTENERS ARE PASSIVE, like the engine's, and nothing here needs
// `preventDefault`: the drawer scrolls on neither axis today, so there is no
// browser gesture to suppress — only one to stop believing in.
//
// EVERY POINT BELOW WAS PAID FOR SOMEWHERE ELSE FIRST
// The band, ending on the drawer's right edge. Measured at ~67px on the
// operator's mark; 72 is the round number, written as an arbitrary value
// because a grip zone is not a spacing step and the scale stops at 24px
// (`styles/theme.css`). A finger confirms it or moves it.
import { feedback } from "../lib/feedback";

const BAND = 72;

// How far the drawer must travel before the lift closes it. The sheet uses 70
// on its own axis and this reuses it: a different threshold per axis can be
// justified, and it cannot be guessed.
const CLOSE_THRESHOLD = 70;

type Drag = { x: number; dx: number };

/**
 * Watches `#drawer` and closes it on a leftward drag begun at its right edge.
 *
 * Installed once, with the rest of the shell. It attaches to the node the
 * engine owns and mutates nothing the engine reads: the only thing it writes is
 * an inline transition and an inline transform, both removed when the gesture
 * ends.
 */
export function installDrawerDismissGesture(): void {
  const drawer = document.querySelector<HTMLElement>("#drawer");
  if (!drawer) return;

  let drag: Drag | null = null;

  function isOpen(): boolean {
    // `data-open`, not `.open`. Both are on the node, and the class is the one
    // that PAINTS — which is why invariant 2 refuses a rule anchored on it and
    // why this reads the attribute instead. It is also the attribute
    // `installFocusManager()` watches, so the two installers agree about what
    // « open » means rather than each deciding.
    return drawer!.hasAttribute("data-open");
  }

  /** Says whether a gesture starting here is this gesture. */
  function inBand(clientX: number): boolean {
    // MEASURED FROM THE DRAWER'S RIGHT EDGE, not from the viewport: the drawer
    // is `max-w-[86%]`, so on a narrow frame its edge is not at 288.
    return clientX >= drawer!.getBoundingClientRect().right - BAND;
  }

  function begin(clientX: number): void {
    if (!isOpen() || !inBand(clientX)) return;
    drag = { x: clientX, dx: 0 };
    // THE TRANSITION IS NEUTRALISED INLINE, not through a class, and the class
    // this used to add cancelled nothing. `.sheet.dragging` is a rule in
    // `legacy.css`; `.drawer` had none, so the 300 ms transition stayed in
    // force for the whole drag and the drawer lagged 40-53 px behind the finger
    // — measured, 38 %. A comment claiming a mechanism that does not exist is
    // worse than no comment.
    //
    // WHY INLINE RATHER THAN A RULE, and both alternatives were tried and
    // refused by a guard that was right. A `.drawer.dragging` rule beside its
    // twin GROWS `legacy.css`, and the residue may only shrink — it is an
    // exception with a date of death. An arbitrary variant on the drawer's own
    // class makes Tailwind generate that class name as a utility, and
    // `check-tailwind-confinement.py` refuses that: `DECLARED_COLLISIONS` is
    // empty on purpose, because a colliding name does not override one property,
    // it brings its WHOLE rule — the `grid` incident, 250 oracle divergences.
    //
    // So it is written where the transform is already written: on the element,
    // in the same task as the gesture's first event, which is what the timing
    // needs anyway.
    drawer!.style.transition = "none";
  }

  function advance(clientX: number): void {
    if (!drag) return;
    // The drawer FOLLOWS THE FINGER, clamped at 0, as the sheet follows on its
    // own axis. Without following it is no longer a manipulation but a blind
    // command.
    drag.dx = Math.max(0, drag.x - clientX);
    drawer!.style.transform = `translateX(${-drag.dx}px)`;
  }

  function end(cancelled: boolean): void {
    const current = drag;
    if (!current) return;
    drag = null;
    drawer!.style.transition = "";
    drawer!.style.transform = "";
    // A CANCEL IS NOT A LIFT. It puts the drawer back rather than closing it on
    // a gesture the browser took away — `sheet.tsx`'s `endDrag(true)`.
    //
    // CLOSING GOES THROUGH THE SEAM THE SCRIM ALREADY USES. `__closeLayers` is
    // published by the engine and called by `ui/sheet.tsx`'s scrim; the ladder
    // is drawer → screen → sheet, so with the drawer open it closes the drawer.
    // A second closing path would be a second navigation history.
    if (!cancelled && current.dx > CLOSE_THRESHOLD) {
      // Through the seam, like every other gesture — one call site (D9).
      feedback("commit", drawer);
      window.__closeLayers?.();
    }
  }

  // THE FINGER. Passive, like the engine's own page gestures.
  drawer.addEventListener("touchstart", (event: TouchEvent) => {
    // Two fingers are not this gesture, and reading the first of them would
    // make a pinch look like a swipe.
    if (event.touches.length !== 1) { end(true); return; }
    begin(event.touches[0].clientX);
  }, { passive: true });
  drawer.addEventListener("touchmove", (event: TouchEvent) => {
    if (event.touches.length !== 1) return;
    advance(event.touches[0].clientX);
  }, { passive: true });
  drawer.addEventListener("touchend", () => end(false), { passive: true });
  drawer.addEventListener("touchcancel", () => end(true), { passive: true });

  // EVERYTHING ELSE. A mouse and a pen are never cancelled by a compositor
  // deciding it wants to scroll, so the pointer path serves them unchanged —
  // and the touch pointer is skipped here because the same finger also arrives
  // as a pointer event, and reading it twice would double every delta. That
  // sentence is the engine's, about the same problem.
  drawer.addEventListener("pointerdown", (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    // THE PRIMARY BUTTON ONLY. A right-drag is a context menu on its way, not a
    // dismissal, and closing on it takes the menu out from under the gesture.
    if (event.button !== 0) return;
    begin(event.clientX);
    if (drag) drawer.setPointerCapture(event.pointerId);
  });
  drawer.addEventListener("pointermove", (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    advance(event.clientX);
  });
  drawer.addEventListener("pointerup", (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    end(false);
  });
  drawer.addEventListener("pointercancel", (event: PointerEvent) => {
    if (event.pointerType === "touch") return;
    end(true);
  });
}
