// What the simulated server HOLDS.
//
// ITS OWN SUBJECT: `stream.ts` is a socket and a driving surface — how a
// connection behaves and what a rule can ask it to do — and this is the state
// both of them read. The log, the cursor sequence, the sockets currently up,
// the frames the client has sent, and the three dials that make a connection
// fail in the three ways it can.
//
// IT KNOWS NOTHING ABOUT A SOCKET. Nothing here dispatches an event or reads a
// `readyState`; a reader of this file learns what the server remembers and
// nothing about how it speaks.
import type { StreamEntry } from "./stream-protocol";

/** The log every connection replays from, and the driver appends to. */
export const log: { entries: StreamEntry[]; sequence: number } = {
  entries: [],
  sequence: 0,
};

/** The three ways a connection can fail, and one is not like the others. */
export const dials = {
  /** Accepted, then closed `4401`: the session is not valid. */
  refusing: false,
  /** Never accepted at all: the server is not there. */
  unreachable: false,
  /** Neither accepted nor refused: a wedged upgrade, and the only shape that
      fires no event whatsoever. */
  stalling: false,
};

/** Every text frame the client has sent — the pongs, in order. */
export let received: string[] = [];
/** Every address the client has connected to, including the closed ones. */
export let connections: string[] = [];

/** What to call around a delivery, so the settle signal can see one.
    INJECTED, NEVER IMPORTED. `mocks/index.ts` imports this layer, so importing
    it back would be the import cycle invariant 8 refuses. */
export const deliveries = {
  began: () => {},
  ended: () => {},
};

/**
 * Builds the next cursor.
 *
 * @returns An id ordered after every id built before it.
 */
export function nextIdentifier(): string {
  log.sequence += 1;
  return `${log.sequence}-0`;
}

/**
 * Records a frame the client sent.
 *
 * The client answers a ping with any text frame, so what matters to a rule is
 * THAT it answered and what it said — never a shape this layer imposes.
 *
 * @param frame What the client sent.
 */
export function recordFrame(frame: string): void {
  received.push(frame);
}

/**
 * Records an address the client connected to.
 *
 * @param address What it asked for, cursor included.
 */
export function recordConnection(address: string): void {
  connections.push(address);
}

/** Forgets everything, so a named state starts from a known stream. */
export function resetServer(): void {
  log.entries = [];
  log.sequence = 0;
  dials.refusing = false;
  dials.unreachable = false;
  dials.stalling = false;
  received = [];
  connections = [];
}
