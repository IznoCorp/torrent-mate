// The event stream, simulated at the TRANSPORT (D-L10-3).
//
// WHY A FAKE `WebSocket` AND NOT A BYPASS. A driving surface that handed an
// event straight to the relay's dispatcher would be half the work and would
// leave the whole subject of this lot unexercised: the handshake, the `4401`
// close, the backoff, the `?last_id=` cursor and the ping reply would all be
// code no proof ever walks. L08 recorded that its own seam replaces the
// network call in process, so caching, redirects and abort signals are not
// proved by it (D-L08-2). That was the right trade for a mock of a REST call.
// Repeating it on the one lot whose SUBJECT is the transport would leave this
// lot with no proof at all.
//
// IT OBEYS `docs/reference/web-ui.md` § WebSocket Protocol TO THE LETTER, and
// two clauses of it carry weight rather than detail:
//
//   ACCEPT, THEN VALIDATE, THEN CLOSE `4401`. A real server accepts the socket
//   before reading the cookie, so a refused session arrives as a close with a
//   custom code on an OPEN socket. Closing before accept would produce an
//   opaque `1006` in a browser, and the client's terminal-close branch would be
//   dead code in production while passing every test written against it.
//
//   `?last_id=` IS AN EXCLUSIVE LOWER BOUND. `XRANGE (last_id +` replays what
//   came AFTER the cursor. Replaying the cursor itself would deliver one event
//   twice on every reconnect, which is the kind of defect that shows up as a
//   count being one too high in a place nobody is counting.
//
// IT EMITS NOTHING ON ITS OWN (D-L10-4). No timer, no seeded traffic. A named
// state is a world where nothing arrives unless the driver makes it arrive —
// which is what keeps the oracle's recorded states measurable at all, and it is
// the half of the settle decision that no amount of counting could replace.

import {
  BUILD_COMMIT,
  isNewerCursor,
  HELLO_TYPE,
  PING_TYPE,
  type StreamEntry,
} from "./stream-protocol";

export type { StreamEntry };

/** The address the stream is served at, so a rule can read the cursor back. */
const RELAY_ADDRESS = "/ws/events";

/** The state of the simulated server, as a rule reads it. */
type ServerState = {
  entries: StreamEntry[];
  sockets: number;
  refusing: boolean;
  unreachable: boolean;
  stalling: boolean;
  received: string[];
};

/** The log every connection replays from, and the driver appends to. */
let entries: StreamEntry[] = [];
/** The next sequence number, so an id is unique and ordered. */
let sequence = 0;
/** Whether the next connection is refused after being accepted. */
let refusing = false;
/** Whether the server is unreachable — the connection never opens at all. */
let unreachable = false;
/** Whether the server HANGS: it neither accepts nor refuses, and says nothing.
    A different shape from `unreachable`, and the one that matters — a hung 101
    upgrade fires no event at all, so a client waiting on `close` waits for
    ever. `unreachable` at least closes. */
let stalling = false;
/** Every text frame the client has sent — the pongs, in order. */
let received: string[] = [];
/** The sockets currently open, so the driver can push and drop. */
let open: MockSocket[] = [];
/** What the seam replaced, kept so nothing claims an uninstall it cannot do. */
let installed = false;
/** What to call around a delivery, so the settle signal can see one.
    INJECTED, NEVER IMPORTED. `mocks/index.ts` imports this module, so importing
    it back would be the import cycle invariant 8 refuses — and a cycle makes
    every other dependency rule unenforceable, because the cycle IS the
    violation. */
let beganDelivery: () => void = () => {};
let endedDelivery: () => void = () => {};
/** Every address the client has connected to, in order — the closed ones too.
    This is how a rule sees the `?last_id=` cursor a reconnect carried, without
    reaching inside the client to read a private field. */
let connections: string[] = [];

/**
 * Builds the next cursor.
 *
 * @returns An id ordered after every id built before it.
 */
function nextIdentifier(): string {
  sequence += 1;
  return `${sequence}-0`;
}

/**
 * The simulated socket, carrying only what a client may legitimately use.
 *
 * NOT A FULL `WebSocket`. It implements the surface the relay is allowed to
 * touch — the four events, `send`, `close`, `readyState`, `url` — and nothing
 * else. A fake that implemented more would invite a client to depend on more,
 * and the real socket is the one that has to answer in production.
 */
