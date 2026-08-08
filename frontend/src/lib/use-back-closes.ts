/**
 * useBackCloses — make the browser Back gesture close an in-page layer.
 *
 * A detail sheet is component state, invisible to history: on a phone the
 * natural « back » gesture would pop the route underneath it and dump the
 * user on another tab. This hook gives the open layer a same-URL history
 * entry so Back has something to pop: the layer closes, the page stays.
 *
 * Contract for the host:
 * - call with the layer's `open` flag and a `close` callback;
 * - any navigation started FROM INSIDE the layer must use `replace: true`,
 *   so the marker entry becomes the destination and a single Back from
 *   there lands on the page under the layer, layer closed.
 */

import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/** History-state marker identifying the entry pushed for an open layer. */
interface BackLayerState {
  readonly backLayer?: boolean;
}

/**
 * Close an in-page layer on the browser Back gesture.
 *
 * Args:
 *   open: Whether the layer is currently open.
 *   close: Callback that closes the layer (idempotent).
 */
export function useBackCloses(open: boolean, close: () => void): void {
  const navigate = useNavigate();
  const location = useLocation();

  // True while OUR marker entry sits on top of the history stack.
  const markerRef = useRef(false);
  // True once the router has actually landed on the marker entry — closing
  // on `marked` alone would fire during the render BEFORE the push settles.
  const landedRef = useRef(false);

  const marked = (location.state as BackLayerState | null)?.backLayer === true;

  // Opening pushes a same-URL marker entry.
  useEffect(() => {
    if (open && !markerRef.current) {
      markerRef.current = true;
      void navigate(`${location.pathname}${location.search}`, {
        state: { backLayer: true },
        // The page under the layer must not jump to the top when the
        // marker entry is pushed (ScrollRestoration treats a push as a
        // new page by default).
        preventScrollReset: true,
      });
    }
    // location is deliberately not a dependency: the push must happen once
    // per opening, not once per URL change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, navigate]);

  // Back popped the marker (marked true → false) → close the layer. Any
  // other navigation away from the marker (e.g. a tab switch) also lands
  // here, and closing then is what a full-width layer wants anyway.
  useEffect(() => {
    if (marked) {
      landedRef.current = true;
      return;
    }
    if (!landedRef.current) return;
    landedRef.current = false;
    if (open && markerRef.current) {
      markerRef.current = false;
      close();
    }
  }, [marked, open, close]);

  // UI close (X, tap outside) consumes the marker entry so history does not
  // accumulate a stale same-URL step.
  useEffect(() => {
    if (!open && markerRef.current) {
      markerRef.current = false;
      void navigate(-1);
    }
  }, [open, navigate]);
}
