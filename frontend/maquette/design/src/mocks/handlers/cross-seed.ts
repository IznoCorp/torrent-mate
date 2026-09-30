// The cross-seed's acts: cut one pair, search, upload, exclude and undo — each
// moving every reader in the SAME call (L17 DESIGN § 2.3: « a mock that answers
// without moving certifies nothing »).
//
// INVENTED, like its seed: no engine route answers any of these today.
import { DELETE, POST, PUT, field, route } from "./shared";
import { mockState } from "../state";
import { crossSeedKey, crossSeedState, nowSeconds, stopRunningOn, switchOf, uploadsKey } from "../cross-seed-state";
import { trackersState } from "../trackers-state";
import { refused, type MockRoute } from "../router";
import { emit } from "../stream";
import type { components } from "../../contract/types";

type Schemas = components["schemas"];

// The states a search may be asked on (§ 17 point 1): nothing is offered the
// engine would refuse to act on. A stopped pair resumes by a search (§ 3.3).
const SEARCHABLE: ReadonlySet<string> = new Set(["noMatch", "error", "notSearched", "stopped"]);

// How long a queued search takes to end, on a real clock: long enough for a
// person to see « en file », short enough to be seen ending in the same visit.
export const SEARCH_MILLISECONDS = 4000;

// The seconds in a day: a spent quota starts again the next day.
const DAY_SECONDS = 86400;

// The event a search's outcome arrives by (F59, demand I).
const SEARCHED = "CrossSeedSearched";

// THE SAME TWO EVENTS a found cross-seed ends by, never a third (L23 § 1): an
// upload published, or refused.
const INJECTED = "CrossSeedInjected";
const REJECTED = "CrossSeedRejected";

// The states an upload may be asked on (L23 § 1 clause 1): only where nothing
// already cross-seeds — never « stoppé », which a search resumes.
const UPLOADABLE: ReadonlySet<string> = new Set(["noMatch", "error", "notSearched"]);

const NO_TORRENT = "no origin torrent carries that hash";
const NO_PAIR = "that torrent has no cross-seed pair on that tracker";
const NOT_RUNNING = "that pair is not running: there is nothing to cut";
const NOT_SEARCHABLE = "a search is offered only on a pair with no match, in error, not yet searched or stopped, not excluded, its own tracker's switch on, its original complete";
const DUPLICATE = "a search is already queued for that pair";
const NOT_UPLOADABLE = "an upload is offered only on a pair with no match, in error or not yet searched, not excluded, its original active in the client, complete and seeding, its tracker's cross-seed and « accepte les uploads » switches on";
const DUPLICATE_UPLOAD = "an upload is already queued for that pair";

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

/**
 * The hash of the torrent an upload publishes: the engine builds a new one, so
 * the layer derives it — deterministic, never the origin's own.
 *
 * @param infoHash The origin's hash.
 * @param tracker The tracker it is published on.
 * @returns A hash of the same length.
 */
function publishedHash(infoHash: string, tracker: string): string {
  const salt = [...tracker].reduce((sum, letter) => (sum * 31 + letter.charCodeAt(0)) % 0xffffffff, 7);
  return salt.toString(16).padStart(8, "0").slice(0, 8) + infoHash.slice(8);
}

/**
 * Ends a queued upload: the pair takes the outcome the scenario chose — by
 * default published, a new entry on its tracker reading « publié par vous »
 * (round 11 OPEN 5 = B) — and the stream says so by the SAME two events.
 *
 * @param state The layer's state the upload was asked in.
 * @param pair The pair uploaded to.
 * @param infoHash The origin's hash.
 */