class MockSocket extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readonly url: string;
  readyState: number = MockSocket.CONNECTING;

  /**
   * Opens a simulated connection and runs the handshake.
   *
   * @param address What the client asked to connect to.
   */
  constructor(address: string | URL) {
    super();
    this.url = String(address);
    connections.push(this.url);
    // A MACROTASK, so a client that attaches its listeners after construction
    // — which is every client, because `new WebSocket()` returns before a
    // listener can be added — is listening by the time the handshake runs.
    globalThis.setTimeout(() => this.handshake(), 0);
  }

  /**
   * Accepts the socket, then validates, then either refuses or greets.
   *
   * The order is the whole of this method, and it is the server's order.
   */
  private handshake(): void {
    if (stalling) {
      // NOTHING HAPPENS. No `open`, no `close`, no `error`, and `readyState`
      // stays CONNECTING — which is exactly what a wedged upgrade looks like to
      // a browser, and exactly what no rule could produce before this existed.
      return;
    }
    if (unreachable) {
      // A SERVER THAT IS NOT THERE NEVER ACCEPTS. The browser reports an error
      // and then an unclean `1006` close, with no `open` in between — which is
      // a different path through the client from a session being refused, and
      // the only one that can drive the connection past « reconnecting ».
      this.readyState = MockSocket.CLOSED;
      this.dispatchEvent(new Event("error"));
      this.dispatchEvent(
        new CloseEvent("close", { code: 1006, reason: "unreachable", wasClean: false }),
      );
      return;
    }
    this.readyState = MockSocket.OPEN;
    open.push(this);
    this.dispatchEvent(new Event("open"));
    if (refusing) {
      // ACCEPTED, THEN REFUSED. The socket was open for that one instant, which
      // is exactly what a browser sees when the server reads the cookie after
      // accepting — and it is why the client's `4401` branch is reachable.
      this.shut(4401, "the session is not valid");
      return;
    }
    this.push({ type: HELLO_TYPE, data: { build_commit: BUILD_COMMIT } });
    this.replay();
  }

  /**
   * Replays everything the client's cursor says it has not seen.
   *
   * The bound is EXCLUSIVE: a client that reconnects having seen `3-0` is sent
   * `4-0` onward and never `3-0` again.
   */
  private replay(): void {
    const cursor = new URL(this.url, globalThis.location.origin).searchParams.get("last_id");
    if (cursor === null) return;
    for (const entry of entries) {
      if (isNewerCursor(entry.id, cursor)) this.push(entry);
    }
  }

  /**
   * Delivers one frame to the client.
   *
   * @param payload What to deliver, serialised the way the server serialises it.
   */
  push(payload: unknown): void {
    if (this.readyState !== MockSocket.OPEN) return;
    this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify(payload) }));
  }

  /**
   * Closes the socket from the server's side.
   *
   * @param code The close code.
   * @param reason Why, in the server's own words.
   */
  shut(code: number, reason: string): void {
    if (this.readyState === MockSocket.CLOSED) return;
    this.readyState = MockSocket.CLOSED;
    open = open.filter((socket) => socket !== this);
    this.dispatchEvent(new CloseEvent("close", { code, reason, wasClean: code === 1000 }));
  }

  /**
   * Records a frame the client sent.
   *
   * The client answers a ping with any text frame, so what matters to a rule is
   * THAT it answered and what it said — never a shape this layer imposes.
   *
   * @param frame What the client sent.
   */
  send(frame: string): void {
    received.push(frame);
  }

  /**
   * Closes the socket from the client's side.
   *
   * @param code The close code, defaulting to the clean one.
   * @param reason Why.
   */
  close(code = 1000, reason = ""): void {
    this.shut(code, reason);
  }
}

/**
 * Appends one event to the log and delivers it to whoever is connected.
 *
 * @param type The event class name, as the backend spells it.
 * @param data Its payload.
 * @returns The entry, with the cursor it was given.
 */
function emit(type: string, data: Record<string, unknown> = {}): StreamEntry {
  const entry: StreamEntry = { id: nextIdentifier(), type, data };
  entries.push(entry);
  deliver(() => {
    for (const socket of [...open]) socket.push(entry);
  });
  return entry;
}

