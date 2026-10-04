// What « Suivis » shows, and in what order — ONE derivation, read by the tab,
// its filter pill's count and the filter panel's counts (§13).
//
// THE ONE PILL OF EVERY LIST (DECIDED 1 of maquette-blocked, § 1.9): the filter
// keeps the series or the films; the sort orders them five ways, by the
// operator's round 3 q1 = C — « Urgence » (today's one fixed order: a follow
// just made, then the status's urgency, then the title), « A → Z », « Z → A »,
// « Suivi récemment » (the follow's creation, `addedAt`), « Prochaine sortie »
// (the next release, `nextAirDate`, a follow with none last). The two dates are
// BK8: the maquette carries them in its follows seed.
import { URGENCY } from "./follow-vocabulary";
import type { Follow } from "./types";

/** The filter's choices, in the order its panel offers them. */
export const FOLLOW_FILTERS = ["tout", "series", "movies"] as const; // french-ok: « tout » is the pill's id, a data value the markup and the rules carry
export type FollowFilter = (typeof FOLLOW_FILTERS)[number];

/** The sort's choices, in the order its panel offers them. */
export const FOLLOW_SORTS = ["urgency", "az", "za", "added", "nextRelease"] as const;
export type FollowSort = (typeof FOLLOW_SORTS)[number];

// A status the table does not name sorts after every one it does.
const UNKNOWN_URGENCY =Object.keys(URGENCY).length;

/**
 * Whether a follow is kept by a filter.
 *
 * @param follow The follow.
 * @param filter The filter in force.
 * @returns True when the follow is shown.
 */
export function followKept(follow: Follow, filter: FollowFilter): boolean {
  if (filter === "series") return follow.kind !== "movie";
  if (filter === "movies") return follow.kind === "movie";
  return true;
}

/**
 * How many follows each filter keeps.
 *
 * @param follows The follows the list counts — the paused ones left out by the caller.
 * @returns One count per filter.
 */
export function followCounts(follows: readonly Follow[]): Record<FollowFilter, number> {
  const counts = { tout: 0, series: 0, movies: 0 } as Record<FollowFilter, number>;
  for (const filter of FOLLOW_FILTERS) counts[filter] = follows.filter((follow) => followKept(follow, filter)).length;
  return counts;
}

/**
 * The follows the list looks among: the active ones (a paused follow waits,
 * folded at the end, outside the list and its counts) whose title holds the
 * search typed in the filter zone, accents ignored.
 *
 * ONE BASIS FOR THE PILL AND ITS PANEL (the orchestrator's ruling on the lot's
 * open point 4): the pill says what the list shows, the search applied
 * (§ 1.1 bis: « the number of cards it shows »), so each choice of its panel
 * counts what the list would show once chosen — with the same search.
 *
 * @param follows Every follow, as read.
 * @param search The search typed, or empty.
 * @returns The follows looked among.
 */
export function followsInView(follows: readonly Follow[], search: string): Follow[] {
  const plain = (text: string) => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase();
  const term = plain(search.trim());
  return follows.filter((follow) => follow.status !== "disabled" && (term === "" || plain(follow.title).includes(term)));
}

/**
 * Compares two titles by French collation.
 *
 * @param left One follow.
 * @param right The other.
 * @returns The comparison.
 */
function byTitle(left: Follow, right: Follow): number {
  return left.title.localeCompare(right.title, "fr");
}

/**
 * The urgency order, today's one fixed order: a follow just made first, then
 * the status's urgency, then the title.
 *
 * @param left One follow.
 * @param right The other.
 * @returns The comparison.
 */
function byUrgency(left: Follow, right: Follow): number {
  return (left.fresh ? 0 : 1) - (right.fresh ? 0 : 1)
    || (URGENCY[left.status] ?? UNKNOWN_URGENCY) - (URGENCY[right.status] ?? UNKNOWN_URGENCY)
    || byTitle(left, right);
}

/**
 * The next release first, a follow with none last; the title between equals.
 *
 * @param left One follow.
 * @param right The other.
 * @returns The comparison.
 */
function byNextRelease(left: Follow, right: Follow): number {
  const [one, other] = [left.nextAirDate, right.nextAirDate];
  if (one === other) return byTitle(left, right);
  if (one === null) return 1;
  if (other === null) return -1;
  // ISO `YYYY-MM-DD`: the text's order is the calendar's.
  return one < other ? -1 : 1;
}

const COMPARE: Record<FollowSort, (left: Follow, right: Follow) => number> = {
  urgency: byUrgency,
  az: byTitle,
  za: (left, right) => byTitle(right, left),
  // The newest follow first; the title between two made at the same second.
  added: (left, right) => right.addedAt - left.addedAt || byTitle(left, right),
  nextRelease: byNextRelease,
};

/**
 * The follows a filter keeps, in the order a sort asks.
 *
 * @param follows The follows.
 * @param filter The filter in force.
 * @param sort The sort in force.
 * @returns A new array: the follows kept, ordered.
 */
export function orderFollows(follows: readonly Follow[], filter: FollowFilter, sort: FollowSort): Follow[] {
  return follows.filter((follow) => followKept(follow, filter)).sort(COMPARE[sort]);
}