function endUpload(state: object, pair: Schemas["CrossSeedPair"], infoHash: string): void {
  if (mockState() !== state || !pair.uploading) return;
  const outcome = crossSeedState().uploadOutcomes[`${infoHash}:${pair.tracker}`] ?? { reason: null };
  const at = nowSeconds();
  if (outcome.reason !== null) {
    Object.assign(pair, {
      state: "error", reason: outcome.reason, trackerReason: outcome.trackerReason, via: "upload", candidate: null,
      waitReason: null, at, uploading: false,
    });
    emit(REJECTED, { info_hash: infoHash, tracker: pair.tracker, reason: outcome.reason });
    return;
  }
  const held = trackersState();
  const origin = held.downloads.find((entry) => entry.infoHash === infoHash);
  const entryHash = publishedHash(infoHash, pair.tracker);
  if (origin !== undefined && !held.downloads.some((entry) => entry.infoHash === entryHash)) {
    held.downloads.push({
      ...structuredClone(origin), infoHash: entryHash, tracker: pair.tracker, provenance: "published", ratio: 0,
      deadline: null, addedAt: at, uploadedBytes: 0, downloadedBytes: 0, downloadRate: null, uploadRate: null,
    });
  }
  Object.assign(pair, {
    state: "active", reason: null, trackerReason: null, via: "upload", candidate: origin?.name ?? null,
    waitReason: null, stoppedAt: null, stopCause: null, entryHash, at, uploading: false,
  });
  emit(INJECTED, { info_hash: entryHash, tracker: pair.tracker, origin: infoHash });
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
      // THE ENGINE SEARCHES NOTHING FOR AN ORIGIN STILL DOWNLOADING.
      const complete = trackersState().downloads.some((entry) => entry.infoHash === infoHash && entry.progress >= 1);
      const tracker = field(request.body, "tracker");
      const asked = typeof tracker === "string" ? torrent.pairs.filter((one) => one.tracker === tracker) : torrent.pairs;
      if (typeof tracker === "string" && asked.length === 0) return refused(404, NO_PAIR);
      // A SECOND ASK ON A PAIR ALREADY SEARCHING is the one refusal (DOIT-4).
      if (asked.some((one) => one.searching) && typeof tracker === "string") return refused(409, DUPLICATE);
      // NOTHING IS OFFERED THE ENGINE WOULD REFUSE (§ 17 point 1): a tracker whose
      // own cross-seed switch is off searches nothing there, whatever the pair's state.
      const pairs = asked.filter((one) => SEARCHABLE.has(one.state) && !one.excluded && !one.searching
        && !torrent.titleExcluded && complete && switchOf(crossSeedKey(one.tracker)));
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
    route("uploadCrossSeed", POST, "/api/torrents/{infoHash}/cross-seed/{tracker}/upload", (request) => {
      const infoHash = request.parameters.infoHash;
      const torrent = torrentOf(infoHash);
      if (torrent === undefined) return refused(404, NO_TORRENT);
      const tracker = request.parameters.tracker;
      const pair = torrent.pairs.find((one) => one.tracker === tracker);
      if (pair === undefined) return refused(404, NO_PAIR);
      // A SECOND ASK ON A PAIR ALREADY UPLOADING is a duplicate (DOIT-4).
      if (pair.uploading) return refused(409, DUPLICATE_UPLOAD);
      // ONLY A TORRENT ACTIVE IN THE CLIENT, COMPLETE AND SEEDING (round 11 OPEN 1 = A).
      const seeding = trackersState().downloads
        .some((entry) => entry.infoHash === infoHash && entry.progress >= 1 && entry.state === "seeding");
      // NOTHING OFFERED THE ENGINE WOULD REFUSE (§ 17 point 1): both of the
      // tracker's switches on — its cross-seed, and its « accepte les uploads ».
      const uploadable = UPLOADABLE.has(pair.state) && !pair.excluded && !pair.searching && !torrent.titleExcluded
        && seeding && switchOf(crossSeedKey(tracker)) && switchOf(uploadsKey(tracker));
      if (!uploadable) return refused(409, NOT_UPLOADABLE);
      crossSeedState().uploads.push({ infoHash, tracker });
      pair.uploading = true;
      const state = mockState();
      setTimeout(() => endUpload(state, pair, infoHash), SEARCH_MILLISECONDS);
      return { queued: true, tracker };
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
