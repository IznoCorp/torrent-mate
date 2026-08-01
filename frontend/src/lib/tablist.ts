/**
 * tablist — shared ARIA keyboard contract for the hand-rolled tab bars
 * (ACQUISITION-7, ticket 250).
 *
 * The app's tab bars are plain button rows (no Radix Tabs primitive). This
 * helper adds the WAI-ARIA tablist keyboard behaviour: ArrowLeft/ArrowRight
 * move to the previous/next tab (wrapping), Home/End jump to the first/last.
 * Activation follows focus (the "automatic activation" pattern) and focus is
 * moved onto the newly-active tab button via its DOM id, which pairs with the
 * roving ``tabIndex`` the tab buttons carry.
 */

import type { KeyboardEvent } from "react";

/**
 * Handle a keydown fired inside a ``role="tablist"`` container.
 *
 * Args:
 *   event: The keyboard event (attach on the tablist container).
 *   ids: The tab ids in display order.
 *   activeId: The currently-active tab id.
 *   activate: Called with the id of the tab to activate.
 *   domId: Maps a tab id to the DOM id of its tab button (focus target).
 */
export function handleTablistKeyDown<T extends string>(
  event: KeyboardEvent<HTMLElement>,
  ids: readonly T[],
  activeId: T,
  activate: (id: T) => void,
  domId: (id: T) => string,
): void {
  if (ids.length === 0) return;
  const current = Math.max(0, ids.indexOf(activeId));
  let next: number;
  switch (event.key) {
    case "ArrowRight":
      next = (current + 1) % ids.length;
      break;
    case "ArrowLeft":
      next = (current - 1 + ids.length) % ids.length;
      break;
    case "Home":
      next = 0;
      break;
    case "End":
      next = ids.length - 1;
      break;
    default:
      return;
  }
  event.preventDefault();
  const id = ids[next];
  if (id === undefined) return;
  activate(id);
  document.getElementById(domId(id))?.focus();
}
