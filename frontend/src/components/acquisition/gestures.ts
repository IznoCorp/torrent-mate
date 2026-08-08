/**
 * Touch-gesture arbitration for the acquisition views.
 *
 * The decisions live in pure functions rather than inside pointer handlers so
 * they can be tested without a DOM gesture harness: jsdom performs no layout
 * and synthesises no real touch, so anything expressed only as handler code is
 * effectively untestable and drifts silently.
 */

/**
 * Left-edge band, in CSS pixels, where a horizontal drag is NOT ours.
 *
 * iOS reserves it for the system back gesture. Competing with it produces a
 * half-navigation the user did not ask for, and the OS wins anyway.
 */
export const EDGE_DEAD_ZONE_PX = 30;

/**
 * Fraction of the container width a drag must cover to change view.
 *
 * Below it the view springs back. Chosen so a deliberate flick commits while an
 * accidental nudge during a vertical scroll does not.
 */
export const VIEW_SWIPE_RATIO = 0.28;

/** Pull distance, in CSS pixels, that commits a refresh. */
export const PULL_THRESHOLD_PX = 64;

/** Drag-to-height damping factor (maquette: `dy * 0.55`). */
export const PULL_DRAG_FACTOR = 0.55;

/** Indicator height ceiling while dragging (maquette: `THRESH + 16`). */
export const PULL_MAX_PX = PULL_THRESHOLD_PX + 16;

/** Indicator height while the refresh runs (maquette: 44 px). */
export const PULL_LOADING_PX = 44;

/**
 * Damped indicator height for a raw downward drag.
 *
 * Args:
 *   dy: Total downward movement, in CSS pixels.
 *
 * Returns:
 *   The `.ptr` height — damped and capped exactly like the maquette.
 */
export function pullHeight(dy: number): number {
  return Math.min(PULL_MAX_PX, dy * PULL_DRAG_FACTOR);
}

/**
 * Whether an indicator height arms the refresh (maquette: `h ≥ THRESH×0.62`).
 *
 * Args:
 *   height: Current `.ptr` height from {@link pullHeight}.
 *
 * Returns:
 *   ``true`` when releasing now must refresh.
 */
export function pullArmed(height: number): boolean {
  return height >= PULL_THRESHOLD_PX * 0.62;
}

/** Movement below this, in CSS pixels, is noise rather than intent. */
const AXIS_LOCK_SLOP_PX = 10;

/** The two views a horizontal swipe moves between. */
export type SwipeView = "maintenant" | "suivis";

/**
 * Decide which axis a drag belongs to, or none yet.
 *
 * Locking matters because the vertical scroller and the horizontal pager share
 * one surface: without a lock, a diagonal drag drives both and neither feels
 * intentional. The dominant axis wins once the movement clears the noise floor.
 *
 * Args:
 *   dx: Horizontal movement since the drag started.
 *   dy: Vertical movement since the drag started.
 *   slop: Movement below which nothing is decided yet.
 *
 * Returns:
 *   ``"x"``, ``"y"``, or ``null`` while the drag is still too small to read.
 */
export function lockAxis(
  dx: number,
  dy: number,
  slop: number = AXIS_LOCK_SLOP_PX,
): "x" | "y" | null {
  const ax = Math.abs(dx);
  const ay = Math.abs(dy);
  if (ax < slop && ay < slop) return null;
  return ax >= ay ? "x" : "y";
}

/**
 * Decide whether a horizontal drag starting here may move between views.
 *
 * Args:
 *   startX: Page X where the pointer went down.
 *   containerLeft: Page X of the pager's left edge.
 *
 * Returns:
 *   ``false`` inside the system back-gesture band, ``true`` elsewhere.
 */
export function shouldStartViewSwipe(
  startX: number,
  containerLeft: number,
): boolean {
  return startX - containerLeft >= EDGE_DEAD_ZONE_PX;
}

/**
 * Resolve a completed horizontal drag to the view that should be shown.
 *
 * There are only two views, so a drag past the last one resolves to itself
 * rather than wrapping: wrapping would make a hard flick land somewhere the
 * operator did not aim for, and there is no third view to justify a carousel.
 *
 * Args:
 *   dx: Total horizontal movement (negative drags towards the next view).
 *   width: Pager width, against which the commit threshold is measured.
 *   current: The view the drag started on.
 *
 * Returns:
 *   The view to settle on — ``current`` when the drag was too short.
 */
export function viewSwipeResult(
  dx: number,
  width: number,
  current: SwipeView,
): SwipeView {
  if (width <= 0) return current;
  if (Math.abs(dx) < width * VIEW_SWIPE_RATIO) return current;
  // Dragging left moves forward in the view order, right moves back. With
  // exactly two views the destination does not depend on the origin: a forward
  // drag lands on the last view whether or not it was already there, which IS
  // the clamp. A third view would need an index walk instead. View order is
  // Suivis → Maintenant (operator directive 2026-08-08).
  return dx < 0 ? "maintenant" : "suivis";
}

/**
 * Longest the pull-to-refresh spinner may stay on screen, in ms.
 *
 * The refresh awaits EVERY acquisition query; the slowest one used to hold
 * the bar hostage (operator report: tens of seconds). Past this cap the bar
 * collapses and the refetches continue in the background.
 */
export const PULL_SPINNER_CAP_MS = 6_000;

/**
 * Resolve a completed vertical pull to whether it commits a refresh.
 *
 * Derived the maquette's way: the DAMPED indicator height must have armed
 * (`h ≥ THRESH × 0.62`), not the raw finger distance — the two disagree
 * (raw 64 px damps to 35.2, well short of arming).
 *
 * Args:
 *   dy: Total downward movement.
 *   atTop: Whether the scroller was already at its top when the pull began.
 *
 * Returns:
 *   ``true`` when the pull was long enough, from the top, to mean "refresh".
 */
export function shouldRefresh(dy: number, atTop: boolean): boolean {
  return atTop && pullArmed(pullHeight(dy));
}
