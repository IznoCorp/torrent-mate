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
/** The path the stream is served at. */
const RELAY_PATH = "/ws/events";
/** What the client answers a ping with. Any text frame is a pong. */
const PONG_FRAME = "pong";

// THE CLOSE CODE A REFUSED SESSION ARRIVES AS. The server accepts the socket
// and only then reads the cookie, so a refusal is a close on an OPEN socket —
// which is what makes this branch reachable at all. Closing before accept would
// give a browser an opaque 1006 and this code would be dead in production.
import {
  announce,
  readCursor,
  resetCursor,
  unblockCursor,
} from "./relay-events";
import {
  countAttempt,
  forceCondition,
  reportCondition,
} from "./relay-condition";

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

// HOW LONG SILENCE MAY LAST BEFORE THE LINK IS PRESUMED DEAD, and this is the
// defect the whole lot turned on. A socket can go HALF-OPEN — the laptop
// sleeps, the phone backgrounds the application, a proxy drops an idle flow —
// and neither peer receives a FIN. `readyState` stays OPEN, no `close` ever
// arrives, and a client that only listens for `close` believes it is connected
// for as long as the tab lives. With `staleTime: Infinity` underneath there is
// no clock to correct it: every screen freezes at the instant of the drop while
// the interface says « Connecté ». That is §8 exactly inverted, inside the
// feature written to end it.
//
// The server pings after thirty seconds of client silence, so forty-five
// seconds without a frame OF ANY KIND — event, hello or ping — means the link
// is gone. The number is production's, which has answered for this protocol
// against real sockets.
const SILENCE_LIMIT_MILLISECONDS = 45_000;

// WHAT IS ACTUALLY WAITED, and the two are separated for the harness alone: a
// rule cannot spend forty-five seconds per hold. `harness/liveness.py` shortens
// them to exercise the MECHANISM, and reads the two constants above out of this
// source to hold the NUMBERS — the same arrangement `settle.py` uses for the
// oracle's budget, and for the same reason: a rule that only ever measured a
// shortened timer would prove nothing about the one that ships.

// HOW LONG AN OPENING MAY TAKE. A hung 101 upgrade — a captive portal, a VPN
// drop, a wedged worker — fires neither `open` nor `close`, so the backoff
// ladder never advances: it only steps on a `close`. Without this the relay
// waits on the browser's own connect timeout, which is minutes on desktop and
// effectively never on some mobile stacks, and the interface sits on
// « Connexion… » with no notice drawn for it.
const OPENING_LIMIT_MILLISECONDS = 10_000;

let silenceLimit = SILENCE_LIMIT_MILLISECONDS;
let openingLimit = OPENING_LIMIT_MILLISECONDS;

/** One event, as the server writes it onto the stream. */

let socket: WebSocket | null = null;
let retryTimer: number | null = null;
// The deadline the current socket is being held to: the opening limit until it
// speaks, the silence limit afterwards. ONE timer for both, because a socket is
// never simultaneously opening and idle.
let livenessTimer: number | null = null;


/**
 * Holds the current socket to a deadline, replacing any deadline it had.
 *
 * @param limit How long, in milliseconds.
 */
function armLiveness(limit: number): void {
  disarmLiveness();
  livenessTimer = globalThis.setTimeout(() => {
    livenessTimer = null;
    // A HALF-OPEN SOCKET NEVER CLOSES ITSELF, so the retry cannot be left to
    // the close handler. The socket is dropped from under it FIRST — the close
    // that may eventually arrive is then guarded out by identity — and the
    // reconnection is driven from here.
    const silent = socket;
    socket = null;
    try {
      silent?.close();
    } catch {
      // A socket that is already closing throws; there is nothing to do about
      // it and nothing to say — the retry below is the whole response.
    }
    retry();
  }, limit);
}

/**
 * Lets go of the current socket without hearing its close.
 *
 * THE ORDER IS THE WHOLE OF IT. `socket` is nulled FIRST, so the close this
 * side is about to cause is dropped by the identity guard in the close
 * listener — which is what makes « every close that reaches the decision is
 * unsolicited » true by construction rather than by a flag somebody has to
 * consume.
 *
 * A SHARED FLAG WAS TRIED AND IT LEAKED, twice over. `teardownAsked` was set by
 * `reconnectNow()` and consumed by the close it expected — except when `socket`
 * was already null, which is every retry from `refused` or `lost`, where
 * `close()` is a no-op and nothing consumed it; and except in a real browser,
 * where `close()` is ASYNCHRONOUS and the close arrives after the replacement
 * is in place, so the identity guard eats it before the flag is read. Either
 * way the flag stayed true and the next unsolicited 1000 — one per deploy —
 * was swallowed: condition « connected », no socket, nothing scheduled. The
 * repair for that defect reintroduced it.
 *
 * @param why What to tell the server.
 */
