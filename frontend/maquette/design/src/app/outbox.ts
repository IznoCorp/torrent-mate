// The mutations that could not depart, and how they leave (L11).
//
// WHAT IT KNOWS: that something is waiting, and how to re-issue it. It does not
// know what a mutation MEANS, which feature made it, or what it will change —
// MODEL Part 13: « the queue holds `{ key, request }` opaque envelopes ».
//
// WHY THE ENQUEUE IS IN `send()` AND NOT IN EACH `queries.ts`. Part 13 says a
// feature's `queries.ts` enqueues, and the intent — the queue learns nothing
// about domains — is kept exactly. What changes is the number of places that
// have to remember: `lib/query-client.ts`'s `send()` is the ONE seam every
// mutation in the tree already passes through (six call sites, three files), so
// enqueuing there is the same behaviour with one writer instead of six. A rule
// that has to be re-applied at every call site is a rule that will be missing
// from the seventh.
//
// WHY AN ENQUEUED MUTATION RESOLVES RATHER THAN REJECTS. Rejecting is what
// triggers L09's rollback, and rolling back a mutation that has NOT failed is
// precisely the defect P8 exists to prevent — the operator's action would
// disappear from the interface while it sat safely on disk waiting to depart.
// So it resolves, and the interface says what is waiting: a resolved mutation
// the operator can see and a departed one are not the same thing, and §8
// forbids an interface that has stopped saying which it is.
import {
  type Envelope,
  forget,
  forgetEverything,
  keep,
  waiting,
} from "./outbox-store";

/** What re-issues an envelope. Set once, by the boot, to `send()`'s own core. */
type Departure = (envelope: Envelope) => Promise<void>;

let depart: Departure | null = null;
let departing = false;
let pendingCount = 0;
const listeners = new Set<() => void>();

/** Tells every subscriber that what is waiting has changed. */
function announce(): void {
  for (const listener of listeners) listener();
}

/**
 * Subscribes to the number waiting.
 *
 * @param listener Called whenever it changes.
 * @returns The unsubscribe.
 */