/**
 * Delivers, and keeps the settle signal busy until the fan-out has been issued.
 *
 * A DELIVERY GOES NOWHERE NEAR `fetch`, so the request counter cannot see it —
 * and between the frame arriving and the refetch it provokes being issued,
 * that counter reads zero over a world that is about to change. It is the same
 * gap `releaseWaiters()` already defends for a read-render-read waterfall, and
 * it is closed the same way: ONE MACROTASK. A macrotask runs after the whole
 * microtask queue, so a refetch the listener scheduled has already called
 * `fetch` — and therefore already been counted — by the time the delivery is
 * released.
 *
 * @param push What delivers the frames.
 */
function deliver(push: () => void): void {
  beganDelivery();
  push();
  globalThis.setTimeout(endedDelivery, 0);
}

/**
 * Appends several events in one turn, in the order given.
 *
 * A BURST IS ONE TURN, and that is the point of having it at all: a reconnect
 * replays several entries synchronously, and a client that inspects only the
 * newest of them drops the rest. Production lived that defect in three hooks
 * (FRONTEND-DATA-03); a rule can only refuse it here if it can produce it.
 *
 * @param wanted The events, in order.
 * @returns The entries, with the cursors they were given.
 */
function emitBurst(
  wanted: readonly { type: string; data?: Record<string, unknown> }[],
): StreamEntry[] {
  return wanted.map((one) => emit(one.type, one.data ?? {}));
}

/**
 * Sends a keep-alive to every open socket.
 *
 * @returns Nothing.
 */
function ping(): void {
  deliver(() => {
    for (const socket of [...open]) socket.push({ type: PING_TYPE });
  });
}

/**
 * Closes every open socket with a code.
 *
 * @param code The close code. `1000` is a clean teardown; anything else is a
 *   loss the client is expected to notice.
 */
function drop(code = 1006): void {
  deliver(() => {
    for (const socket of [...open]) socket.shut(code, "dropped by the driver");
  });
}

/**
 * Makes the next connection be accepted and then refused with `4401`.
 *
 * @param wanted Whether to refuse.
 */
function refuse(wanted = true): void {
  refusing = wanted;
}

/**
 * Makes every connection fail to open at all.
 *
 * @param wanted Whether the server is unreachable.
 */
function setUnreachable(wanted = true): void {
  unreachable = wanted;
}

/**
 * Makes every connection HANG — neither accepted nor refused.
 *
 * @param wanted Whether the server stalls.
 */
function stall(wanted = true): void {
  stalling = wanted;
}

/**
 * Reads the simulated server's state.
 *
 * @returns What it holds, copied, so a reader cannot write it back.
 */
function state(): ServerState {
  return {
    entries: entries.map((entry) => ({ ...entry })),
    sockets: open.length,
    refusing,
    unreachable,
    stalling,
    received: [...received],
  };
}

/**
 * Forgets everything, so a named state starts from a known stream.
 *
 * It does NOT close the open sockets: `reset()` is called between states while
 * the application keeps running, and tearing its connection down would make
 * every state after the first measure a reconnecting shell.
 */
export function resetStream(): void {
  entries = [];
  sequence = 0;
  refusing = false;
  unreachable = false;
  stalling = false;
  received = [];
  connections = [];
}

/** The driving surface, and the only way into this layer. */
export type StreamDriver = {
  emit: typeof emit;
  emitBurst: typeof emitBurst;
  ping: typeof ping;
  drop: typeof drop;
  refuse: typeof refuse;
  setUnreachable: typeof setUnreachable;
  stall: typeof stall;
  state: typeof state;
  connections: () => string[];
  reset: typeof resetStream;
};

/**
 * Installs the fake transport in place of the browser's `WebSocket`.
 *
 * @param deliveries What to call when a delivery starts and when its fan-out
 *   has been issued, so the settle signal can see a frame in flight.
 * @returns The driving surface.
 */
export function installMockStream(deliveries: {
  began: () => void;
  ended: () => void;
}): StreamDriver {
  beganDelivery = deliveries.began;
  endedDelivery = deliveries.ended;
  if (!installed) {
    installed = true;
    globalThis.WebSocket = MockSocket as unknown as typeof WebSocket;
  }
  return {
    emit,
    emitBurst,
    ping,
    drop,
    refuse,
    setUnreachable,
    stall,
    state,
    connections: () => [...connections],
    reset: resetStream,
  };
}
