/**
 * ``useEventStream`` — the app's single live-event WebSocket (tm-shell §5.3).
 *
 * Connects to ``/ws/events`` (see ``personalscraper/web/ws/routes.py``), performs
 * the authenticated handshake, replays missed events on reconnect (via the
 * persisted stream cursor), and exposes a small reactive surface used by the
 * shell's StatusDot and (wave-later) the dashboard feed. Exactly **one** socket
 * per app is intended — mount the hook once, behind {@link EventStreamProvider},
 * and read it everywhere through context.
 *
 * Lifecycle / resilience:
 *
 * - **Handshake** — on ``ws.hello`` the ``build_commit`` is captured and the state
 *   flips to ``'connected'``. TCP-open alone is not "connected".
 * - **Connect-timeout** — a hung 101 upgrade never fires ``onopen``; a 10 s timer
 *   armed at ``connect()`` force-closes it so the reconnect path runs instead of
 *   the StatusDot stalling on ``'connecting'`` forever.
 * - **Keep-alive** — on ``ws.ping`` the client replies ``pong``. A 45 s watchdog
 *   (re-armed on every frame) force-closes a silent peer so the reconnect path
 *   runs — the server pings every 30 s, so 45 s of silence means a dead link.
 * - **Reconnect** — exponential backoff 1 s → 30 s with 50–100 % jitter; the
 *   ladder resets on a successful handshake.
 * - **Replay** — each event ``id`` is persisted to ``localStorage`` and passed
 *   back as ``?last_id=`` so the server ``XRANGE``-replays only what was missed.
 *   A monotonic cursor guard drops any event id at or below the last applied one,
 *   so a stale ``last_id`` (older than the stream's trim window) or a server-side
 *   overlap resend can never replay-flood or double-deliver into the ring.
 * - **Auth lost** — a ``4401`` close is terminal: the state goes ``'disconnected'``
 *   and the socket is **not** reconnected (the REST 401 flow owns the redirect).
 * - **Bounded memory** — events are kept in a ring capped at
 *   {@link EVENTS_CAP}; the oldest are dropped past the cap.
 * - **StrictMode-safe** — a per-effect ``disposed`` token neutralises every async
 *   callback (timers, socket handlers) once the effect is torn down, so React
 *   19's dev double-invoke leaves a single surviving socket.
 */

import { useEffect, useState } from "react";

import { isHello, isPing, parseServerMessage, type EventMessage } from "@/api/events";

/** ``localStorage`` key holding the last seen stream cursor (for replay). */
export const LAST_EVENT_ID_STORAGE_KEY = "torrentmate:last_event_id";

/** Silence (no frame) beyond this, in ms, force-closes the socket → reconnect. */
const WATCHDOG_MS = 45_000;
/** No ``onopen`` within this many ms of ``connect()`` → force-close + reconnect. */
const CONNECT_TIMEOUT_MS = 10_000;
/** First reconnect delay, in ms (doubles each attempt up to the ceiling). */
const BACKOFF_MIN_MS = 1_000;
/** Reconnect delay ceiling, in ms. */
const BACKOFF_MAX_MS = 30_000;
/** Maximum retained events before the oldest are evicted from the ring. */
export const EVENTS_CAP = 10_000;
/** Custom close code the server uses to signal a lost / invalid session. */
const CLOSE_AUTH_LOST = 4401;

/** The connection lifecycle exposed to the UI (drives the StatusDot). */
export type ConnectionState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected";

/**
 * The reactive value returned by {@link useEventStream} / read via context.
 *
 * Attributes:
 *   events: The bounded, append-ordered list of received domain events.
 *   connectionState: The live socket lifecycle state.
 *   buildCommit: The backend build commit from the handshake, or ``null`` before
 *     the first successful ``ws.hello``.
 *   lastEventId: The most recent persisted stream cursor, or ``null`` when none
 *     has been seen yet on this device.
 */
export interface EventStreamState {
  readonly events: readonly EventMessage[];
  readonly connectionState: ConnectionState;
  readonly buildCommit: string | null;
  readonly lastEventId: string | null;
}