export function subscribeToOutbox(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * How many mutations are waiting to depart.
 *
 * READ SYNCHRONOUSLY, from a count this module maintains, and NOT from the
 * store. A component subscribes to this through `useSyncExternalStore`, which
 * requires a snapshot that is the same value for an unchanged state — an async
 * read cannot be that, and a promise re-created per render is a render loop.
 *
 * @returns The count.
 */
export function outboxDepth(): number {
  return pendingCount;
}

/**
 * Accepts a mutation the network refused to take.
 *
 * @param envelope The request, exactly as it will be re-issued.
 * @returns True when it is really on disk — false means it was lost, and the
 *     caller is the only one that can still tell the operator so.
 */
export async function holdBack(envelope: Envelope): Promise<boolean> {
  const kept = await keep(envelope);
  if (kept) {
    pendingCount += 1;
    announce();
  }
  return kept;
}

/**
 * Sets what re-issues an envelope. Called once, by the boot.
 *
 * IT IS INJECTED RATHER THAN IMPORTED, and that is invariant 7 rather than
 * taste: `lib/query-client.ts` imports THIS to enqueue, so importing it back
 * would be a cycle — and a cycle between the queue and the thing it queues is
 * the kind that survives review because both halves read naturally.
 *
 * @param departure What re-issues an envelope.
 */
export function setDeparture(departure: Departure): void {
  depart = departure;
}

/**
 * Sends everything that is waiting, oldest first.
 *
 * EXACTLY ONCE, AND WHERE EACH HALF OF THAT LIVES. An envelope is forgotten
 * only AFTER its request has answered, so a replay interrupted mid-flight
 * leaves it on disk and the next boot sends it again — at LEAST once, which is
 * all a client can promise on its own. The other half is the key the envelope
 * carries: the layer records the keys it has applied and answers a second
 * arrival with the first answer, so « at least once » on the wire is « exactly
 * once » in the data. A client that deleted first would promise at most once
 * and lose the operator's action to a dropped connection.
 *
 * ONE AT A TIME. Two departures at once would race on the same store and could
 * send one envelope twice before either had forgotten it — which the key would
 * absorb, but a queue that relies on the deduplicator for ordinary operation is
 * a queue with no ordering at all.
 */
export async function departAll(): Promise<void> {
  if (departing || !depart) return;
  departing = true;
  try {
    for (const envelope of await waiting()) {
      try {
        await depart(envelope);
      } catch (refused) {
        // STILL UNREACHABLE, OR REFUSED OUTRIGHT — and this stops the run
        // either way. Going on would send later envelopes before an earlier
        // one, and the operator's actions have an order they were made in.
        break;
      }
      await forget(envelope.key);
      pendingCount = Math.max(0, pendingCount - 1);
      announce();
    }
  } finally {
    departing = false;
  }
}

/**
 * Installs the outbox: counts what survived the last run, and sends it.
 *
 * ON `online` AND ON THE RELAY'S RETURN, not on a timer. The browser's `online`
 * event is what the platform offers and it is the cheap signal; it is also
 * famously optimistic — it fires for a network interface coming up, not for a
 * server becoming reachable — so a departure that fails simply leaves the queue
 * where it was and the next signal tries again.
 */
export function installOutbox(): void {
  void waiting().then((held) => {
    pendingCount = held.length;
    announce();
    // What was on disk when the application started is, by definition, a
    // mutation from a previous run that never departed.
    if (held.length) void departAll();
  });
  globalThis.addEventListener("online", () => void departAll());
}

/**
 * Empties the outbox. For the harness, which drives one scenario after another.
 */
export async function forgetOutbox(): Promise<void> {
  await forgetEverything();
  pendingCount = 0;
  announce();
}

// PUBLISHED HERE AND NOT BY THE BOOT, for the reason `shell.tsx` states about
// itself: it owns WHEN a thing is installed, and the module owns WHAT. The
// engine's seams and the mock layer's already work this way, each declaring its
// own surface beside the functions it exposes.
//
// A rule that had to reach inside this module to ask what is waiting would be a
// rule coupled to how the module is built.
declare global {
  interface Window {
    /** What is waiting to depart — P8's own seam. */
    __outbox?: {
      depth: typeof outboxDepth;
      subscribe: typeof subscribeToOutbox;
      forget: typeof forgetOutbox;
      /** What is on DISK, which is not always what the count says. */
      waiting: () => Promise<Envelope[]>;
      /** Issues one mutation through the real path a surface uses. */
      issue: (method: string, path: string, body?: unknown) => Promise<unknown>;
      /** Sends what is waiting, without waiting for an `online` event. */
      depart: () => Promise<void>;
    };
  }
}

/**
 * Publishes the outbox's driving surface. Called by the boot.
 *
 * THE ISSUER IS PASSED IN rather than imported, and it is the same reason
 * `setDeparture` exists: `lib/query-client.ts` imports THIS module to enqueue,
 * so importing it back would be a cycle.
 *
 * WHY A RULE MAY ISSUE A MUTATION AT ALL. P8 is a property of the path a
 * surface really takes — issue, fail, hold, depart — and a rule that rebuilt
 * that path out of `fetch` calls would be proving its own reconstruction. This
 * is a DRIVING seam, exactly like `__mocks` and `__go`: read by rules, never by
 * a component, and it dies at switchover with the rest of them.
 *
 * @param issue The real `send()`, which is the path every surface uses.
 */
export function publishOutboxSeam(
  issue: (method: string, path: string, body?: unknown) => Promise<unknown>,
): void {
  globalThis.window.__outbox = {
    depth: outboxDepth,
    subscribe: subscribeToOutbox,
    forget: forgetOutbox,
    waiting,
    issue,
    depart: departAll,
  };
}
