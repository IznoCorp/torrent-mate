// A tunnel CLOSED — its medium vanished (Q8) or a later choice in place (Q9) —
// posed for the harness, and « Marquer comme vu » that forgets it.
//
// A DERIVATION, SHOWN AS ONE: no seeded row is closed. The engine closes the
// tunnel with its reason (BK3, BK4) and stores, per account, that it was seen
// (BK5); the layer poses the closure on a real acquisition and forgets it once
// seen, in every world.
import { acquisitionKey } from "../../lib/arrival-slots";
import { currentRung } from "../../lib/current-rung";
import { mockState } from "../state";
import { trackersState } from "../trackers-state";
import { forgetLadder, ladderOf, ownTimeOf, rungIndex, stripPosition } from "./ladder";
import { POST, route } from "./shared";
import type { MockRoute } from "../router";
import type { components } from "../../contract/types";

type QueueCard = components["schemas"]["QueueCard"];
type Closure = components["schemas"]["Closure"];
type Rung = components["schemas"]["JourneyStage"];

// Every list of the layer a card of the queue is served from, in both worlds.
const QUEUE_LISTS = [
  "inFlight", "inFlightReel", "moving", "movingReel", "blocked", "takeable",
  "stuck", "stuckLoaded", "settled", "settledLoaded",
] as const;

// A later choice in place: the release is not filed, its strip stops on « rangé ».
const SUPERSEDED = "superseded";
const SHELVED = "shelved";
// Where a closed tunnel stops: the rung it was on, never reached.
const NOT_REACHED = "pending";
const DONE = "done";
// A rung running now: a pack verified in Plex, a medium back taken again.
const RUNNING = "now";
// A torrent the client still shares.
const SEEDING = "seeding";
// Between a title and the season or episode it is of, in a key.
const KEY_SEPARATOR = "|";
// One minute, in the epoch seconds a closure's time is written in.
const MINUTE = 60;
// A torrent's hash is forty hexadecimal figures.
const HASH_LENGTH = 40;
const HEX = 16;
const FNV_OFFSET = 0x811c9dc5;
const FNV_PRIME = 0x01000193;
// The figures one 32-bit word spells.
const HASH_WORD = 8;

/** What a closure names besides its reason. */
export type ClosureDetails = {
  /** For a superseded release, its own release line — the torrent that keeps seeding. */
  release?: string;
  /** How many minutes ago the tunnel closed — what orders the list (DECIDED 1). */
  minutesAgo?: number;
};

/**
 * The ladder a closed tunnel keeps: where it stood when it closed, that rung
 * never reached — or, for a superseded release, « rangé » not done.
 *
 * @param row The acquisition's row.
 * @param reason Why it closed.
 * @returns The rungs, held on the row itself.
 */
function closedLadder(row: QueueCard, reason: Closure["reason"]): Rung[] {
  const key = acquisitionKey(row);
  const laid = structuredClone(ladderOf(key, stripPosition(row.strip), { times: ownTimeOf(row) }));
  const stopped = reason === SUPERSEDED ? rungIndex(SHELVED) : currentRung(laid);
  return laid.map((rung, index) => {
    if (index < stopped) return reason === SUPERSEDED ? { ...rung, state: DONE } : rung;
    const { reason: cause, resumes, blockedSince, ...kept } = rung;
    void cause;
    void resumes;
    void blockedSince;
    return { ...kept, state: NOT_REACHED, when: "" };
  });
}

/**
 * A hash for a posed torrent, the same for the same release on every pose.
 *
 * @param name The release line.
 * @returns Forty hexadecimal figures.
 */
function posedHash(name: string): string {
  let figures = "";
  for (let part = 0; figures.length < HASH_LENGTH; part += 1) {
    let hash = FNV_OFFSET;
    for (const character of `${name}#${part}`) hash = Math.imul(hash ^ character.charCodeAt(0), FNV_PRIME) >>> 0;
    figures += hash.toString(HEX).padStart(HASH_WORD, "0");
  }
  return figures.slice(0, HASH_LENGTH);
}

/**
 * The superseded release's torrent, seeding in the client (Q9: « son torrent
 * continue de semer ») — posed, when the client does not hold it already.
 *
 * @param row The acquisition's row.
 * @param release Its release line.
 */
function keepSeeding(row: QueueCard, release: string): void {
  const downloads = trackersState().downloads;
  if (downloads.some((entry) => entry.name === release)) return;
  const [template] = downloads;
  if (template === undefined) return;
  downloads.push({
    ...structuredClone(template),
    infoHash: posedHash(release),
    name: release,
    title: row.title,
    kind: row.kind === "movie" ? "movie" : row.episode == null ? "season" : "episode",
    season: row.season ?? null,
    episode: row.episode ?? null,
    state: SEEDING,
    ids: row.ids ?? null,
    poster: row.poster ?? null,
  } as (typeof downloads)[number]);
}

