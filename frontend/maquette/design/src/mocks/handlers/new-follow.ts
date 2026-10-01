// The record a follow just made starts as.
//
// Every field the create request does not describe is a token or a blank,
// never a value copied off another record; the two dates of Suivis' sort pill
// (BK8) are the follow's creation, now, and no release date until the
// catalogue says one.
import type { components } from "../../contract/types";

type Follow = components["schemas"]["Follow"];

const NEWLY_ADDED_STATUS = "pending";
const NEWLY_ADDED_SINCE = "";
const NEWLY_ADDED_YEAR = 0;
// Milliseconds in a second: the clock reads one, the contract says the other.
const MILLISECONDS = 1000;

/**
 * The record of a follow just made.
 *
 * @param title The medium's title.
 * @param kind The medium's kind, as the request names it.
 * @param year The request's year, possibly not a number.
 * @param ids The medium's merged identity.
 * @param poster The poster of the entry it was followed from, if any.
 * @returns The new follow, fresh and not yet searched.
 */
export function newFollow(title: string, kind: string, year: number, ids: Follow["ids"],
  poster: string | null): Follow {
  return {
    title,
    kind,
    year: Number.isFinite(year) ? year : NEWLY_ADDED_YEAR,
    status: NEWLY_ADDED_STATUS,
    showStatus: null,
    since: NEWLY_ADDED_SINCE,
    addedAt: Math.floor(Date.now() / MILLISECONDS),
    nextAirDate: null,
    searches: 0,
    fresh: true,
    ids,
    poster,
  };
}
