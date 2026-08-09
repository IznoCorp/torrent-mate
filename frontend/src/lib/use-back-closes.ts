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
import {
  NavigationType,
  useLocation,
  useNavigate,
  useNavigationType,
} from "react-router-dom";

/** History-state marker identifying the entry pushed for an open layer. */
interface BackLayerState {
  readonly backLayer?: string;
}

/** Source of per-instance marker ids.
 *
 *  Identity matters: two layers can be mounted at once (a panel hosts both a
 *  journey sheet and a follow sheet). With a shared boolean, the inner layer
 *  reads the OUTER's marker as its own and closes on a Back that was never
 *  meant for it. */
let markerSeq = 0;

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
  const navigationType = useNavigationType();

  // This instance's marker id — stable for the component's lifetime.
  const markerIdRef = useRef<string>("");
  if (markerIdRef.current === "") {
    markerSeq += 1;
    markerIdRef.current = `layer-${String(markerSeq)}`;
  }

  // True while OUR marker entry sits on top of the history stack.
  const markerRef = useRef(false);
  // True once the router has actually landed on the marker entry — closing
  // on `marked` alone would fire during the render BEFORE the push settles.
  const landedRef = useRef(false);

  const marked =
    (location.state as BackLayerState | null)?.backLayer === markerIdRef.current;

  // Opening pushes a same-URL marker entry.
  useEffect(() => {
    if (open && !markerRef.current) {
      markerRef.current = true;
      void navigate(`${location.pathname}${location.search}`, {
        state: { backLayer: markerIdRef.current },
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

  // Back popped the marker (marked true → false) → close the layer.
  //
  // Gated on a POP, and that gate is load-bearing: a SECOND layer opening on
  // top pushes its own marker, which also takes us off ours. Closing then
  // would shut the layer underneath the one the operator just opened. Our
  // marker is merely buried; when the upper layer closes, the router pops
  // back onto it and `marked` is true again.
  useEffect(() => {
    if (marked) {
      landedRef.current = true;
      return;
    }
    if (!landedRef.current) return;
    if (navigationType !== NavigationType.Pop) return;
    landedRef.current = false;
    if (open && markerRef.current) {
      markerRef.current = false;
      close();
    }
  }, [marked, open, close, navigationType]);

  // UI close (X, tap outside) consumes the marker entry so history does not
  // accumulate a stale same-URL step.
  useEffect(() => {
    if (!open && markerRef.current) {
      markerRef.current = false;
      void navigate(-1);
    }
  }, [open, navigate]);
}
