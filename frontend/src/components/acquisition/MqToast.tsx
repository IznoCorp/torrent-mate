/**
 * MqToast — the maquette's in-page toast for the Acquisition surface.
 *
 * One neutral tone (the maquette has no success/error variants — the
 * MESSAGE carries the meaning), anchored above the FAB (`.mqtoast`,
 * bottom 82 px), auto-hidden after 5 s with the close button as the real
 * control. Imperative `mqtoast(msg)` mirrors sonner's ergonomics so call
 * sites need no provider plumbing; `<MqToaster />` is the single host,
 * rendered once inside the `.mq` scope.
 */

import { useCallback, useEffect, useRef, useState, type ReactElement } from "react";

import { X } from "lucide-react";

/** Auto-hide delay — maquette `toast()` uses 5000 ms. */
const TOAST_HIDE_MS = 5000;

let listener: ((msg: string) => void) | null = null;

/**
 * Show a toast on the Acquisition surface.
 *
 * Args:
 *   msg: The message — it must carry the outcome by itself (single tone).
 */
export function mqtoast(msg: string): void {
  listener?.(msg);
}

/**
 * Host element for {@link mqtoast} — render exactly once per page.
 *
 * Returns:
 *   The maquette toast element (hidden until a message arrives).
 */
export function MqToaster(): ReactElement {
  const [msg, setMsg] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const hide = useCallback(() => {
    if (timerRef.current != null) clearTimeout(timerRef.current);
    timerRef.current = null;
    setMsg(null);
  }, []);

  const show = useCallback((m: string) => {
    if (timerRef.current != null) clearTimeout(timerRef.current);
    setMsg(m);
    timerRef.current = setTimeout(() => {
      setMsg(null);
    }, TOAST_HIDE_MS);
  }, []);

  useEffect(() => {
    listener = show;
    return () => {
      listener = null;
      if (timerRef.current != null) clearTimeout(timerRef.current);
    };
  }, [show]);

  return (
    <div
      className={`mqtoast ${msg != null ? "show" : ""}`}
      role="status"
      aria-atomic="true"
      aria-live="polite"
    >
      <span>{msg ?? ""}</span>
      <button
        type="button"
        className="mqtoastclose"
        aria-label="Fermer la notification"
        onClick={hide}
      >
        <X aria-hidden="true" />
      </button>
    </div>
  );
}
