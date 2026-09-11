// WHETHER A LAYER IS OPEN — one fact, published for the one part of the frame
// that is placed by it.
//
// `app/focus.ts` already decides it: each time the markup says which layer is
// on top, it marks the rest of the frame `inert`. The message reads THAT
// decision rather than a second reading of the same attributes, so the two can
// never disagree about whether a layer is open.
//
// NOT IN THE STORE, for `app/message-presence.ts`'s measured reason: a store
// write re-renders every page, and a node replaced between a finger's press and
// its click loses the click (B-247). Its one subscriber is the message's host.

let open = false;
const listeners = new Set<() => void>();

/**
 * Records whether a layer is open, and tells whoever is watching.
 *
 * Args:
 *     on: True while a drawer, a screen, the sheet or a confirmation is open.
 */
export function setLayerOpen(on: boolean): void {
  if (open === on) return;
  open = on;
  for (const listener of listeners) listener();
}

/** Whether a layer is open right now. */
export function readLayerOpen(): boolean {
  return open;
}

/**
 * Subscribes to the fact.
 *
 * Args:
 *     onChange: Called when a layer opens where none was, and when the last one
 *         closes.
 *
 * Returns:
 *     The unsubscription.
 */
export function subscribeToLayerOpen(onChange: () => void): () => void {
  listeners.add(onChange);
  return () => listeners.delete(onChange);
}
