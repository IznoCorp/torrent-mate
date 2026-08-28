// What the stream has announced, and how far this client has got.
//
// ITS OWN SUBJECT: `relay.ts` holds a CONNECTION — opening it, holding it to a
// deadline, deciding when to try again — and this holds the EVENTS that came
// down it and the cursor that says where they stopped. Neither needs to know
// how the other works.
//
// IT KNOWS NO DOMAIN (invariant 10). An event's type is a string; what any of
// them MEANS lives in `features/<domain>/live.ts`.
import { isNewerCursor } from "./stream-cursor";

/** One event, as the server writes it onto the stream. */
export type RelayEvent = {
  id: string;
  type: string;
  data: Record<string, unknown>;
};

/** What a listener is handed for every event that arrives. */
type EventListener = (event: RelayEvent) => void;

const listeners = new Set<EventListener>();

/** How far this client has got, and what a reconnect asks to resume from. */
let cursor: string | null = null;

/**
 * Hands one event to everyone listening, then records where we got to.
 *
 * EVERY EVENT, ONE AT A TIME, as it arrives. A reconnect replays a burst
 * synchronously, and a listener that inspected only the newest of them would
 * drop the rest — production lived that defect in three separate hooks
 * (FRONTEND-DATA-03). Here the shape cannot occur, and R93 emits a burst and
 * asserts it anyway, because « cannot occur » is a claim and a rule is a proof.
 *
 * EACH LISTENER IS ISOLATED. There is one today, and this module exports the
 * entry point so there will be more: without the isolation, one listener's
 * throw skips every listener after it AND escapes into the page.
 *
 * THE CURSOR MOVES AFTER THE FAN-OUT, AND ONLY IF IT SUCCEEDED. It used to move
 * first, so an event whose invalidation threw was skipped by the next
 * reconnect's replay as well — one screen stale for the life of the process,
 * with nothing anywhere recording it. And it only ever moves FORWARD: two
 * briefly-overlapping sockets could otherwise hand it an older id than the one
 * already reached, and the next reconnect would replay from behind.
 *
 * @param event What arrived.
 */
export function announce(event: RelayEvent): void {
  let delivered = true;
  for (const listener of [...listeners]) {
    try {
      listener(event);
    } catch {
      delivered = false;
    }
  }
  if (delivered && (cursor === null || isNewerCursor(event.id, cursor))) {
    cursor = event.id;
  }
}

/**
 * Subscribes to the events.
 *
 * @param listener What to call for every event, one at a time, in order.
 * @returns The unsubscribe.
 */
export function subscribeToEvents(listener: EventListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Reads how far this client has got.
 *
 * @returns The last cursor announced, or null before the first event.
 */
export function readCursor(): string | null {
  return cursor;
}

/** Forgets where we got to, so a reset starts from the whole stream. */
export function resetCursor(): void {
  cursor = null;
}
