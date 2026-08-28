// The live relay's TRANSPORT, and nothing else.
//
// WHERE IT LIVES, AND WHY IT IS NOT A FEATURE (invariant 10). A relay, its
// reconnection policy and its replay window are the application's SHAPE, not
// its subject. The surface the work happened to be tested against is not what
// the code is about — and this file names no domain word, knows nothing of a
// query cache and could not tell a media item from a pipeline run.
//
// IT IS INSTALLED AT BOOT, NEVER MOUNTED WITH A SURFACE, and that is a
// correctness decision rather than a placement one. `lib/query-client.ts` sets
// `staleTime: Infinity`, `refetchOnWindowFocus: false` and
// `refetchOnReconnect: false` — each argued there, each right, and their sum is
// that A QUERY WHICH MISSES ITS INVALIDATION IS STALE FOR THE LIFE OF THE
// PROCESS. There is no clock behind it. A subscription mounted with a surface
// would miss every event arriving while that surface is unmounted, and the
// remount would refetch nothing.
//
// Production's equivalent is a hook, and it is safe there because 21
// `refetchInterval` sites poll underneath it: a missed event costs sixty
// seconds. Here it would cost forever. That is what makes the same shape,
// transposed, a defect (B-154).
//
// IT DOES NOT RETRY A REFUSAL. A session the server will not accept is not a
// connection problem, and retrying one is a loop that produces nothing and
// says nothing — the exact « rien ne se passe » §8 of the constitution calls a
// lie by omission. It becomes a state the interface DRAWS instead.

/** What the server pushes once, before anything else. */
const HELLO_TYPE = "ws.hello";
/** What the server pushes after thirty seconds of client silence. */
const PING_TYPE = "ws.ping";
/** The address the stream is served at. */
const RELAY_ADDRESS = "/ws/events";
/** What the client answers a ping with. Any text frame is a pong. */
const PONG_FRAME = "pong";

// THE CLOSE CODE A REFUSED SESSION ARRIVES AS. The server accepts the socket
// and only then reads the cookie, so a refusal is a close on an OPEN socket —
// which is what makes this branch reachable at all. Closing before accept would
// give a browser an opaque 1006 and this code would be dead in production.
const REFUSED_CODE = 4401;
// A clean teardown. Nothing to say, nothing to reconnect to.
const CLEAN_CODE = 1000;

// The backoff, in milliseconds, one entry per attempt, the last repeating. It
// is a RECONNECTION SCHEDULE and not a poll: each delay happens once, after a
// failure, and the sequence stops the moment a connection succeeds.
const BACKOFF_MILLISECONDS = [250, 500, 1000, 2000, 4000, 8000] as const;

// How many attempts may fail before the interface stops saying « reconnecting »
// and starts saying « this screen is not updating ». Past this point the sum of
// the delays above is several seconds, which is longer than a reader will read
// a stale list without being told.
const ATTEMPTS_BEFORE_LOST = 3;

/** What the connection is doing, as an interface may draw it. */
export type RelayCondition =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "lost"
  | "refused";

/** One event, as the server writes it onto the stream. */
export type RelayEvent = {
  id: string;
  type: string;
  data: Record<string, unknown>;
};

/** What a reader of the connection sees. */
export type RelaySnapshot = {
  condition: RelayCondition;
  /** Failed attempts since the last success. Zero while connected. */
  attempts: number;
  /** The commit the server said it was serving, once it has said so. */
  buildCommit: string | null;
  /** When the connection was last known good, as a millisecond instant. */
  currentSince: number | null;
};

/** What a listener is handed for every event that arrives. */
type EventListener = (event: RelayEvent) => void;

let socket: WebSocket | null = null;
let attempts = 0;
let cursor: string | null = null;
let buildCommit: string | null = null;
let currentSince: number | null = null;
let condition: RelayCondition = "connecting";
let retryTimer: number | null = null;
let stopped = false;

// The snapshot is REBUILT ONLY WHEN SOMETHING CHANGES. `useSyncExternalStore`
// compares by identity and re-renders on every new object, so a getter that
// built a fresh one per call would re-render the shell on every unrelated
// render — and, in React's strict development double-render, loop.
let snapshot: RelaySnapshot = {
  condition,
  attempts,
  buildCommit,
  currentSince,
};

const conditionListeners = new Set<() => void>();
const eventListeners = new Set<EventListener>();

/**
 * Publishes a new snapshot and tells everyone watching the connection.
 */
function publish(): void {
  snapshot = { condition, attempts, buildCommit, currentSince };
  for (const listener of [...conditionListeners]) listener();
}

/**
 * Hands one event to everyone listening.
 *
 * EVERY EVENT, ONE AT A TIME, as it arrives. A reconnect replays a burst
 * synchronously, and a listener that inspected only the newest of them would
 * drop the rest — production lived that defect in three separate hooks. Here
 * the shape cannot occur, and R93 emits a burst and asserts it anyway, because
 * « cannot occur » is a claim and a rule is a proof.
 *
 * @param event What arrived.
 */
function announce(event: RelayEvent): void {
  cursor = event.id;
  for (const listener of [...eventListeners]) listener(event);
}

