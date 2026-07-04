/**
 * UpdateToast — informs the user a new build is being applied (tm-shell §5.4).
 *
 * Renders nothing itself: when the service worker reports a new version is ready
 * ({@link PwaState.needRefresh}), it raises a single sonner toast and immediately
 * calls {@link PwaState.applyUpdate}, which activates the waiting SW and reloads
 * the page. The update is automatic — the toast only tells the user why the page
 * is about to reload; no action is required. A ref guards against re-firing the
 * toast/reload across re-renders.
 *
 * The visible toast host (`<Toaster />`) is mounted alongside this component at
 * the app root (see `App.tsx`).
 */

import { useEffect, useRef } from "react";

import { toast } from "sonner";

import type { PwaState } from "@/hooks/usePwa";

/** Message shown while the fresh build activates and the page reloads. */
const UPDATE_MESSAGE = "Nouvelle version disponible — mise à jour…";

/**
 * Fire the auto-update toast + reload when a new SW is ready.
 *
 * Args:
 *   state: The shared PWA state (only ``needRefresh`` + ``applyUpdate`` are read).
 *
 * Returns:
 *   ``null`` — the component is behaviour-only.
 */
export function UpdateToast({ state }: { state: PwaState }): null {
  const { needRefresh, applyUpdate } = state;
  const firedRef = useRef(false);

  useEffect(() => {
    if (!needRefresh || firedRef.current) {
      return;
    }
    firedRef.current = true;
    toast(UPDATE_MESSAGE);
    applyUpdate();
  }, [needRefresh, applyUpdate]);

  return null;
}
