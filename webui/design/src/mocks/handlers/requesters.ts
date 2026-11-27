// Who asked for each acquisition, and what each of them set on it — the plural
// requesters every follow and every queue card carries (round 9 Q16, F27), and
// each requester's own quality and pause (round 10 Q6).
//
// DECORATED AT THE ANSWER, never written into the seeds: the seeds are the
// owner's real acquisitions, and who else asked is invented (`../identity`).
import {
  moveRequester,
  preferencesOf,
  requestersOf,
  rightsOfAccount,
  signedInId,
  signedInRights,
  type Preference,
} from "../identity";
import { followForKey, titlesOfKey } from "../follow-key";
import { refused, type MockRoute } from "../router";
import { POST, PUT, field, route, text } from "./shared";
import type { components } from "../../contract/types";
import type { Right } from "../../lib/rights";

type Schemas = components["schemas"];

// The quality floors, lowest first: the highest a right-holding requester set wins.
const FLOORS = ["720p", "1080p", "2160p"];
const FORBIDDEN = 403;
// The status a paused follow carries — the generic pause's own.
const PAUSED = "disabled";
const MISSING = 404;
const NOT_THEIRS = "the caller is not among this acquisition's requesters";
const NO_SUCH = "no acquisition answers to that key, or that requester";

/**
 * Adds its requesters to every row that names an acquisition.
 *
 * @param rows Follows or queue cards, each keyed by its title.
 * @returns The same rows, each carrying `requesters`.
 */
export function withRequesters<Row extends { title: string }>(rows: Row[]): (Row & { requesters: Schemas["AccountRef"][] })[] {
  // THE CALLER'S SUBSET, unless its role sees everyone's (§ 17: « par défaut,
  // pas les acquisitions qu'il n'a pas demandées »). A filter on a 200, never a
  // 403: an account with no acquisition right reads an empty list.
  const sees = signedInRights().holds("acquisition.see.others");
  return rows
    .map((row) => ({ ...row, requesters: requestersOf(row.title) }))
    .filter((row) => sees || row.requesters.some((one) => one.id === signedInId()));
}

/**
 * The settings in force on one acquisition, from the requesters who may set them.
 *
 * ONLY A REQUESTER WHOSE ROLE HOLDS THE RIGHT COUNTS (round 10 Q6, precised): a
 * setting written before a role lost the right, or seeded for one that never
 * had it, enters neither « the highest wins » nor « every one asked ».
 *
 * @param title The acquisition.
 * @returns The caller's own settings and the ones in force.
 */
function settingsOf(title: string): Pick<Schemas["Follow"], "ownQuality" | "quality" | "ownPaused" | "paused"> {
  const preferences = preferencesOf(title);
  const holders = (right: Right) => requestersOf(title)
    .map((one) => one.id)
    .filter((id) => rightsOfAccount(id).holds(right));
  const floors = holders("acquisition.quality.own")
    .map((id) => preferences[id]?.quality)
    .filter((floor): floor is string => typeof floor === "string");
  const quality = floors.sort((left, right) => FLOORS.indexOf(right) - FLOORS.indexOf(left))[0] ?? null;
  const pausers = holders("acquisition.pause.own");
  const own = preferences[signedInId()] ?? {};
  return {
    ownQuality: own.quality ?? null,
    quality,
    ownPaused: own.paused === true,
    paused: pausers.length > 0 && pausers.every((id) => preferences[id]?.paused === true),
  };
}

/**
 * Adds its requesters and its settings to every follow.
 *
 * @param follows The follows.
 * @returns The same follows, decorated.
 */
export function withAcquisitionFacts(follows: Schemas["Follow"][]): Schemas["Follow"][] {
  // PAUSED FOR ALL once every requester holding the right has asked (round 10
  // Q6): the follow stops being looked for, as the generic pause stops it.
  return withRequesters(follows).map((follow) => {
    const settings = settingsOf(follow.title);
    return { ...follow, ...settings, status: settings.paused ? PAUSED : follow.status };
  });
}

/**
 * Writes the caller's own setting on one of their follows.
 *
 * @param followedId The follow, by its key.
 * @param change The setting written.
 * @returns The follow, decorated, or a refusal.
 */
function setOwn(followedId: string, change: Preference): unknown {
  const follow = followForKey(followedId);
  if (follow === undefined) return refused(MISSING, NO_SUCH);
  if (!requestersOf(follow.title).some((one) => one.id === signedInId())) return refused(FORBIDDEN, NOT_THEIRS);
  const preferences = preferencesOf(follow.title);
  preferences[signedInId()] = { ...preferences[signedInId()], ...change };
  return withAcquisitionFacts([follow])[0];
}

/** Every route this subject answers. */
export function requesterRoutes(): MockRoute[] {
  return [
    route("reassignRequester", POST, "/acquisition/requesters/reassign", (request) => {
      // THE ACQUISITION IS NAMED BY ITS MEDIUM'S KEY (K3-G4), followed or not.
      // The move is written under every title the medium is drawn with, so a card and a follow
      // of one medium say the same requesters afterwards; the answer is the first that held `from`.
      const [from, to] = [text(request.body, "from"), text(request.body, "to")];
      const moves = titlesOfKey(text(request.body, "acquisition")).map((title) => moveRequester(title, from, to));
      const moved = moves.find((one) => one !== null) ?? null;
      return moved === null ? refused(MISSING, NO_SUCH) : { requesters: moved };
    }),
    route("setAcquisitionQuality", PUT, "/acquisition/followed/{followedId}/quality", (request) => {
      const profile = field(request.body, "profile");
      return setOwn(request.parameters.followedId, { quality: typeof profile === "string" ? profile : null });
    }),
    route("setAcquisitionPause", PUT, "/acquisition/followed/{followedId}/pause", (request) =>
      setOwn(request.parameters.followedId, { paused: field(request.body, "paused") === true })),
  ];
}
