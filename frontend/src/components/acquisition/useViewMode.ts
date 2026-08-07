/**
 * The « Suivis » display mode, persisted per browser / PWA install.
 *
 * Deliberately NOT in the URL (A7): the mode is a preference, not a location.
 * `?tab=` stays the only shareable state (DOIT-10) — a mode in the URL would make
 * every shared link impose the sender's habit on the receiver.
 */

import { useCallback, useState } from "react";

/** The three display modes of the Suivis view. */
export type ViewMode = "list" | "group" | "grid";

const KEY = "tm.follows.viewmode";
const MODES: readonly ViewMode[] = ["list", "group", "grid"];

/**
 * Read and write the persisted display mode.
 *
 * Returns:
 *   The current mode and a setter. Storage failures (private browsing, quota)
 *   are swallowed: the mode still applies for the session — a preference must
 *   never be able to break the page.
 */
export function useViewMode(): readonly [ViewMode, (m: ViewMode) => void] {
  const [mode, setMode] = useState<ViewMode>(() => {
    try {
      const stored = localStorage.getItem(KEY);
      return MODES.includes(stored as ViewMode) ? (stored as ViewMode) : "list";
    } catch {
      return "list";
    }
  });

  const set = useCallback((next: ViewMode) => {
    setMode(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* private mode — the session keeps the choice, it just will not survive. */
    }
  }, []);

  return [mode, set] as const;
}
