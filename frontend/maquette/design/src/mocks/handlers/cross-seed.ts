// The cross-seed's acts: cut one pair, search, exclude and undo — each moving
// every reader in the SAME call (L17 DESIGN § 2.3: « a mock that answers
// without moving certifies nothing »).
//
// INVENTED, like its seed: no engine route answers any of these today.
import { DELETE, POST, PUT, field, route } from "./shared";
import { mockState } from "../state";
import { crossSeedKey, crossSeedState, nowSeconds, stopRunningOn } from "../cross-seed-state";
import { trackersState } from "../trackers-state";
import { refused, type MockRoute } from "../router";
import { emit } from "../stream";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];

// The states a search may be asked on (§ 17 point 1): nothing is offered the
// engine would refuse to act on.
const SEARCHABLE: ReadonlySet<string> = new Set(["noMatch", "error", "notSearched"]);

// How long a queued search takes to end, on a real clock: long enough for a
// person to see « en file », short enough to be seen ending in the same visit.
export const SEARCH_MILLISECONDS = 4000;

// The seconds in a day: a spent quota starts again the next day.
const DAY_SECONDS = 86400;

// The event a search's outcome arrives by (F59, demand I).
const SEARCHED = "CrossSeedSearched";

const NO_TORRENT = "no origin torrent carries that hash";
const NO_PAIR = "that torrent has no cross-seed pair on that tracker";
const NOT_RUNNING = "that pair is not running: there is nothing to cut";
const NOT_SEARCHABLE = "a search is offered only on a pair with no match, in error, or not yet searched, and not excluded";
const DUPLICATE = "a search is already queued for that pair";

/**
 * One origin's cross-seed, or a refusal.
 *
 * @param infoHash The origin's hash.
 * @returns The torrent's cross-seed.
 */
function torrentOf(infoHash: string): Schemas["TorrentCrossSeed"] | undefined {
  return crossSeedState().torrents[infoHash];
}

/**
 * Removes one cross-seed's client entry WITHOUT its files, and closes its
 * running obligation « libérée » — never left reading in breach (M4).
 *
 * @param entryHash The cross-seed's own entry, or null when it has none drawn.
 * @returns The entries removed and the obligations released.
 */
function removeEntry(entryHash: string | null): { removed: string[]; released: string[] } {
  if (entryHash === null) return { removed: [], released: [] };
  const held = trackersState();
  const removed = held.downloads.some((entry) => entry.infoHash === entryHash) ? [entryHash] : [];
  held.downloads = held.downloads.filter((entry) => entry.infoHash !== entryHash);
  const released: string[] = [];
  for (const obligation of held.obligations) {
    if (obligation.infoHash !== entryHash || obligation.releasedAt !== null) continue;
    obligation.releasedAt = nowSeconds();
    released.push(entryHash);
  }
  return { removed, released };
}

/**
 * Cuts one running pair: its entry out, its obligation released, the pair
 * stopped by removal and excluded — one call, every projection.
 *
 * @param pair The pair, running.
 * @returns What left and what was released.
 */
function cutPair(pair: Schemas["CrossSeedPair"]): { removed: string[]; released: string[] } {
  const answer = removeEntry(pair.entryHash);
  Object.assign(pair, { state: "stopped", stoppedAt: nowSeconds(), stopCause: "removed", entryHash: null, excluded: true });
  return answer;
}

/**
 * What a switch write earns when its option stops the running pairs too: every
 * tracker whose `cross_seed` the write turns off has its running pairs stopped,
 * their entries out and their obligations released, in the SAME call.
 *
 * @param values The write, keyed `<file>:<key>`.
 */
export function stopRunningCrossSeeds(values: Record<string, unknown>): void {
  for (const tracker of trackersState().trackers) {
    if (values[`tracker:${crossSeedKey(tracker.name)}`] !== false) continue;
    for (const entryHash of stopRunningOn(tracker.name)) removeEntry(entryHash);
  }
}

/**
 * Ends a queued search: the pair takes its outcome and the stream says so.
 * Deterministic — a pair with no match still finds none, any other is injected.
 *
 * @param state The layer's state the search was asked in.
 * @param pair The pair searched.
 * @param infoHash The origin's hash.
 */