function letGo(why: string): void {
  const going = socket;
  socket = null;
  disarmLiveness();
  try {
    going?.close(CLEAN_CODE, why);
  } catch {
    // A socket already closing throws; it is going away either way.
  }
}

/** Releases the current deadline. */
function disarmLiveness(): void {
  if (livenessTimer === null) return;
  globalThis.clearTimeout(livenessTimer);
  livenessTimer = null;
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
  // ANY FRAME PROVES THE LINK IS ALIVE, including a ping — which is why the
  // watchdog is re-armed here rather than in the event branch, and why the
  // instant is recorded here too. `currentSince` is what the notice calls « les
  // informations affichées datent de », and that is the age of the DATA: the
  // last moment this client knew it was current, not the moment it connected.
  // Written only at the handshake, it announced the session's start — a screen
  // open since 09:00 and dropped at 14:30 claimed its data was five hours old
  // when it was thirty seconds old.
  armLiveness(silenceLimit);
  reportCondition({ currentSince: Date.now() });
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
    const commit = typeof data === "object" && data !== null
      ? (data as Record<string, unknown>).build_commit
      : undefined;
    // A FRESH CONNECTION IS ABOUT TO REPLAY from wherever the cursor stopped,
    // so a freeze from the previous one is spent.
    unblockCursor();
    reportCondition({
      condition: "connected",
      attempts: 0,
      ...(typeof commit === "string" ? { buildCommit: commit } : {}),
    });
    return;
  }
  if (message.type === PING_TYPE) {
    // ANSWERING IS THE WHOLE OF IT. The server resets its silence timer on any
    // text frame; a missed ping is the server's business and reaches this
    // client as a close, never as a state it has to infer.
    //
    // AND IT CAN THROW. `send()` on a socket that has begun closing raises
    // `InvalidStateError`, and this call sits inside a message listener — an
    // escaping error there is an uncaught exception on a page whose interface
    // does not depend on the transport at all.
    try {
      socket?.send(PONG_FRAME);
    } catch {
      // The socket is going away; the close handler is where that is decided.
    }
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
  disarmLiveness();
  const attempts = countAttempt();
  reportCondition({
    condition: attempts > ATTEMPTS_BEFORE_LOST ? "lost" : "reconnecting",
  });
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
  retryTimer = null;
  // BUILT ABSOLUTE, and the scheme is derived from the page's. A RELATIVE
  // address is a recent addition to the `WebSocket` constructor — Firefox 124,
  // Safari 17.4, Chromium 116 — so an older engine, an embedded WebView or the
  // system WebView backing an installed PWA throws `SyntaxError` on it. The
  // throw is caught below, but a connection that can never be made is not a
  // failure worth being resilient about: production has built the absolute form
  // since before this file existed.
  const scheme = globalThis.location.protocol === "https:" ? "wss:" : "ws:";
  const base = `${scheme}//${globalThis.location.host}${RELAY_PATH}`;
  const cursor = readCursor();
  const address = cursor === null
    ? base
    : `${base}?last_id=${encodeURIComponent(cursor)}`;
  // THE DEADLINE IS ARMED BEFORE THE SOCKET EXISTS, so an opening that never
  // resolves is caught by the same mechanism that catches silence afterwards.
  armLiveness(openingLimit);
  let opened: WebSocket;
  try {
    opened = new WebSocket(address);
  } catch {
    // THE CONSTRUCTOR CAN THROW, and this call site is a module-level statement
    // in the boot: an escaping error would run before `createRoot` and leave the
    // operator on the startup screen with no interface at all — for a failure in
    // a transport the interface does not depend on. It is a reconnection like
    // any other.
    socket = null;
    disarmLiveness();
    retry();
    return;
  }
  socket = opened;
  opened.addEventListener("open", () => {
    if (opened !== socket) return;
    // THE UPGRADE SUCCEEDED, so the opening deadline has done its job and the
    // silence watchdog takes over. Without this listener the « opening » limit
    // was really a TIME-TO-FIRST-FRAME limit: a socket accepted at t=0 whose
    // hello is late — a cold worker, a large `?last_id=` replay — was killed at
    // ten seconds and retried, re-requesting the same window and being killed
    // again. A connect storm on exactly the reconnection the cursor exists to
    // make cheap.
    armLiveness(silenceLimit);
  });
  opened.addEventListener("message", (event) => {
    // THE SAME GUARD THE CLOSE LISTENER HAS, and it was missing here. A real
    // `close()` is ASYNCHRONOUS: the browser goes on dispatching frames already
    // in its receive buffer while `socket` already points at the replacement.
    // A stale `ws.hello` then set the condition to `connected` for a socket
    // that was closing — a green dot over a link that no longer exists, and a
    // permanent one if the replacement never opens.
    if (opened !== socket) return;
    if (typeof event.data === "string") receive(event.data);
  });
  opened.addEventListener("close", (event) => {
    if (opened !== socket) return;
    socket = null;
    disarmLiveness();
    if (event.code === REFUSED_CODE) {
      // NOT A CONNECTION PROBLEM, so not a reconnection. The interface says the
      // session is over and offers the way back; retrying would say nothing.
      // `currentSince` IS KEPT. What is on screen really does date from the
      // moment the connection was last good, and a session ending does not
      // make that less true — clearing it would take the one fact the notice
      // has that a reader can act on. It also kept the drawn state and the
      // real path saying different things, which is how a maquette starts
      // lying about the application it is.
      reportCondition({ condition: "refused" });
      return;
    }
      // A CLEAN CLOSE IS ONLY SILENCE IF WE ASKED FOR IT. The server closes
    // cleanly when it shuts down — and this deployment restarts the web process
    // on every merge, so an unsolicited 1000 is the single most frequent way
    // this connection ends. Treating every 1000 as a deliberate teardown left
    // the condition on « connected » with no socket and nothing scheduled:
    // every open tab showing a live-looking screen that would never update
    // again.
    // EVERY CLOSE THAT REACHES HERE IS UNSOLICITED, BY CONSTRUCTION — see
    // `letGo`, which nulls the socket before closing so the identity guard four
    // lines above owns a close this side asked for.
    retry();
  });
  opened.addEventListener("error", () => {
    // A browser reports an error and then a close for the same failure. The
    // close is where the decision is taken, so this listener exists to stop the
    // error surfacing as an unhandled one, and does nothing else.
  });
}

