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
  type Preference,
} from "../identity";
import { mockState } from "../state";
import { refused, type MockRoute } from "../router";
import { POST, PUT, field, route, text } from "./shared";
import type { components } from "../../contract/types";
import type { Right } from "../../features/account/rights";

type Schemas = components["schemas"];

// The quality floors, lowest first: the highest a right-holding requester set wins.
const FLOORS = ["720p", "1080p", "2160p"];
const FORBIDDEN = 403;
const MISSING = 404;
const NOT_THEIRS = "the caller is not among this acquisition's requesters";
const NO_SUCH = "no acquisition carries that title, or that requester";

/**
 * Adds its requesters to every row that names an acquisition.
 *
 * @param rows Follows or queue cards, each keyed by its title.
 * @returns The same rows, each carrying `requesters`.
 */
export function withRequesters<Row extends { title: string }>(rows: Row[]): (Row & { requesters: Schemas["AccountRef"][] })[] {
  return rows.map((row) => ({ ...row, requesters: requestersOf(row.title) }));
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
  return withRequesters(follows).map((follow) => ({ ...follow, ...settingsOf(follow.title) }));
}

/**
 * Writes the caller's own setting on one of their follows.
 *
 * @param followedId The follow, by its title.
 * @param change The setting written.
 * @returns The follow, decorated, or a refusal.
 */
function setOwn(followedId: string, change: Preference): unknown {
  const follow = mockState().follows.find((one) => one.title === followedId);
  if (follow === undefined) return refused(MISSING, NO_SUCH);
  if (!requestersOf(follow.title).some((one) => one.id === signedInId())) return refused(FORBIDDEN, NOT_THEIRS);
  const preferences = preferencesOf(follow.title);
  preferences[signedInId()] = { ...preferences[signedInId()], ...change };
  return withAcquisitionFacts([follow])[0];
}

/** Every route this subject answers. */
export function requesterRoutes(): MockRoute[] {
  return [
    route("reassignRequester", POST, "/api/acquisition/requesters/reassign", (request) => {
      const moved = moveRequester(text(request.body, "title"), text(request.body, "from"), text(request.body, "to"));
      return moved === null ? refused(MISSING, NO_SUCH) : { requesters: moved };
    }),
    route("setAcquisitionQuality", PUT, "/api/acquisition/followed/{followedId}/quality", (request) => {
      const profile = field(request.body, "profile");
      return setOwn(request.parameters.followedId, { quality: typeof profile === "string" ? profile : null });
    }),
    route("setAcquisitionPause", PUT, "/api/acquisition/followed/{followedId}/pause", (request) =>
      setOwn(request.parameters.followedId, { paused: field(request.body, "paused") === true })),
  ];
}