function endSearch(state: object, pair: Schemas["CrossSeedPair"], infoHash: string): void {
  if (mockState() !== state || !pair.searching) return;
  const found = pair.state !== "noMatch";
  Object.assign(pair, found
    ? { state: "active", reason: null, waitReason: null, stoppedAt: null, stopCause: null }
    : { state: "noMatch", reason: null, candidate: null }, { at: nowSeconds(), searching: false });
  emit(SEARCHED, { info_hash: infoHash, tracker: pair.tracker, state: pair.state });
}

/** Every route this subject answers. */
export function crossSeedRoutes(): MockRoute[] {
  return [
    route("cutCrossSeed", POST, "/api/torrents/{infoHash}/cross-seed/{tracker}/cut", (request) => {
      const torrent = torrentOf(request.parameters.infoHash);
      if (torrent === undefined) return refused(404, NO_TORRENT);
      const pair = torrent.pairs.find((one) => one.tracker === request.parameters.tracker);
      if (pair === undefined) return refused(404, NO_PAIR);
      if (pair.state !== "active") return refused(409, NOT_RUNNING);
      return cutPair(pair);
    }),
    route("searchCrossSeed", POST, "/api/torrents/{infoHash}/cross-seed/search", (request) => {
      const infoHash = request.parameters.infoHash;
      const torrent = torrentOf(infoHash);
      if (torrent === undefined) return refused(404, NO_TORRENT);
      const tracker = field(request.body, "tracker");
      const asked = typeof tracker === "string" ? torrent.pairs.filter((one) => one.tracker === tracker) : torrent.pairs;
      if (typeof tracker === "string" && asked.length === 0) return refused(404, NO_PAIR);
      // A SECOND ASK ON A PAIR ALREADY SEARCHING is the one refusal (DOIT-4).
      if (asked.some((one) => one.searching) && typeof tracker === "string") return refused(409, DUPLICATE);
      const pairs = asked.filter((one) => SEARCHABLE.has(one.state) && !one.excluded && !one.searching
        && !torrent.titleExcluded);
      if (pairs.length === 0) return refused(409, NOT_SEARCHABLE);
      const held = crossSeedState();
      held.searches.push({ infoHash, tracker: typeof tracker === "string" ? tracker : null });
      // THE QUOTA IS THE ENGINE'S: spent, the search waits for the next day — still « en file ».
      const spent = held.quota.used >= held.quota.perDay;
      held.quota.used += 1;
      const state = mockState();
      for (const pair of pairs) {
        pair.searching = true;
        if (!spent) setTimeout(() => endSearch(state, pair, infoHash), SEARCH_MILLISECONDS);
      }
      return { queued: true, trackers: pairs.map((one) => one.tracker), startsAt: spent ? nowSeconds() + DAY_SECONDS : null };
    }),
    route("writeCrossSeedExclusion", PUT, "/api/torrents/{infoHash}/cross-seed/exclusions", (request) => {
      const infoHash = request.parameters.infoHash;
      const torrent = torrentOf(infoHash);
      if (torrent === undefined) return refused(404, NO_TORRENT);
      const tracker = field(request.body, "tracker");
      if (typeof tracker === "string") {
        const pair = torrent.pairs.find((one) => one.tracker === tracker);
        if (pair === undefined) return refused(404, NO_PAIR);
        pair.excluded = true;
        return { infoHash, tracker, excluded: true };
      }
      // « NE PLUS PARTAGER CE TITRE »: every running pair cut, every pair and the title excluded.
      for (const pair of torrent.pairs) {
        if (pair.state === "active") cutPair(pair);
        pair.excluded = true;
      }
      torrent.titleExcluded = true;
      return { infoHash, tracker: null, excluded: true };
    }),
    route("undoCrossSeedExclusion", DELETE, "/api/torrents/{infoHash}/cross-seed/exclusions", (request) => {
      const infoHash = request.parameters.infoHash;
      const torrent = torrentOf(infoHash);
      if (torrent === undefined) return refused(404, NO_TORRENT);
      const tracker = field(request.body, "tracker");
      if (typeof tracker === "string") {
        const pair = torrent.pairs.find((one) => one.tracker === tracker);
        if (pair === undefined) return refused(404, NO_PAIR);
        pair.excluded = false;
        return { infoHash, tracker, excluded: false };
      }
      torrent.titleExcluded = false;
      for (const pair of torrent.pairs) pair.excluded = false;
      return { infoHash, tracker: null, excluded: false };
    }),
  ];
}
