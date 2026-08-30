// WHETHER A MESSAGE IS ON SCREEN — one fact, published for the one part of the
// frame that must react to it.
//
// WHY IT IS NOT IN THE STORE, and the reason is measured rather than
// stylistic. The store is read by every page, so a write to it re-renders the
// whole tree — and a re-render REPLACES nodes on surfaces that do not keep
// their identity (B-247). A message is dismissed from a capture-phase
// `pointerdown`, which sits between a real finger's press and the `click` that
// follows: the pressed node is torn out in that gap and the click is never
// dispatched at all. Measured on the maintenance page, where the first tap of
// a session simply did nothing while the boot hint was up.
//
// So this is its own subscription with its own subscribers — today exactly one,
// `app/action-button.tsx`. A fact one component needs does not have to travel
// through the state every component reads.
//
// IT IS THE FRAME'S AND IT NAMES NOTHING. Which message, and what it says, is
// the message's own business (`ui/toast.tsx` from L15's phase 6). What is here
// is presence, because the action button is anchored to the same corner and the
// message paints over it.
import { useSyncExternalStore } from "react";

let present = false;
const listeners = new Set<() => void>();

/**
 * Records whether a message is on screen, and tells whoever is watching.
 *
 * Args:
 *     on: True while a message is shown.
 */
export function setMessagePresent(on: boolean): void {
  if (present === on) return;
  present = on;
  for (const listener of listeners) listener();
}

/**
 * Subscribes a component to the message's presence.
 *
 * Returns:
 *     True while a message is on screen.
 */
export function useMessagePresent(): boolean {
  return useSyncExternalStore(
    (onChange) => {
      listeners.add(onChange);
      return () => listeners.delete(onChange);
    },
    () => present,
  );
}

// NO SEAM IS PUBLISHED HERE, and it is a subtraction rather than an omission.
// One was — `window.__messagePresent` — written for an engine that would call
// it, and by the time the message layer landed the engine called
// `window.__toast.show`/`hide` instead and `app/toast-host.ts` called the
// setter above BY IMPORT. Nothing read it, in `design/src` or in the harness:
// new machinery with no subject, which is the shape D5 names and which this
// wave's own comments cite twice. Found by a reader of the seams.
