/**
 * Detect a fine pointer with hover — a mouse or trackpad, not a thumb.
 */

import { useEffect, useState } from "react";

/** The query that distinguishes a mouse from a finger. */
export const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)";

/**
 * Report whether the device has a fine, hovering pointer.
 *
 * Deliberately NOT a width breakpoint: a phone held in landscape is wide, and a
 * touchscreen laptop is narrow-ish, yet the thing being decided is whether a
 * hover-only affordance can be reached at all. Width answers a different
 * question and gets this one wrong on both devices.
 *
 * Defaults to `false` when `matchMedia` is unavailable (jsdom, SSR): the
 * touch-safe rendering is the one that hides nothing the operator needs, so an
 * unknown environment gets it.
 *
 * Returns:
 *   ``true`` on mouse/trackpad devices, ``false`` on touch and when unknown.
 */
export function useFinePointer(): boolean {
  const [fine, setFine] = useState(false);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mql = window.matchMedia(FINE_POINTER_QUERY);
    setFine(mql.matches);
    const onChange = (e: MediaQueryListEvent): void => {
      setFine(e.matches);
    };
    mql.addEventListener("change", onChange);
    return () => {
      mql.removeEventListener("change", onChange);
    };
  }, []);

  return fine;
}
