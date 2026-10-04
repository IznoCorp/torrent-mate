// Where a mutation waits when the network will not take it (L11).
//
// THIS FILE KNOWS NOTHING ABOUT MUTATIONS. It opens a store, puts a record in,
// lists them and deletes one. What an envelope MEANS is `app/outbox.ts`'s, and
// what it does is the feature's — MODEL Part 13: « the queue holds opaque
// envelopes; it never knows what a mutation IS ».
//
// WHY IT PERSISTS AT ALL, and it is the operator's arbitration of 2026-08-30: a
// mutation the operator watched succeed and that then vanished because the
// application was closed is NE-DOIT-PAS-1's shape — an action reported as done
// that never happened. So the queue outlives the process.
//
// WHY INDEXEDDB AND NOT `localStorage`. Not size, which would be a poor reason
// for the six small envelopes this will ever hold at once. `localStorage` is
// SYNCHRONOUS and serialises through the main thread, and this is written from
// inside a failed request — the exact moment the interface is trying to stay
// responsive. It is also string-only, so every envelope would round-trip
// through JSON and a body that is not JSON-representable would be silently
// mangled rather than refused.

/** One mutation waiting to depart, exactly as it will be re-issued. */
export type Envelope = {
  /** Its identity, and the key the layer deduplicates on. */
  key: string;
  method: string;
  path: string;
  body: unknown;
  /** When it was accepted, so the oldest departs first. */
  accepted: number;
  /**
   * A number that only ever rises, breaking ties in `accepted`.
   *
   * `Date.now()` has millisecond resolution and two mutations CAN land in one
   * millisecond — a multi-select delete, an undo re-issuing a verb, the
   * delegation firing two. Sorted on `accepted` alone their order then comes
   * from `getAll()`, which is key order, which is a UUID: `pause` then
   * `resume` replays backwards and leaves the wrong final state.
   */
  order: number;
};

const DATABASE = "tm-outbox";
const STORE = "waiting";

let opening: Promise<IDBDatabase | null> | null = null;

/**
 * Opens the store, once.
 *
 * @returns The database, or null where IndexedDB is unavailable — a private
 *     window, a browser refusing storage. Null is a WORKING state and not an
 *     error: the queue then holds nothing across a restart, and the caller is
 *     the one that decides what to tell the operator about it.
 */
function database(): Promise<IDBDatabase | null> {
  if (opening) return opening;
  const attempt: Promise<IDBDatabase | null> = new Promise((resolve) => {
    let request: IDBOpenDBRequest;
    try {
      request = globalThis.indexedDB.open(DATABASE, 1);
    } catch (unavailable) {
      resolve(null);
      return;
    }
    request.onupgradeneeded = () => {
      const database_ = request.result;
      if (!database_.objectStoreNames.contains(STORE)) {
        database_.createObjectStore(STORE, { keyPath: "key" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => resolve(null);
    // A blocked open never fires either handler. Nothing here may hang the
    // caller: this runs inside a failed request, and a promise that never
    // settles there would leave the surface waiting forever on a network that
    // is already known to be gone.
    request.onblocked = () => resolve(null);
  });
  // A FAILURE IS NOT MEMOISED. Holding a rejected open for the life of the
  // document turns one transient error — a blocked upgrade from another tab, a
  // momentary quota refusal — into an outbox that is off until the page is
  // reloaded, silently, with every later mutation rolling back instead of
  // waiting. The next call tries again.
  opening = attempt.then((database_) => {
    if (database_ === null) opening = null;
    return database_;
  });
  return opening;
}

/**
 * Runs one transaction and resolves when it has really committed.
 *
 * ON `oncomplete` AND NOT ON `onsuccess`. A request succeeding says the
 * operation was accepted; only the transaction completing says it is on disk.
 * The difference is exactly the window this queue exists to survive.
 *
 * @param mode Whether the transaction writes.
 * @param work What to do with the store; its request's result is returned.
 * @returns What the work asked for, or null when the store is unavailable.
 */
async function transact<Result>(
  mode: IDBTransactionMode,
  work: (store: IDBObjectStore) => IDBRequest<Result>,
): Promise<Result | null> {
  const database_ = await database();
  if (!database_) return null;
  return new Promise((resolve) => {
    let outcome: Result | null = null;
    try {
      // A CONNECTION THE BROWSER CLOSED under us — an eviction, a version
      // change from another tab — throws here. The handle is dropped so the
      // next call opens a fresh one rather than asking a dead one forever.
      const transaction = database_.transaction(STORE, mode);
      const request = work(transaction.objectStore(STORE));
      request.onsuccess = () => {
        outcome = request.result;
      };
      transaction.oncomplete = () => resolve(outcome);
      transaction.onerror = () => resolve(null);
      transaction.onabort = () => resolve(null);
    } catch (refused) {
      opening = null;
      resolve(null);
    }
  });
}

/**
 * Writes one envelope, replacing any with the same key.
 *
 * @param envelope What to keep.
 * @returns True when it is really on disk.
 */
export async function keep(envelope: Envelope): Promise<boolean> {
  const written = await transact("readwrite", (store) => store.put(envelope));
  return written !== null;
}

/**
 * Reads every waiting envelope, oldest first.
 *
 * @returns What is waiting. Empty where the store is unavailable.
 */
export async function waiting(): Promise<Envelope[]> {
  const found = await transact<Envelope[]>("readonly", (store) => store.getAll());
  return (found ?? []).sort(
    (a, b) => a.accepted - b.accepted || (a.order ?? 0) - (b.order ?? 0));
}

/**
 * Forgets one envelope. Called only after its request has really answered.
 *
 * @param key The envelope's identity.
 */
export async function forget(key: string): Promise<void> {
  await transact("readwrite", (store) => store.delete(key));
}

/**
 * Empties the store. For the harness, which drives one scenario after another.
 */
export async function forgetEverything(): Promise<void> {
  await transact("readwrite", (store) => store.clear());
}