/** Read the persisted last-event cursor, tolerating unavailable storage. */
function readLastEventId(): string | null {
  try {
    return window.localStorage.getItem(LAST_EVENT_ID_STORAGE_KEY);
  } catch {
    return null;
  }
}

/** Persist the last-event cursor, tolerating unavailable storage. */
function writeLastEventId(id: string): void {
  try {
    window.localStorage.setItem(LAST_EVENT_ID_STORAGE_KEY, id);
  } catch {
    // Storage blocked (private mode / quota) — replay simply restarts from live.
  }
}

/** Parse a Redis stream id ``"<ms>-<seq>"`` into a numeric ``[ms, seq]`` tuple. */
function parseStreamId(id: string): [number, number] {
  const dash = id.indexOf("-");
  const msPart = dash === -1 ? id : id.slice(0, dash);
  const seqPart = dash === -1 ? "" : id.slice(dash + 1);
  const ms = Number(msPart);
  const seq = Number(seqPart);
  return [Number.isFinite(ms) ? ms : 0, Number.isFinite(seq) ? seq : 0];
}

/**
 * Is stream id ``id`` strictly newer than ``since``?
 *
 * The Redis stream cursor is monotonically increasing, so this doubles as the
 * replay/duplicate guard: an id at or below the last applied one is a stale
 * replay (or a server-side overlap resend) and must be dropped.
 *
 * Args:
 *   id: The candidate event's stream id.
 *   since: The last applied stream id, or ``null`` when none applied yet.
 *
 * Returns:
 *   ``true`` when ``id`` is strictly greater than ``since`` (or ``since`` is
 *   ``null`` / empty).
 */
export function isNewerStreamId(id: string, since: string | null): boolean {
  if (since === null || since === "") {
    return true;
  }
  const [idMs, idSeq] = parseStreamId(id);
  const [sinceMs, sinceSeq] = parseStreamId(since);
  if (idMs !== sinceMs) {
    return idMs > sinceMs;
  }
  return idSeq > sinceSeq;
}

/** Build the ``/ws/events`` URL, appending ``?last_id=`` when a cursor exists. */
function buildEventsUrl(lastId: string | null): string {
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const base = `${scheme}://${window.location.host}/ws/events`;
  if (lastId === null || lastId === "") {
    return base;
  }
  return `${base}?last_id=${encodeURIComponent(lastId)}`;
}

/**
 * Open and manage the single live-event WebSocket.
 *
 * Returns:
 *   The reactive {@link EventStreamState}. The socket is opened on mount and
 *   closed on unmount; consumers never touch the socket directly.
 */
