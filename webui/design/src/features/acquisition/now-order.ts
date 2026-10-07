// What « En cours » shows, and in what order — ONE derivation, read by the tab,
// its filter pill's count and the filter panel's counts (§13).
//
// THE SAME ZONE AS « SUIVIS » (the operator: the filter and sort zone is on every
// tab). What an acquisition on its way can be told apart by is its kind and how
// far it has gone, so the filter keeps the series or the films and the sort
// orders the queue as the engine serves it, by progress, or by title.
import type { QueueCard } from "../../lib/engine-queue";
import { titleMatches } from "./title-search";

/** The filter's choices, in the order its panel offers them. */
export const NOW_FILTERS = ["all", "series", "movies"] as const;
export type NowFilter = (typeof NOW_FILTERS)[number];

/** The sort's choices, in the order its panel offers them. */
export const NOW_SORTS = ["queue", "progress", "az", "za"] as const;
export type NowSort = (typeof NOW_SORTS)[number];

/**
 * Whether a card is kept by a filter.
 *
 * @param card The card.
 * @param filter The filter in force.
 * @returns True when the card is shown.
 */
function kept(card: QueueCard, filter: NowFilter): boolean {
  if (filter === "series") return card.kind !== "movie";
  if (filter === "movies") return card.kind === "movie";
  return true;
}

/**
 * How far a card has gone: the pipeline positions it has passed.
 *
 * @param card The card.
 * @returns The count of positions done.
 */
function progressOf(card: QueueCard): number {
  return (card.strip ?? []).filter((position) => position === 1).length;
}

const byTitle = (left: QueueCard, right: QueueCard) => left.title.localeCompare(right.title, "fr");

/**
 * The cards a filter keeps among those whose title holds the search, in the
 * order a sort asks.
 *
 * @param cards The cards on their way, in the order the queue serves them.
 * @param filter The filter in force.
 * @param sort The sort in force.
 * @param search What was typed in the zone.
 * @returns A new array: the cards kept, ordered.
 */
export function orderNow(cards: readonly QueueCard[], filter: NowFilter, sort: NowSort, search: string): QueueCard[] {
  const found = cards.filter((card) => kept(card, filter) && titleMatches(card.title, search));
  if (sort === "progress") return found.sort((left, right) => progressOf(right) - progressOf(left) || byTitle(left, right));
  if (sort === "az") return found.sort(byTitle);
  if (sort === "za") return found.sort((left, right) => byTitle(right, left));
  return found;
}

/**
 * How many cards each filter keeps, the search applied — the pill says what the
 * list shows, so each choice of its panel counts what the list would show.
 *
 * @param cards The cards on their way.
 * @param search What was typed in the zone.
 * @returns One count per filter.
 */
export function nowCounts(cards: readonly QueueCard[], search: string): Record<NowFilter, number> {
  const counts = { all: 0, series: 0, movies: 0 } as Record<NowFilter, number>;
  for (const filter of NOW_FILTERS) counts[filter] = orderNow(cards, filter, "queue", search).length;
  return counts;
}