/**
 * Closes an acquisition's tunnel with its reason, until the layer is next
 * reset or the closure is seen — a derivation, shown as one (BK3, BK4).
 *
 * EVERY ROW the acquisition is served from closes, in both worlds: its card
 * then stands in « À traiter », its strip stopped where the tunnel was, until
 * the account marks it seen. A superseded release's torrent keeps seeding.
 *
 * @param subject The acquisition's key — « Silo|S03E07 », or a title.
 * @param reason Why it closed.
 * @param winner For a superseded release, the release line of the file in place.
 * @param details Its own release, and how long ago it closed.
 */
export function poseClosure(
  subject: string, reason: Closure["reason"], winner: string | null = null, details: ClosureDetails = {},
): void {
  const state = mockState();
  const at = Math.floor(Date.now() / 1000) - (details.minutesAgo ?? 0) * MINUTE;
  for (const list of QUEUE_LISTS) {
    state[list] = state[list].map((row) => {
      if (acquisitionKey(row) !== subject || row.closure != null) return row;
      const release = details.release ?? row.release ?? null;
      if (reason === SUPERSEDED && release !== null) keepSeeding(row, release);
      // THE CLOSED CARD CARRIES ITS OWN LADDER, and no strip: a medium back
      // opens a NEW tunnel under the same key, with a ladder of its own.
      const { strip, absorbedBy, ...closed } = row;
      void strip;
      void absorbedBy;
      return { ...closed, release, ladder: closedLadder(row, reason), closure: { reason, at, winner } };
    });
  }
}

/**
 * The medium comes back (Q8: « un média qui revient plus tard ouvre un nouveau
 * tunnel »): a fresh tunnel under the same key, taken now — the closed one, not
 * yet seen, still says its own.
 *
 * @param subject The acquisition's key.
 */
export function poseMediumBack(subject: string): void {
  const state = mockState();
  forgetLadder(subject);
  for (const list of QUEUE_LISTS) {
    const closed = state[list].find((row) => acquisitionKey(row) === subject && row.closure != null);
    if (closed === undefined) continue;
    const { closure, ladder, ...fresh } = closed;
    void closure;
    void ladder;
    state[list] = [{ ...fresh, strip: [RUNNING, 0, 0, 0, 0] }, ...state[list]];
  }
}

/**
 * The medium found in the library, filed by hand elsewhere (Q8: « rangé à la
 * main ailleurs, il part simplement »): its tunnel ends with no closure and no
 * card.
 *
 * @param subject The acquisition's key.
 */
export function poseFiledByHand(subject: string): void {
  const state = mockState();
  for (const list of QUEUE_LISTS) state[list] = state[list].filter((row) => acquisitionKey(row) !== subject);
  forgetLadder(subject);
}

/**
 * A pack filed, save the episodes a later choice holds (Q9, maquette-blocked §
 * 1.6): its tunnel went to its end — « rangé » done, verified in Plex now —
 * and its journey names each episode kept; nothing closed, no card.
 *
 * @param pack The pack's key, « Silo|S03 ».
 * @param kept The episodes left in place, « S03E07 ».
 */
export function poseKeptNewer(pack: string, kept: string[]): void {
  poseFiled(pack)[rungIndex(SHELVED)].keptNewer = kept;
  // THE EPISODES KEPT went to their own end, filed before the pack: no card.
  const state = mockState();
  const title = pack.split(KEY_SEPARATOR)[0];
  const ended = new Set(kept.map((episode) => title + KEY_SEPARATOR + episode));
  for (const list of QUEUE_LISTS) state[list] = state[list].filter((row) => !ended.has(acquisitionKey(row)));
}

/**
 * A pack filed and verifying, the release it superseded closed apart — what
 * stands in place of a superseded episode.
 *
 * @param pack The pack's key.
 * @returns The pack's ladder, as the layer now holds it.
 */
export function poseFiled(pack: string): Rung[] {
  forgetLadder(pack);
  return ladderOf(pack, { current: rungIndex("verified"), state: RUNNING });
}

/** The routes of a closure: « Marquer comme vu ». */
export function closureRoutes(): MockRoute[] {
  return [
    // SEEN IS GONE, for this account, in every world: the closed tunnel's card
    // leaves the queue's answer for good. IDEMPOTENT — a closure already seen,
    // or none, answers the same.
    route("dismissClosure", POST, "/acquisition/journeys/{infoHash}/closure/seen", (request) => {
      const subject = request.parameters.infoHash;
      const state = mockState();
      for (const list of QUEUE_LISTS)
        state[list] = state[list].filter((row) => acquisitionKey(row) !== subject || row.closure == null);
      return { ok: true };
    }),
  ];
}