export function useEventStream(): EventStreamState {
  const [events, setEvents] = useState<readonly EventMessage[]>([]);
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("connecting");
  const [buildCommit, setBuildCommit] = useState<string | null>(null);
  const [lastEventId, setLastEventId] = useState<string | null>(() =>
    readLastEventId(),
  );

  useEffect(() => {
    // Per-effect token. Once the effect is torn down (unmount, or StrictMode's
    // dev double-invoke), `disposed` flips and every async callback becomes a
    // no-op, so a single socket survives and no stale timer resurrects one.
    let disposed = false;
    let socket: WebSocket | null = null;
    let attempt = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let watchdogTimer: ReturnType<typeof setTimeout> | null = null;
    let connectTimer: ReturnType<typeof setTimeout> | null = null;
    // Highest stream id applied to the ring so far — the monotonic guard that
    // drops stale replays and duplicate deliveries. Seeded from the persisted
    // cursor so a reconnect replay never re-appends already-seen events.
    let lastAppliedId = readLastEventId();

    const clearReconnect = (): void => {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const clearWatchdog = (): void => {
      if (watchdogTimer !== null) {
        clearTimeout(watchdogTimer);
        watchdogTimer = null;
      }
    };

    const clearConnect = (): void => {
      if (connectTimer !== null) {
        clearTimeout(connectTimer);
        connectTimer = null;
      }
    };

    // Re-armed on every inbound frame; firing means the peer went silent past
    // the ping cadence, so we force-close and let `onclose` reconnect.
    const armWatchdog = (): void => {
      clearWatchdog();
      watchdogTimer = setTimeout(() => {
        if (disposed) {
          return;
        }
        socket?.close();
      }, WATCHDOG_MS);
    };

    const scheduleReconnect = (): void => {
      if (disposed) {
        return;
      }
      clearReconnect();
      const ceiling = Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** attempt);
      // Full jitter over [50 %, 100 %] of the ceiling avoids reconnect stampedes.
      const delay = ceiling * (0.5 + Math.random() * 0.5);
      attempt += 1;
      setConnectionState("reconnecting");
      reconnectTimer = setTimeout(() => {
        if (disposed) {
          return;
        }
        connect();
      }, delay);
    };

    function connect(): void {
      if (disposed) {
        return;
      }
      clearWatchdog();
      clearConnect();
      const ws = new WebSocket(buildEventsUrl(readLastEventId()));
      socket = ws;

      // Connect-timeout: a hung 101 upgrade never fires `onopen`, which would
      // otherwise strand the state on 'connecting' forever. Force-close so
      // `onclose` runs the reconnect ladder.
      connectTimer = setTimeout(() => {
        if (disposed) {
          return;
        }
        ws.close();
      }, CONNECT_TIMEOUT_MS);

      ws.onopen = (): void => {
        if (disposed) {
          return;
        }
        // Opened in time — cancel the connect-timeout. Open ≠ connected: wait for
        // `ws.hello` to confirm the auth handshake. Arm the silence watchdog now
        // so a silent-after-open peer still reconnects.
        clearConnect();
        armWatchdog();
      };

      ws.onmessage = (event): void => {
        if (disposed) {
          return;
        }
        const raw: unknown = event.data;
        if (typeof raw !== "string") {
          return;
        }
        // Any frame proves liveness → reset the silence watchdog.
        armWatchdog();

        const msg = parseServerMessage(raw);
        if (msg === null) {
          return;
        }

        if (isHello(msg)) {
          attempt = 0; // A good handshake resets the backoff ladder.
          setBuildCommit(msg.data.build_commit);
          setConnectionState("connected");
          return;
        }

        if (isPing(msg)) {
          try {
            ws.send("pong");
          } catch {
            // Socket already closing — `onclose` will drive the reconnect.
          }
          return;
        }

        // Domain event: drop stale replays / duplicate deliveries via the
        // monotonic cursor guard, then persist the cursor and append into the
        // bounded ring. React coalesces a synchronous replay burst into a single
        // re-render, so the appends are effectively batched.
        if (!isNewerStreamId(msg.id, lastAppliedId)) {
          return;
        }
        lastAppliedId = msg.id;
        writeLastEventId(msg.id);
        setLastEventId(msg.id);
        setEvents((prev) => {
          const appended = [...prev, msg];
          return appended.length > EVENTS_CAP
            ? appended.slice(appended.length - EVENTS_CAP)
            : appended;
        });
      };

      ws.onerror = (): void => {
        // Errors surface as a paired `close`; the state transition lives there.
      };

      ws.onclose = (event): void => {
        if (disposed) {
          return;
        }
        clearWatchdog();
        clearConnect();
        socket = null;
        if (event.code === CLOSE_AUTH_LOST) {
          // Session lost — terminal. The REST 401 flow owns the /login redirect;
          // reconnecting would only earn another 4401.
          setConnectionState("disconnected");
          return;
        }
        scheduleReconnect();
      };
    }

    connect();

    return (): void => {
      disposed = true;
      clearReconnect();
      clearWatchdog();
      clearConnect();
      if (socket !== null) {
        // Detach handlers first so the imminent close can't schedule a reconnect.
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        socket.close();
        socket = null;
      }
    };
  }, []);

  return { events, connectionState, buildCommit, lastEventId };
}
