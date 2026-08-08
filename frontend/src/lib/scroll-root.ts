/**
 * Finding the element that actually scrolls.
 *
 * The shell is a frame (see `AppShell`): the document itself never scrolls, and
 * the scrollport is the `main` element it marks with `data-scroll-root`. Any
 * gesture that reads or moves the scroll position — pull-to-refresh, « back to
 * top » — must ask this, not the window, or it reads a value that is always 0
 * and moves an element that never moves.
 */

/** Attribute the shell puts on its scrollport. */
export const SCROLL_ROOT_ATTR = "data-scroll-root";

/**
 * Return the scrollport containing `el`.
 *
 * Args:
 *   el: Any element inside the shell (null tolerated — callers hold refs).
 *
 * Returns:
 *   The scrollport, or null when `el` is detached or rendered outside the
 *   shell (a full-screen Sheet scrolls on its own).
 */
export function scrollRootOf(el: Element | null): HTMLElement | null {
  return el?.closest<HTMLElement>(`[${SCROLL_ROOT_ATTR}]`) ?? null;
}

/**
 * Return the scrollport to its top.
 *
 * Args:
 *   el: Any element inside the scrollport.
 */
export function scrollRootToTop(el: Element | null): void {
  const root = scrollRootOf(el);
  // `scrollTo` is absent outside a real browser (jsdom); assigning scrollTop
  // works in both and needs no guard.
  if (root != null) root.scrollTop = 0;
}