/**
 * Reads one frame, whatever the server sent.
 *
 * A frame this client cannot parse is DROPPED and never guessed at: a malformed
 * message that reached a listener as an event with an empty payload would
 * refresh a surface for a reason nobody could reconstruct.
 *
 * @param raw The frame body.
 */
function receive(raw: string): void {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return;
  }
  if (typeof parsed !== "object" || parsed === null) return;
  const message = parsed as Record<string, unknown>;
  if (typeof message.type !== "string") return;

  if (message.type === HELLO_TYPE) {
    const data = message.data;
    if (typeof data === "object" && data !== null) {
      const commit = (data as Record<string, unknown>).build_commit;
      if (typeof commit === "string") buildCommit = commit;
    }
    attempts = 0;
    condition = "connected";
    currentSince = Date.now();
    publish();
    return;
  }
  if (message.type === PING_TYPE) {
    // ANSWERING IS THE WHOLE OF IT. The server resets its silence timer on any
    // text frame; a missed ping is the server's business and reaches this
    // client as a close, never as a state it has to infer.
    socket?.send(PONG_FRAME);
    return;
  }
  if (typeof message.id !== "string") return;
  const data = typeof message.data === "object" && message.data !== null
    ? (message.data as Record<string, unknown>)
    : {};
  announce({ id: message.id, type: message.type, data });
}

/**
 * Schedules the next attempt, and says what the interface should show meanwhile.
 */
function retry(): void {
  attempts += 1;
  condition = attempts > ATTEMPTS_BEFORE_LOST ? "lost" : "reconnecting";
  publish();
  const delay = BACKOFF_MILLISECONDS[
    Math.min(attempts - 1, BACKOFF_MILLISECONDS.length - 1)
  ];
  retryTimer = globalThis.setTimeout(connect, delay);
}

/**
 * Opens the socket, carrying the cursor of the last event this client saw.
 *
 * THE CURSOR IS WHAT MAKES A RECONNECT HONEST. Without it the gap is either
 * lost — the screen silently misses what happened while the network was down —
 * or papered over by invalidating everything, which is one line, always
 * correct, and indistinguishable from a reload. The server replays the gap with
 * an exclusive lower bound, so the same event never arrives twice.
 */
function connect(): void {
  if (stopped) return;
  retryTimer = null;
  const address = cursor === null
    ? RELAY_ADDRESS
    : `${RELAY_ADDRESS}?last_id=${encodeURIComponent(cursor)}`;
  const opened = new WebSocket(address);
  socket = opened;
  opened.addEventListener("message", (event) => {
    if (typeof event.data === "string") receive(event.data);
  });
  opened.addEventListener("close", (event) => {
    if (opened !== socket) return;
    socket = null;
    if (event.code === REFUSED_CODE) {
      // NOT A CONNECTION PROBLEM, so not a reconnection. The interface says the
      // session is over and offers the way back; retrying would say nothing.
      condition = "refused";
      currentSince = null;
      publish();
      return;
    }
    if (event.code === CLEAN_CODE || stopped) return;
    currentSince = currentSince ?? null;
    retry();
  });
  opened.addEventListener("error", () => {
    // A browser reports an error and then a close for the same failure. The
    // close is where the decision is taken, so this listener exists to stop the
    // error surfacing as an unhandled one, and does nothing else.
  });
}

/**
 * Starts the relay. Called once, from the boot.
 *
 * @returns Nothing. There is no disposer, because nothing calls one — a
 *   returned one would be a promise this module does not keep.
 */
export function installRelay(): void {
  stopped = false;
  connect();
}

/**
 * Subscribes to the CONNECTION, for a component drawing its condition.
 *
 * @param listener What to call when the condition changes.
 * @returns The unsubscribe.
 */
export function subscribeToCondition(listener: () => void): () => void {
  conditionListeners.add(listener);
  return () => {
    conditionListeners.delete(listener);
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
 * Subscribes to the EVENTS.
 *
 * @param listener What to call for every event, one at a time, in order.
 * @returns The unsubscribe.
 */
export function subscribeToEvents(listener: EventListener): () => void {
  eventListeners.add(listener);
  return () => {
    eventListeners.delete(listener);
  };
}

/**
 * Asks for a connection now, whatever the backoff was waiting for.
 *
 * This is the manual retry the `lost` state offers. It resets the attempt
 * count, because a reader who asked is not the same thing as a schedule that
 * expired — the interface should say « connecting » again rather than go on
 * saying the screen is cold.
 */
export function reconnectNow(): void {
  if (retryTimer !== null) {
    globalThis.clearTimeout(retryTimer);
    retryTimer = null;
  }
  socket?.close(CLEAN_CODE, "replaced by a manual retry");
  socket = null;
  attempts = 0;
  condition = "connecting";
  publish();
  connect();
}

/**
 * Stops the relay and forgets its cursor.
 *
 * For the harness alone: a named state that needs a cold relay reaches it
 * through this rather than through a private field.
 */
export function resetRelay(): void {
  stopped = true;
  if (retryTimer !== null) {
    globalThis.clearTimeout(retryTimer);
    retryTimer = null;
  }
  socket?.close(CLEAN_CODE, "reset");
  socket = null;
  attempts = 0;
  cursor = null;
  buildCommit = null;
  currentSince = null;
  condition = "connecting";
  publish();
}
