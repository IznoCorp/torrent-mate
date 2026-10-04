// What the interface is TOLD about the connection.
//
// ITS OWN FILE BECAUSE IT IS ITS OWN SUBJECT, and the split is on that rather
// than on a line count: `relay.ts` owns a socket — opening it, holding it to a
// deadline, closing it, deciding when to try again — and this owns the reading
// a component subscribes to. Nothing here knows what a WebSocket is; nothing
// there knows what `useSyncExternalStore` is.
//
// IT KNOWS NO DOMAIN (invariant 10). A condition, an attempt count and an
// instant are the application's SHAPE.

/** What the connection is doing, as an interface may draw it. */
export type RelayCondition =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "lost"
  | "refused";

/** What a reader of the connection sees. */
export type RelaySnapshot = {
  condition: RelayCondition;
  /** Failed attempts since the last success. Zero while connected. */
  attempts: number;
  /** The commit the server said it was serving, once it has said so. */
  buildCommit: string | null;
  /**
   * When this client last knew it was current, as a millisecond instant.
   *
   * THE AGE OF THE DATA, not the age of the connection. Any frame proves the
   * link is alive — a ping as much as an event — so any frame moves it.
   */
  currentSince: number | null;
};

let condition: RelayCondition = "connecting";
let attempts = 0;
let buildCommit: string | null = null;
let currentSince: number | null = null;

// A condition the HARNESS asked for, overriding what the transport is really
// doing. It exists because a named state is driven SYNCHRONOUSLY — `__go` calls
// its function and does not await — while three of the four conditions take a
// backoff delay and a handshake to reach for real. So this drives the DRAWING,
// and the transport's own walk into each condition is R93's, measured against a
// real socket.
let forced: RelayCondition | null = null;

// The snapshot is REBUILT ONLY WHEN SOMETHING CHANGES. `useSyncExternalStore`
// compares by identity and re-renders on every new object, so a getter that
// built a fresh one per call would re-render the shell on every unrelated
// render — and, in React's strict development double-render, loop.
let snapshot: RelaySnapshot = { condition, attempts, buildCommit, currentSince };

const listeners = new Set<() => void>();

/** Rebuilds the snapshot and tells everyone watching. */
function publish(): void {
  snapshot = { condition: forced ?? condition, attempts, buildCommit, currentSince };
  for (const listener of [...listeners]) listener();
}

/**
 * Records what the transport now knows, and publishes it.
 *
 * @param next The fields that changed. Anything omitted is left as it was.
 */
export function reportCondition(next: {
  condition?: RelayCondition;
  attempts?: number;
  buildCommit?: string;
  currentSince?: number;
}): void {
  if (next.condition !== undefined) condition = next.condition;
  if (next.attempts !== undefined) attempts = next.attempts;
  if (next.buildCommit !== undefined) buildCommit = next.buildCommit;
  if (next.currentSince !== undefined) currentSince = next.currentSince;
  publish();
}

/**
 * Counts one more failed attempt.
 *
 * @returns The new count, which is what the backoff schedule is indexed by.
 */
export function countAttempt(): number {
  attempts += 1;
  return attempts;
}


/**
 * Subscribes to the connection, for a component drawing its condition.
 *
 * @param listener What to call when the condition changes.
 * @returns The unsubscribe.
 */
export function subscribeToCondition(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Reads the connection's condition.
 *
 * @returns The snapshot, stable by identity until something changes.
 */
export function readCondition(): RelaySnapshot {
  return snapshot;
}

/**
 * Asks for a condition, for the harness alone.
 *
 * @param wanted The condition to draw, or null to go back to the real one.
 */
export function forceCondition(wanted: RelayCondition | null): void {
  forced = wanted;
  publish();
}
