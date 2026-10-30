// How long a connection is given, and on what schedule it is tried again.
//
// ITS OWN SUBJECT: `relay.ts` holds a socket and decides what to do with it;
// this holds the numbers that decision is made against, and the two reasons
// each number is what it is. Nothing here touches a socket.

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
 * Published because the holds that certify them read the CONSTANTS out of this
 * file's source, and a constant is not a program: `let silenceLimit =
 * SILENCE_LIMIT_MILLISECONDS / 45` would leave them green while a one-second
 * watchdog tore down healthy connections, and so would a `setLimits` call
 * anywhere in the boot.
 *
 * @returns The deadlines in force, in milliseconds.
 */
export function readLimits(): { silence: number; opening: number } {
  return { silence: silenceLimit, opening: openingLimit };
}

/**
 * How long to wait before the next attempt.
 *
 * @param attempts How many have failed since the last success.
 * @returns The delay, in milliseconds.
 */
export function backoffFor(attempts: number): number {
  return BACKOFF_MILLISECONDS[
    Math.min(attempts - 1, BACKOFF_MILLISECONDS.length - 1)
  ];
}

/**
 * Whether the interface should stop saying « reconnecting ».
 *
 * @param attempts How many have failed since the last success.
 * @returns True once the reader should be told the screen is cold.
 */
export function isLost(attempts: number): boolean {
  return attempts > ATTEMPTS_BEFORE_LOST;
}

/** The deadline a socket that has not spoken yet is held to. */
export const openingDeadline = (): number => openingLimit;
/** The deadline a socket that has spoken is held to. */
export const silenceDeadline = (): number => silenceLimit;