/**
 * Shortens the two deadlines, for the harness alone.
 *
 * @param wanted The limits, in milliseconds. Omit one to leave it as it is.
 */
export function setLimits(wanted: { silence?: number; opening?: number }): void {
  if (wanted.silence !== undefined) silenceLimit = wanted.silence;
  if (wanted.opening !== undefined) openingLimit = wanted.opening;
}

/**
 * Reads the limits the relay is RUNNING on.
 *
 * Published because the two holds that certify them read the CONSTANTS out of
 * this file's source, and a constant is not a program: `let silenceLimit =
 * SILENCE_LIMIT_MILLISECONDS / 45` would leave both green while a one-second
 * watchdog tore down healthy connections, and so would a `setLimits` call
 * anywhere in the boot. This is what a rule compares against on a fresh page,
 * before it shortens anything.
 *
 * @returns The deadlines in force, in milliseconds.
 */
export function readLimits(): { silence: number; opening: number } {
  return { silence: silenceLimit, opening: openingLimit };
}

/**
 * Starts the relay. Called once, from the boot.
 *
 * @returns Nothing. There is no disposer, because nothing calls one — a
 *   returned one would be a promise this module does not keep.
 */
export function installRelay(): void {
  connect();
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
  // A FORCED CONDITION DOES NOT SURVIVE AN EXPLICIT ASK. The harness's lever
  // exists to DRAW a condition, and a reader who taps « réessayer » has asked
  // for the real one — leaving the override in place made the control dead in
  // the exact state that offers it, which is the §8 defect this whole feature
  // exists to end, sitting inside the feature (B-156).
  forceCondition(null);
  if (retryTimer !== null) {
    globalThis.clearTimeout(retryTimer);
    retryTimer = null;
  }
  letGo("replaced by a manual retry");
  reportCondition({ condition: "connecting", attempts: 0 });
  connect();
}


/**
 * Puts the relay back to a known good place between named states.
 *
 * IT DOES NOT TEAR THE CONNECTION DOWN, and that is the same decision
 * `resetStream()` takes for the same reason: a reset runs between states while
 * the application keeps running, so closing the socket would make every state
 * after the first measure a reconnecting shell. What it clears is what a
 * previous state could have left behind — a forced condition, above all, which
 * would otherwise draw a warning over eighty-four states that have nothing
 * wrong with them.
 */
export function resetRelay(): void {
  forceCondition(null);
  resetCursor();
  letGo("reset");
  if (socket === null) reconnectNow();
}
