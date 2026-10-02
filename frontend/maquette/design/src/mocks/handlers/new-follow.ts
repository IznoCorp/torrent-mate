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
// The year no family knows is a BLANK, which the card leaves out: a 0 was drawn
// as a year, « 0 · série » (B-673).
const NEWLY_ADDED_YEAR = "";
// Milliseconds in a second: the clock reads one, the contract says the other.
const MILLISECONDS = 1000;

/**
 * The record of a follow just made.
 *
 * @param title The medium's title.
 * @param kind The medium's kind, as the request names it.
 * @param year The request's year, else the one the medium's identity names — possibly neither.
 * @param ids The medium's merged identity.
 * @param poster The poster of the entry it was followed from, if any.
 * @returns The new follow, fresh and not yet searched.
 */
export function newFollow(title: string, kind: string, year: number | string, ids: Follow["ids"],
  poster: string | null): Follow {
  return {
    title,
    kind,
    year: typeof year === "string" || Number.isFinite(year) ? year : NEWLY_ADDED_YEAR,
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
